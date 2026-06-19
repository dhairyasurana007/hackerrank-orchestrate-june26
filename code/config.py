"""Central configuration for the evidence-review pipeline.

Paths resolve relative to the repository root so the package works whether it is
invoked from the repo root or from within ``code/``. Secrets are read from the
environment at call time, never at import time.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional
    load_dotenv = None

REPO_ROOT = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    # Load a gitignored .env at the repo root so OPENROUTER_API_KEY (and optional
    # overrides) can live there instead of the shell environment.
    load_dotenv(REPO_ROOT / ".env")

DATASET_DIR = REPO_ROOT / "dataset"
IMAGES_DIR = DATASET_DIR / "images"

CLAIMS_CSV = DATASET_DIR / "claims.csv"
SAMPLE_CLAIMS_CSV = DATASET_DIR / "sample_claims.csv"
USER_HISTORY_CSV = DATASET_DIR / "user_history.csv"
EVIDENCE_REQUIREMENTS_CSV = DATASET_DIR / "evidence_requirements.csv"

OUTPUT_PATH = REPO_ROOT / "output.csv"
CACHE_DIR = REPO_ROOT / "code" / "cache"

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.6")

CONCURRENCY = int(os.environ.get("ER_CONCURRENCY", "4"))
MAX_RETRIES = int(os.environ.get("ER_MAX_RETRIES", "5"))
REQUEST_TIMEOUT = float(os.environ.get("ER_REQUEST_TIMEOUT", "60"))


class ConfigError(RuntimeError):
    """Raised when required runtime configuration (e.g. an API key) is missing."""


def get_api_key() -> str:
    """Return the OpenRouter API key from the environment (read at call time)."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ConfigError(
            "OPENROUTER_API_KEY is not set. Export it or add it to a .env file before "
            "making model calls. See .env.example."
        )
    return key
