"""Shared pytest fixtures for Roxy tests."""

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from roxy.config.loader import Config


@pytest.fixture
def tmp_config_path(tmp_path: Path) -> Path:
    """Return a temporary config file path."""
    return tmp_path / "config.yaml"


@pytest.fixture
def config(tmp_config_path: Path) -> Config:
    """Return a Config instance using a temporary file."""
    cfg = Config(path=tmp_config_path)
    return cfg


@pytest.fixture
def populated_config(config: Config) -> Config:
    """Return a Config with sample data loaded."""
    config.load()
    config.set("user.name", "TestUser")
    config.set("user.identity", "Researcher")
    config.set("user.research_domain", "bioinformatics")
    config.set("user.topics", ["protein folding", "drug design"])
    config.set("models.default", "openai/gpt-4.1-mini")
    config.set("models.providers.openai.api_key", "sk-test1234567890abcdef")
    config.save()
    return config


@pytest.fixture
def clean_env(monkeypatch: Any) -> None:
    """Remove ROXY_* env vars to isolate tests."""
    for key in list(os.environ.keys()):
        if key.startswith("ROXY_"):
            monkeypatch.delenv(key, raising=False)
