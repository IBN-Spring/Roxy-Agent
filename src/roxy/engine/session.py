"""SessionManager — persist and resume chat sessions as JSON files."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roxy.config.paths import sessions_dir


class SessionManager:
    """Create, save, load, list, and delete chat sessions.

    Sessions are stored as JSON files in ~/.roxy/sessions/<session_id>.json.
    """

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or sessions_dir()

    # ── create ───────────────────────────────────────────────────

    def create(self, model: str = "", workspace: str = "") -> Session:
        """Create a new session with a unique ID."""
        session_id = uuid.uuid4().hex[:12]
        session = Session(
            id=session_id,
            created_at=datetime.now(timezone.utc),
            model=model,
            workspace=workspace,
        )
        return session

    # ── save / load ──────────────────────────────────────────────

    def save(self, session: Session) -> Path:
        """Persist a session to disk. Returns the file path."""
        session.updated_at = datetime.now(timezone.utc)
        data = session.to_dict()
        path = self._path_for(session.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return path

    def load(self, session_id: str) -> Session | None:
        """Load a session by ID. Returns None if not found."""
        path = self._path_for(session_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Session.from_dict(data)

    # ── list / delete ────────────────────────────────────────────

    def list_sessions(self, limit: int = 20) -> list[Session]:
        """List recent sessions, newest first."""
        sessions: list[Session] = []
        for path in sorted(self.base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(sessions) >= limit:
                break
            try:
                session = self.load(path.stem)
                if session:
                    sessions.append(session)
            except Exception:
                continue
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session file. Returns True if it existed."""
        path = self._path_for(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    # ── helpers ──────────────────────────────────────────────────

    def _path_for(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"


class Session:
    """A single chat session."""

    def __init__(
        self,
        id: str = "",
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        model: str = "",
        workspace: str = "",
        messages: list[dict[str, Any]] | None = None,
        message_count: int = 0,
    ):
        self.id = id or uuid.uuid4().hex[:12]
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or self.created_at
        self.model = model
        self.workspace = workspace
        self.messages: list[dict[str, Any]] = messages or []
        self.message_count = message_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "model": self.model,
            "workspace": self.workspace,
            "messages": self.messages,
            "message_count": len(self.messages),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        created = data.get("created_at", "")
        updated = data.get("updated_at", "")
        return cls(
            id=data.get("id", ""),
            created_at=datetime.fromisoformat(created) if created else None,
            updated_at=datetime.fromisoformat(updated) if updated else None,
            model=data.get("model", ""),
            workspace=data.get("workspace", ""),
            messages=data.get("messages", []),
            message_count=data.get("message_count", 0),
        )
