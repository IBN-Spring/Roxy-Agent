"""Tests for SessionManager — create, save, load, list, delete."""

import json
from pathlib import Path

from roxy.engine.session import Session, SessionManager


class TestSessionCreate:
    def test_create_has_id(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        session = sm.create()
        assert session.id
        assert len(session.id) == 12

    def test_create_stores_model(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        session = sm.create(model="openai/gpt-4.1")
        assert session.model == "openai/gpt-4.1"

    def test_create_stores_workspace(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        session = sm.create(workspace="/tmp/project")
        assert session.workspace == "/tmp/project"


class TestSessionSaveLoad:
    def test_save_and_load_roundtrip(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        session = sm.create(model="test/model")
        session.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        sm.save(session)

        loaded = sm.load(session.id)
        assert loaded is not None
        assert loaded.id == session.id
        assert loaded.model == "test/model"
        assert len(loaded.messages) == 2
        assert loaded.messages[0]["content"] == "hello"

    def test_load_nonexistent(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        assert sm.load("nonexistent") is None

    def test_save_creates_file(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        session = sm.create()
        path = sm.save(session)
        assert path.exists()
        assert path.suffix == ".json"

        # Verify JSON content
        with open(path, "r") as f:
            data = json.load(f)
        assert data["id"] == session.id
        assert "created_at" in data


class TestSessionList:
    def test_list_returns_sessions(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        s1 = sm.create()
        s2 = sm.create()
        sm.save(s1)
        sm.save(s2)

        sessions = sm.list_sessions()
        ids = {s.id for s in sessions}
        assert s1.id in ids
        assert s2.id in ids

    def test_list_respects_limit(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        for _ in range(10):
            s = sm.create()
            sm.save(s)

        sessions = sm.list_sessions(limit=3)
        assert len(sessions) == 3


class TestSessionDelete:
    def test_delete_existing(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        session = sm.create()
        sm.save(session)

        assert sm.delete(session.id) is True
        assert sm.load(session.id) is None

    def test_delete_nonexistent(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        assert sm.delete("nonexistent") is False


class TestSessionToDict:
    def test_to_dict_includes_all_fields(self, tmp_path: Path):
        sm = SessionManager(base_dir=tmp_path)
        session = sm.create(model="x", workspace="/w")
        session.messages = [{"role": "user", "content": "hi"}]
        d = session.to_dict()
        assert d["id"] == session.id
        assert d["model"] == "x"
        assert d["workspace"] == "/w"
        assert d["message_count"] == 1
        assert len(d["messages"]) == 1
        assert "created_at" in d
        assert "updated_at" in d
