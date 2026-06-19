"""Config loader — layered resolution: CLI flags > env vars > YAML file > defaults."""

import os
from pathlib import Path
from typing import Any

import yaml

from roxy.config.paths import config_file
from roxy.config.schema import DEFAULTS, mask_value


class Config:
    """Layered config: CLI flags > env vars > YAML file > defaults.

    Usage:
        cfg = Config()
        cfg.load()
        model = cfg.get("models.default")
        cfg.set("user.name", "Alice")
        cfg.save()
    """

    def __init__(self, path: Path | None = None):
        self._path = path or config_file()
        self._data: dict[str, Any] = {}
        self._cli_overrides: dict[str, Any] = {}

    # ── load / save ──────────────────────────────────────────────

    def load(self) -> None:
        """Load config from YAML file. Missing file = use defaults (no error)."""
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}

    def save(self) -> None:
        """Atomically write config to YAML file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._data, f, allow_unicode=True, default_flow_style=False)
        tmp.replace(self._path)

    # ── get / set ────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Resolve a config key: CLI overrides → env var → YAML → defaults.

        Env var naming: dots→underscores, uppercase.  e.g. 'models.default' → ROXY_MODELS_DEFAULT
        """
        # 1. CLI override (highest priority)
        if key in self._cli_overrides:
            return self._cli_overrides[key]

        # 2. Environment variable
        env_key = "ROXY_" + key.upper().replace(".", "_")
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return self._coerce_type(env_val, key)

        # 3. YAML file (dotted path)
        val = self._get_nested(key)
        if val is not None:
            return val

        # 4. Built-in default
        return DEFAULTS.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value in the YAML layer (written on save())."""
        self._set_nested(key, value)

    def set_cli_override(self, key: str, value: Any) -> None:
        """Set a CLI-level override (highest priority, not persisted)."""
        self._cli_overrides[key] = value

    def is_configured(self, feature: str) -> bool:
        """Check if a feature's required keys are set (truthy)."""
        required_map = {
            "llm": ["models.default"],
            "user": ["user.name"],
            "research": ["user.research_domain", "user.topics"],
        }
        keys = required_map.get(feature, [feature])
        return all(bool(self.get(k)) for k in keys)

    # ── display ──────────────────────────────────────────────────

    def to_dict(self, mask_secrets: bool = True) -> dict[str, Any]:
        """Return all config as a flat dict. Optionally mask secret values."""
        result: dict[str, Any] = {}
        self._flatten(self._data, "", result)

        # Apply CLI overrides on top
        for k, v in self._cli_overrides.items():
            result[k] = f"{v} (cli)"

        # Add DEFAULTS for keys not present
        for k, v in DEFAULTS.items():
            if k not in result:
                result[k] = v

        if mask_secrets:
            return {k: mask_value(k, v) if isinstance(v, str) else v for k, v in result.items()}
        return result

    # ── internal helpers ─────────────────────────────────────────

    def _get_nested(self, key: str) -> Any:
        """Get a dotted-path key from self._data."""
        parts = key.split(".")
        node: Any = self._data
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        return node

    def _set_nested(self, key: str, value: Any) -> None:
        """Set a dotted-path key in self._data."""
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def _flatten(self, data: dict, prefix: str, result: dict) -> None:
        """Recursively flatten a nested dict into dotted keys."""
        for k, v in data.items():
            full_key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
            if isinstance(v, dict) and not any(isinstance(v2, dict) for v2 in v.values()):
                # Leaf dict: keep as-is
                result[full_key] = v
            elif isinstance(v, dict):
                self._flatten(v, full_key, result)
            else:
                result[full_key] = v

    @staticmethod
    def _coerce_type(value: str, key: str) -> Any:
        """Coerce an env-var string to the type expected by the key."""
        # Booleans
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        # Lists (comma-separated)
        if key in ("user.topics", "user.info_sources"):
            return [v.strip() for v in value.split(",") if v.strip()]
        # Integers
        if key.startswith("monitoring."):
            try:
                return int(value)
            except ValueError:
                pass
        return value
