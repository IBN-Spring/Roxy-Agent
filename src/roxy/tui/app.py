"""Roxy TUI App — Textual application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from textual.app import App

from roxy.config.loader import Config
from roxy.engine.session import Session, SessionManager
from roxy.tui.screens.chat import ChatScreen


class RoxyApp(App):
    """Main Textual application for Roxy Chat."""

    TITLE = "Roxy"
    SUB_TITLE = "Vertical-domain research agent"

    CSS = """
    Screen {
        background: $surface;
    }
    """

    def __init__(
        self,
        config: Config,
        session: Session | None = None,
        model: str | None = None,
    ):
        super().__init__()
        self.roxy_config = config
        self.roxy_session = session
        self.roxy_model = model

    def on_mount(self) -> None:
        """Push the chat screen when the app mounts."""
        self.push_screen(
            ChatScreen(
                config=self.roxy_config,
                session=self.roxy_session,
                model=self.roxy_model,
            )
        )


def launch_tui(
    config: Config,
    session_id: str | None = None,
    model: str | None = None,
) -> None:
    """Launch the Roxy TUI.

    Args:
        config: Loaded Roxy config.
        session_id: Optional session ID to resume.
        model: Optional model override.
    """
    session: Session | None = None

    if session_id:
        sm = SessionManager()
        session = sm.load(session_id)
        if session is None:
            print(f"Session '{session_id}' not found. Starting a new session.")

    app = RoxyApp(config=config, session=session, model=model)
    app.run()
