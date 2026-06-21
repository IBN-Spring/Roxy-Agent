"""Tests for slash command dispatch logic (unit tests, no TUI needed)."""

import pytest

from roxy.config.loader import Config
from roxy.tui.screens.chat import ChatScreen, HELP_TEXT


class _FakeEngine:
    """Minimal fake for testing slash commands that don't need the engine."""
    session_id = "test12345678"
    message_count = 0

    class provider:
        @staticmethod
        def resolve_model(override=None):
            return override or "deepseek/deepseek-chat"


class TestSlashCommands:
    """Test slash command dispatch returns correct strings."""

    @pytest.fixture
    def screen(self) -> ChatScreen:
        cfg = Config()
        cfg.load()
        return ChatScreen.__new__(ChatScreen)

    def _setup_engine(self, screen: ChatScreen):
        screen._engine = _FakeEngine()
        screen._session = type("s", (), {"id": "test12345678", "message_count": 0})()
        screen.config = Config()
        screen.model_override = None

    def test_help(self, screen: ChatScreen):
        result = screen._handle_slash("/help")
        assert "Agent" in result or "Slash Commands" in result or "Chat Commands" in result
        assert "/status" in result
        assert "/evolve" in result

    def test_model_show(self, screen: ChatScreen):
        self._setup_engine(screen)
        result = screen._handle_slash("/model")
        assert "deepseek/deepseek-chat" in result

    def test_model_switch(self, screen: ChatScreen):
        self._setup_engine(screen)
        result = screen._handle_slash("/model openai/gpt-4.1")
        assert "openai/gpt-4.1" in result
        assert screen.model_override == "openai/gpt-4.1"

    def test_sessions_empty(self, screen: ChatScreen):
        # Create screen with fake engine pointing at isolated sessions dir
        screen._engine = _FakeEngine()
        screen._session = type("s", (), {"id": "test12345678", "message_count": 0})()
        result = screen._handle_slash("/sessions")
        assert "No saved sessions" in result or "Recent Sessions" in result

    def test_doctor(self, screen: ChatScreen):
        self._setup_engine(screen)
        result = screen._handle_slash("/doctor")
        assert "Roxy Status" in result

    def test_clear(self, screen: ChatScreen):
        """Clear needs a mounted Textual DOM — just verify the handler exists."""
        assert hasattr(screen, "_cmd_clear")

    def test_resume_no_arg(self, screen: ChatScreen):
        result = screen._handle_slash("/resume")
        assert "Usage" in result

    def test_resume_not_found(self, screen: ChatScreen):
        result = screen._handle_slash("/resume nonexis7")
        assert "not found" in result.lower()

    def test_unknown_command(self, screen: ChatScreen):
        result = screen._handle_slash("/foobar")
        assert "Unknown command" in result

    def test_help_text_has_all_commands(self, screen: ChatScreen):
        # v1.0 test: verify key commands appear in help
        assert "/status" in HELP_TEXT
        assert "/evolve" in HELP_TEXT
        assert "/kb" in HELP_TEXT
        assert "/sessions" in HELP_TEXT
        assert "/resume" in HELP_TEXT
        assert "/exit" in HELP_TEXT

    # ── research commands ────────────────────────────────────

    def test_feeds(self, screen: ChatScreen):
        result = screen._handle_slash("/feeds")
        assert "Feed" in result or "feeds" in result.lower() or "No feeds" in result

    def test_runs(self, screen: ChatScreen):
        result = screen._handle_slash("/runs")
        assert "Run" in result or "runs" in result.lower() or "No collection" in result

    def test_digest_default(self, screen: ChatScreen):
        result = screen._handle_slash("/digest")
        assert "Digest" in result or "digest" in result.lower() or "No entries" in result

    def test_digest_30(self, screen: ChatScreen):
        result = screen._handle_slash("/digest 30")
        assert "Digest" in result or "digest" in result.lower() or "No entries" in result

    # ── v1.0 evolution commands ────────────────────────────

    def test_evolve_cmd(self, screen: ChatScreen):
        result = screen._handle_slash("/evolve")
        assert "Evolution" in result or "proposal" in result.lower() or "No proposals" in result

    def test_proposals_cmd(self, screen: ChatScreen):
        result = screen._handle_slash("/proposals")
        assert "Evolution" in result or "proposal" in result.lower() or "No proposals" in result

    def test_proposal_no_arg(self, screen: ChatScreen):
        result = screen._handle_slash("/proposal")
        assert "Usage" in result

    def test_kb_no_query(self, screen: ChatScreen):
        result = screen._handle_slash("/kb")
        assert "Usage" in result

    def test_kb_search(self, screen: ChatScreen):
        result = screen._handle_slash("/kb test")
        assert "KB Search" in result or "No results" in result or "empty" in result.lower()

    def test_collect_no_feeds(self, screen: ChatScreen):
        self._setup_engine(screen)
        result = screen._handle_slash("/collect")
        assert "No feeds" in result or "feeds" in result.lower() or "disabled" in result.lower()

    def test_status(self, screen: ChatScreen):
        self._setup_engine(screen)
        result = screen._handle_slash("/status")
        assert "Dashboard" in result or "model" in result.lower()

    def test_tool_summary_is_compact(self, screen: ChatScreen):
        log = [{
            "calls": ["web_fetch", "web_fetch", "web_fetch", "web_fetch"],
            "results": [
                {"tool": "web_fetch", "success": True, "preview": "a" * 200},
                {"tool": "web_fetch", "success": False, "preview": "b" * 200},
                {"tool": "knowledge_query", "success": True, "preview": "c" * 200},
                {"tool": "web_fetch", "success": True, "preview": "d" * 200},
            ],
        }]

        result = screen._format_tool_summary(log)

        assert "+1 more" in result
        assert "1 more tool result" in result
        assert len(result.splitlines()) == 5
