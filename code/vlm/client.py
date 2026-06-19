"""OpenRouter VLM client with caching, retry, and usage tracking (MVP-4).

The client is the single chokepoint for vision+text model calls. A transport
callable is injected so tests can run fully mocked, never touching the network.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import config

RETRY_STATUS = {429, 500, 502, 503, 504}


class VLMError(RuntimeError):
    """Raised when a model call fails after retries or inputs are invalid."""


class RetryableError(RuntimeError):
    """Marker for transport errors that should be retried."""


@dataclass
class VLMResponse:
    data: dict
    raw_text: str
    usage: dict
    images: int
    cached: bool


_SUPPORTED_FORMATS = {"jpeg", "png", "gif", "webp"}


def _sniff_format(raw: bytes) -> str | None:
    """Detect the true image format from magic bytes (extensions are unreliable here)."""
    if raw[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if raw[:4] == b"\x89PNG":
        return "png"
    if raw[:3] == b"GIF":
        return "gif"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return None


def _reencode_to_jpeg(path: Path) -> bytes:
    """Decode any Pillow-readable image (including HEIC) and re-encode as JPEG."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise VLMError(
            f"cannot decode {path.name}: install Pillow (and pillow-heif for HEIC)"
        ) from exc
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
        register_avif = getattr(pillow_heif, "register_avif_opener", None)
        if register_avif is not None:
            register_avif()
    except ImportError:
        pass
    try:
        import pillow_avif  # noqa: F401  (registers AVIF support with Pillow on import)
    except ImportError:
        pass
    try:
        with Image.open(path) as image:
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=90)
            return buffer.getvalue()
    except Exception as exc:
        raise VLMError(f"could not decode image {path.name}: {exc}") from exc


def encode_image(path: Path) -> dict:
    """Return an OpenAI-style image content block, normalized to a supported format.

    Many dataset files carry a .jpg extension but contain PNG/WebP/HEIC bytes, which
    the provider rejects. We sniff the real format and re-encode unsupported ones.
    """
    if not path.exists():
        raise VLMError(f"image not found: {path}")
    raw = path.read_bytes()
    fmt = _sniff_format(raw)
    if fmt in _SUPPORTED_FORMATS:
        data, media = raw, f"image/{fmt}"
    else:
        data, media = _reencode_to_jpeg(path), "image/jpeg"
    b64 = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{media};base64,{b64}"}}


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (RetryableError, TimeoutError)):
        return True
    return getattr(exc, "status_code", None) in RETRY_STATUS


def _default_transport(messages, model):
    from openai import OpenAI

    client = OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.get_api_key())
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
    )
    text = completion.choices[0].message.content or ""
    usage = {}
    if completion.usage is not None:
        usage = {
            "input_tokens": completion.usage.prompt_tokens,
            "output_tokens": completion.usage.completion_tokens,
        }
    return text, usage


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise VLMError("model did not return valid JSON") from None


@dataclass
class VLMClient:
    model: str = field(default_factory=lambda: config.MODEL)
    transport: object = _default_transport
    cache_dir: Path = field(default_factory=lambda: config.CACHE_DIR)
    max_retries: int = field(default_factory=lambda: config.MAX_RETRIES)
    prompt_version: str = "v1"
    backoff_base: float = 0.5

    def __post_init__(self):
        self.stats = {
            "calls": 0, "cache_hits": 0, "input_tokens": 0, "output_tokens": 0, "images": 0,
        }

    def _cache_key(self, system, user_text, image_paths):
        hasher = hashlib.sha256()
        for part in (self.prompt_version, self.model, system, user_text):
            hasher.update(part.encode("utf-8"))
        for path in image_paths:
            try:
                hasher.update(path.read_bytes())
            except OSError as exc:
                raise VLMError(f"image not found: {path}") from exc
        return hasher.hexdigest()

    def _backoff(self, attempt):
        return self.backoff_base * (2 ** (attempt - 1))

    def _build_messages(self, system, user_text, image_paths):
        content = [{"type": "text", "text": user_text}]
        content.extend(encode_image(path) for path in image_paths)
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ]

    def _call_with_retry(self, messages):
        attempt = 0
        while True:
            try:
                return self.transport(messages, self.model)
            except Exception as exc:
                attempt += 1
                if attempt > self.max_retries or not _is_retryable(exc):
                    raise VLMError(f"model call failed: {exc}") from exc
                time.sleep(self._backoff(attempt))

    def complete(self, system, user_text, image_paths=()) -> VLMResponse:
        paths = [Path(p) for p in image_paths]
        key = self._cache_key(system, user_text, paths)
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            self.stats["cache_hits"] += 1
            return VLMResponse(cached=True, **payload)
        text, usage = self._call_with_retry(self._build_messages(system, user_text, paths))
        data = _parse_json(text)
        self.stats["calls"] += 1
        self.stats["images"] += len(paths)
        self.stats["input_tokens"] += usage.get("input_tokens", 0)
        self.stats["output_tokens"] += usage.get("output_tokens", 0)
        payload = {"data": data, "raw_text": text, "usage": usage, "images": len(paths)}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(payload), encoding="utf-8")
        return VLMResponse(cached=False, **payload)
