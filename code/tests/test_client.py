"""Tests for the OpenRouter VLM client (MVP-4)."""
from __future__ import annotations

import json

import pytest

from vlm import client as vlm


def _img(tmp_path, name="a.jpg", data=b"\xff\xd8\xff\xe0jpg"):
    path = tmp_path / name
    path.write_bytes(data)
    return path


class FakeTransport:
    def __init__(self, payload=None, usage=None, fail_times=0, exc=None):
        self.text = json.dumps(payload if payload is not None else {"ok": True})
        self.usage = usage or {"input_tokens": 10, "output_tokens": 5}
        self.fail_times = fail_times
        self.exc = exc or vlm.RetryableError("429")
        self.calls = 0

    def __call__(self, messages, model):
        self.calls += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.exc
        return self.text, self.usage


def _client(tmp_path, transport, **kw):
    return vlm.VLMClient(transport=transport, cache_dir=tmp_path / "cache", backoff_base=0, **kw)


def test_cache_miss_then_hit(tmp_path):
    img = _img(tmp_path)
    fake = FakeTransport()
    client = _client(tmp_path, fake)
    first = client.complete("sys", "user", [img])
    assert first.cached is False and fake.calls == 1
    second = client.complete("sys", "user", [img])
    assert second.cached is True and fake.calls == 1
    assert client.stats["cache_hits"] == 1


def test_retry_then_success(tmp_path):
    fake = FakeTransport(fail_times=2)
    client = _client(tmp_path, fake)
    result = client.complete("sys", "user", [_img(tmp_path)])
    assert result.data == {"ok": True}
    assert fake.calls == 3


def test_non_retryable_raises(tmp_path):
    fake = FakeTransport(fail_times=1, exc=ValueError("bad"))
    client = _client(tmp_path, fake)
    with pytest.raises(vlm.VLMError):
        client.complete("sys", "user", [_img(tmp_path)])


def test_retry_exhausted_raises(tmp_path):
    fake = FakeTransport(fail_times=99)
    client = _client(tmp_path, fake, max_retries=2)
    with pytest.raises(vlm.VLMError):
        client.complete("sys", "user", [_img(tmp_path)])
    assert fake.calls == 3


def test_missing_image_reported(tmp_path):
    client = _client(tmp_path, FakeTransport())
    with pytest.raises(vlm.VLMError):
        client.complete("sys", "user", [tmp_path / "nope.jpg"])


def test_image_media_types(tmp_path):
    jpg = _img(tmp_path, "a.jpg")
    png = _img(tmp_path, "b.png", b"\x89PNG\r\n")
    assert vlm.encode_image(jpg)["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert vlm.encode_image(png)["image_url"]["url"].startswith("data:image/png;base64,")


def test_usage_counters(tmp_path):
    fake = FakeTransport(usage={"input_tokens": 12, "output_tokens": 7})
    client = _client(tmp_path, fake)
    client.complete("sys", "user", [_img(tmp_path)])
    assert client.stats["calls"] == 1
    assert client.stats["input_tokens"] == 12
    assert client.stats["output_tokens"] == 7
    assert client.stats["images"] == 1


def test_sniff_detects_webp_despite_jpg_extension(tmp_path):
    path = tmp_path / "x.jpg"
    path.write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
    assert vlm.encode_image(path)["image_url"]["url"].startswith("data:image/webp")


def test_all_sample_images_encode_to_supported_format():
    import config
    from data import loaders

    supported = ("data:image/jpeg", "data:image/png", "data:image/webp", "data:image/gif")
    for record in loaders.load_claims(config.SAMPLE_CLAIMS_CSV):
        for img in record.images:
            url = vlm.encode_image(img.path)["image_url"]["url"]
            assert url.startswith(supported), f"{img.path.name}: {url[:25]}"
