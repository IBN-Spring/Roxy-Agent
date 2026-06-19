"""ChatScreen — main TUI chat interface."""

from __future__ import annotations

import asyncio
import logging

from textual.screen import Screen
from textual.containers import VerticalScroll, Container
from textual.widgets import Static

from roxy.config.loader import Config
from roxy.engine.query_engine import QueryEngine, TurnOutput
from roxy.engine.session import Session, SessionManager
from roxy.tui.widgets.input_area import InputArea
from roxy.tui.widgets.message import MessageWidget
from roxy.tui.widgets.status_bar import StatusBar

logger = logging.getLogger(__name__)


class ChatScreen(Screen):
    """Main chat screen: message history + input + status bar."""

    DEFAULT_CSS = """
    ChatScreen {
        layout: vertical;
    }
    #message-list {
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
    }
    #thinking-indicator {
        height: auto;
        padding: 0 2;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        config: Config,
        session: Session | None = None,
        model: str | None = None,
    ):
        super().__init__()
        self.config = config
        self.model_override = model
        self._engine: QueryEngine | None = None
        self._session = session
        self._streaming_task: asyncio.Task | None = None
        self._current_assistant_msg: MessageWidget | None = None

    # ── lifecycle ────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Set up the engine, restore session messages, update status."""
        sm = SessionManager()
        self._session = self._session or sm.create(
            model=self.model_override or self.config.get("models.default"),
        )
        self._engine = QueryEngine(self.config, self._session)

        # Restore existing messages from a resumed session
        msg_list = self.query_one("#message-list", VerticalScroll)
        for msg in self._session.messages:
            self._add_message(msg["role"], msg.get("content", ""))

        # Update status bar
        self._update_status()

        # Focus input
        self.query_one(InputArea).focus_input()

    # ── compose ──────────────────────────────────────────────────

    def compose(self):
        yield VerticalScroll(id="message-list")
        yield Static("", id="thinking-indicator")
        yield InputArea()
        yield StatusBar()

    # ── message handling ─────────────────────────────────────────

    def on_input_area_submit_message(self, event: InputArea.SubmitMessage) -> None:
        """Handle user submitting a message."""
        if self._streaming_task and not self._streaming_task.done():
            return  # Already processing

        user_text = event.text
        self._add_message("user", user_text)
        self._update_status()

        # Start streaming in background
        self._streaming_task = asyncio.create_task(self._run_stream(user_text))

    async def _run_stream(self, user_input: str) -> None:
        """Run the query engine and stream results to the TUI."""
        if not self._engine:
            return

        thinking = self.query_one("#thinking-indicator", Static)
        thinking.update("Thinking...")

        # Accumulator for streaming content
        full_content = ""

        try:
            async for output in self._engine.submit_message(user_input, self.model_override):
                if output.type == "chunk":
                    full_content += output.content
                    self._upsert_assistant_message(full_content)

                elif output.type == "tool_call":
                    calls = output.meta.get("calls", [])
                    thinking.update(f"🔧 Calling: {', '.join(calls)}")

                elif output.type == "tool_result":
                    tool = output.meta.get("tool", "")
                    ok = output.meta.get("success", False)
                    icon = "✓" if ok else "✗"
                    thinking.update(f"  {icon} {tool}")

                elif output.type == "done":
                    thinking.update("")

                elif output.type == "error":
                    thinking.update("")
                    self._add_message("error", output.content)

                elif output.type == "status":
                    model = output.meta.get("model", "")
                    thinking.update(f"Thinking... [{model}]")
        except Exception as exc:
            logger.error(f"Stream error: {exc}")
            thinking.update("")
            self._add_message("error", f"Error: {exc}")
        finally:
            thinking.update("")
            self._finalize_assistant_message(full_content)
            self._update_status()
            self._session = self._engine.session if self._engine else None

    # ── message rendering helpers ────────────────────────────────

    def _add_message(self, role: str, content: str) -> MessageWidget:
        """Add a message widget to the message list."""
        msg_list = self.query_one("#message-list", VerticalScroll)
        widget = MessageWidget(role, content)
        msg_list.mount(widget)
        msg_list.scroll_end(animate=False)
        return widget

    def _upsert_assistant_message(self, content: str) -> None:
        """Create or update the streaming assistant message."""
        if self._current_assistant_msg is None:
            self._current_assistant_msg = self._add_message("assistant", content)
        else:
            self._current_assistant_msg.content = content
            self._current_assistant_msg.refresh()

    def _finalize_assistant_message(self, content: str) -> None:
        """Finalize the streaming assistant message."""
        if self._current_assistant_msg and content.strip():
            self._current_assistant_msg.content = content
            self._current_assistant_msg.refresh()
        elif self._current_assistant_msg and not content.strip():
            # Empty response — keep last message but don't double-add
            pass
        self._current_assistant_msg = None

    # ── status bar ───────────────────────────────────────────────

    def _update_status(self) -> None:
        """Update the status bar with current engine state."""
        if not self._engine:
            return
        bar = self.query_one(StatusBar)
        bar.update(
            model=self._engine.provider.resolve_model(self.model_override),
            session_id=self._engine.session_id,
            msg_count=self._engine.message_count,
        )
