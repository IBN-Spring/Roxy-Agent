"""Standard paths for Roxy configuration and data."""

from pathlib import Path


def roxy_home() -> Path:
    """Return the Roxy home directory (~/.roxy), creating it if needed."""
    path = Path.home() / ".roxy"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    """Path to the main config YAML file."""
    return roxy_home() / "config.yaml"


def sessions_dir() -> Path:
    """Path to the sessions directory."""
    path = roxy_home() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def knowledge_dir() -> Path:
    """Path to the knowledge base directory."""
    path = roxy_home() / "knowledge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def knowledge_db() -> Path:
    """Path to the SQLite knowledge database."""
    return knowledge_dir() / "roxy.db"


def skills_dir() -> Path:
    """Path to built-in skills directory (within the package)."""
    # Resolved relative to this file's location: src/roxy/config/paths.py → src/roxy → src → roxy/
    return Path(__file__).resolve().parent.parent.parent.parent / "skills"
