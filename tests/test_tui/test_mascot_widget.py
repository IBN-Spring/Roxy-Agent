"""Tests for the TUI pixel status widget."""

from rich.text import Text

from roxy.tui.widgets.mascot import MascotWidget


def test_mascot_renders_rich_text():
    widget = MascotWidget()
    rendered = widget.render()
    assert isinstance(rendered, Text)
    assert ">" in rendered.plain


def test_mascot_has_expected_states():
    expected = {"idle", "thinking", "typing", "tool", "magic", "success", "error"}
    assert expected.issubset(set(MascotWidget.FRAMES))


def test_unknown_state_falls_back_to_idle(monkeypatch):
    widget = MascotWidget()
    monkeypatch.setattr(widget, "update", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(widget, "set_interval", lambda *_args, **_kwargs: None)

    widget.set_state("unknown")

    assert widget._state == "idle"


def test_magic_alias_uses_tool_frames():
    assert MascotWidget.FRAMES["magic"] is MascotWidget.FRAMES["tool"]
