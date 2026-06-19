"""Tests for the configuration module (MVP-1)."""
from __future__ import annotations

import importlib

import pytest

import config


def test_dataset_paths_exist():
    assert config.CLAIMS_CSV.exists()
    assert config.SAMPLE_CLAIMS_CSV.exists()
    assert config.USER_HISTORY_CSV.exists()
    assert config.EVIDENCE_REQUIREMENTS_CSV.exists()
    assert config.IMAGES_DIR.is_dir()


def test_import_does_not_require_key():
    importlib.reload(config)


def test_get_api_key_raises_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(config.ConfigError):
        config.get_api_key()


def test_get_api_key_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert config.get_api_key() == "sk-or-test"
