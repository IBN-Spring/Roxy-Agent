"""Config schema — key definitions, defaults, and validation."""

from dataclasses import dataclass, field
from typing import Any


# Default config values, used when nothing is set in YAML or env.
DEFAULTS: dict[str, Any] = {
    "models.default": "openai/gpt-4.1-mini",
    "models.providers": {},
    "user.name": "",
    "user.identity": "",
    "user.research_domain": "",
    "user.topics": [],
    "user.info_sources": [],
    "workspace.path": "",
    "ui.theme": "dark",
    "monitoring.enabled": False,
    "comm.notifier": "",
}

# Config keys that contain secrets — masked in `roxy config list` output.
SECRET_KEYS = {
    "api_key",
    "token",
    "password",
    "secret",
    "cookie",
}

# Valid provider configuration keys per provider entry.
PROVIDER_KEYS = {"api_key", "base_url", "api_version"}


def mask_value(key: str, value: str) -> str:
    """Mask a secret value for display. Shows first 6 chars + '...'."""
    if not value or not isinstance(value, str):
        return str(value) if value else ""
    for secret_hint in SECRET_KEYS:
        if secret_hint in key.lower():
            if len(value) <= 12:
                return value[:4] + "****"
            return value[:6] + "..." + value[-4:]
    return value


def validate_config(data: dict[str, Any]) -> list[str]:
    """Validate config data. Returns a list of error messages (empty = valid)."""
    errors: list[str] = []

    # Validate models
    default_model = data.get("models.default", DEFAULTS["models.default"])
    if default_model and "/" not in str(default_model):
        errors.append(f"models.default: invalid model format '{default_model}', expected 'provider/model'")

    # Validate providers
    providers = data.get("models.providers", {})
    if isinstance(providers, dict):
        for name, cfg in providers.items():
            if isinstance(cfg, dict):
                unknown = set(cfg.keys()) - PROVIDER_KEYS
                if unknown:
                    errors.append(f"models.providers.{name}: unknown keys {unknown}")

    # Validate user topics
    topics = data.get("user.topics", [])
    if not isinstance(topics, list):
        errors.append("user.topics: must be a list")

    # Validate info sources
    sources = data.get("user.info_sources", [])
    if not isinstance(sources, list):
        errors.append("user.info_sources: must be a list")

    return errors
