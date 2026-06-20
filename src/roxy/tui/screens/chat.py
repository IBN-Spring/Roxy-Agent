"""ChatScreen — main TUI chat interface with slash commands."""

from __future__ import annotations

import asyncio
import logging

from textual.screen import Screen
from textual.containers import VerticalScroll, Container
from textual.widgets import Static

from roxy import __version__
from roxy.config.loader import Config
from roxy.engine.query_engine import QueryEngine, TurnOutput
from roxy.engine.session import Session, SessionManager
from roxy.tui.widgets.input_area import InputArea
from roxy.tui.widgets.message import MessageWidget
from roxy.tui.widgets.status_bar import StatusBar
from roxy.tui.widgets.welcome import WelcomePanel

logger = logging.getLogger(__name__)

# ── slash commands ──────────────────────────────────────────────

HELP_TEXT = """\
[b]Slash Commands[/b]

  /help              Show this message
  /clear             Clear the screen (session kept)
  /doctor            Show provider, tools, channels, KB status
  /model             Show current model
  /model [name]      Switch model for this session
  /sessions          List recent sessions
  /resume [id]       Resume a previous session
  /exit              Exit Roxy

[b]Tips[/b]
  • Ask Roxy to search your knowledge base or read files
  • Add feeds with: roxy research feeds add "Name" "URL"
  • Collect updates: roxy research collect --all
  • Digest: roxy research digest --days 7
"""


class ChatScreen(Screen):
    """Main chat screen: message history + input + status bar."""

    DEFAULT_CSS = """
    ChatScreen {
        layout: vertical;
    }
    #chat-shell {
        height: 1fr;
        border: round $primary;
        margin: 0 1 1 1;
    }
    #message-list {
        height: 1fr;
        overflow-y: auto;
        padding: 0 1 1 1;
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

        self._mount_welcome()

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
        with Container(id="chat-shell"):
            yield Static("", id="welcome-slot")
            yield VerticalScroll(id="message-list")
            yield Static("", id="thinking-indicator")
            yield InputArea()
        yield StatusBar()

    # ── message handling ─────────────────────────────────────────

    def on_input_area_submit_message(self, event: InputArea.SubmitMessage) -> None:
        """Handle user submitting a message."""
        if self._streaming_task and not self._streaming_task.done():
            return  # Already processing

        user_text = event.text.strip()

        # ── Slash commands ────────────────────────────────────
        if user_text.startswith("/"):
            self._hide_welcome()
            self._add_message("user", user_text)
            response = self._handle_slash(user_text)
            self._add_message("status", response)
            self._update_status()
            return

        # Hide welcome panel on first message
        self._hide_welcome()

        self._add_message("user", user_text)
        self._update_status()

        # Start streaming in background
        self._streaming_task = asyncio.create_task(self._run_stream(user_text))

    # ── slash command dispatcher ─────────────────────────────────

    def _handle_slash(self, text: str) -> str:
        """Route a slash command to its handler. Returns formatted response."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/help": self._cmd_help,
            "/clear": self._cmd_clear,
            "/doctor": self._cmd_doctor,
            "/model": lambda a: self._cmd_model(a),
            "/sessions": self._cmd_sessions,
            "/resume": lambda a: self._cmd_resume(a),
            "/exit": self._cmd_exit,
        }

        handler = handlers.get(cmd)
        if handler:
            return handler(arg)
        return f"[yellow]Unknown command: {cmd}[/yellow]\nType /help to see available commands."

    # ── individual commands ──────────────────────────────────────

    def _cmd_help(self, _arg: str) -> str:
        return HELP_TEXT

    def _cmd_clear(self, _arg: str) -> str:
        """Clear all messages from the display (session intact)."""
        msg_list = self.query_one("#message-list", VerticalScroll)
        for child in list(msg_list.children):
            child.remove()
        return "[dim]Screen cleared. Session preserved.[/dim]"

    def _cmd_doctor(self, _arg: str) -> str:
        """Run a mini doctor check and return formatted status."""
        lines = ["[b]Roxy Status[/b]", ""]

        # Provider
        from roxy.models.health import ProviderHealth
        health = ProviderHealth(self.config)
        results = health.check_all()
        for name, info in sorted(results.items()):
            icon = "✓" if info["status"] == "ok" else "⚠" if info["status"] == "warn" else "✗"
            lines.append(f"  {icon} Provider [cyan]{name}[/cyan]: {info['message']}")

        # Model
        model = self._engine.provider.resolve_model(self.model_override) if self._engine else "—"
        lines.append(f"  → Model: [cyan]{model}[/cyan]")

        # Tools
        try:
            from roxy.tools.registry import ToolRegistry
            from roxy.tools.builtin import ReadFileTool, WebFetchTool, KnowledgeQueryTool
            reg = ToolRegistry()
            reg.register(ReadFileTool())
            reg.register(WebFetchTool())
            reg.register(KnowledgeQueryTool())
            tool_names = ", ".join(t.name for t in reg.get_all())
            lines.append(f"  → Tools: {tool_names}")
        except Exception:
            pass

        # KB
        try:
            from roxy.knowledge.store import KnowledgeStore
            ks = KnowledgeStore()
            ks.init_db()
            stats = ks.get_stats()
            lines.append(f"  → Knowledge: {stats['entry_count']} entries, {stats['tag_count']} tags")
        except Exception:
            lines.append("  → Knowledge: unavailable")

        # Sessions
        try:
            sm = SessionManager()
            sessions = sm.list_sessions(limit=5)
            lines.append(f"  → Sessions: {len(sessions)} saved (this: {self._engine.session_id[:8]}...)" if self._engine else "")
        except Exception:
            pass

        # Channels
        try:
            from roxy.research.channels import ALL_CHANNELS
            for ch in ALL_CHANNELS:
                lines.append(f"  → Channel [cyan]{ch.name}[/cyan]: tier {ch.tier}")
        except Exception:
            pass

        return "\n".join(lines)

    def _cmd_model(self, arg: str) -> str:
        """Show or switch the current model."""
        if not self._engine:
            return "[yellow]Engine not initialized.[/yellow]"

        current = self._engine.provider.resolve_model(self.model_override)

        if not arg:
            return f"Current model: [cyan]{current}[/cyan]\nSwitch: /model provider/model-name"

        # Switch model
        self.model_override = arg.strip()
        self._update_status()
        return f"Model switched: [cyan]{current}[/cyan] → [green]{self.model_override}[/green]"

    def _cmd_sessions(self, _arg: str) -> str:
        """List recent sessions."""
        sm = SessionManager()
        sessions = sm.list_sessions(limit=10)

        if not sessions:
            return "[dim]No saved sessions.[/dim]"

        lines = ["[b]Recent Sessions[/b]", ""]
        for s in sessions:
            date = s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "—"
            model_short = s.model.split("/")[-1] if "/" in s.model else (s.model or "—")
            marker = " ← current" if self._session and s.id == self._session.id else ""
            lines.append(f"  [cyan]{s.id[:8]}[/cyan] {date}  {model_short}  ({s.message_count} msgs){marker}")
        lines.append("")
        lines.append("Resume: /resume <id>")
        return "\n".join(lines)

    def _cmd_resume(self, arg: str) -> str:
        """Resume a previous session."""
        session_id = arg.strip()
        if not session_id:
            return "[yellow]Usage: /resume <session-id>[/yellow]\nUse /sessions to see available sessions."

        sm = SessionManager()
        session = sm.load(session_id)
        if session is None:
            # Try prefix match
            all_sessions = sm.list_sessions()
            matches = [s for s in all_sessions if s.id.startswith(session_id)]
            if len(matches) == 1:
                session = sm.load(matches[0].id)
            elif len(matches) > 1:
                return f"[yellow]Ambiguous prefix. Matches: {', '.join(s.id[:8] for s in matches)}[/yellow]"
            else:
                return f"[yellow]Session '{session_id}' not found.[/yellow]"

        if session is None:
            return f"[yellow]Session '{session_id}' not found.[/yellow]"

        # Rebuild engine with new session
        self._session = session
        self._engine = QueryEngine(self.config, self._session)
        self._current_assistant_msg = None

        # Clear and repopulate message list
        msg_list = self.query_one("#message-list", VerticalScroll)
        for child in list(msg_list.children):
            child.remove()
        for msg in self._session.messages:
            self._add_message(msg["role"], msg.get("content", ""))

        self._update_status()
        model = session.model or "—"
        return f"[green]Resumed session [cyan]{session.id[:8]}[/cyan] ({session.message_count} msgs, model: {model})[/green]"

    def _cmd_exit(self, _arg: str) -> str:
        """Schedule app exit."""
        self.app.exit()
        return ""

    # ── streaming ────────────────────────────────────────────────

    async def _run_stream(self, user_input: str) -> None:
        """Run the query engine and stream results to the TUI."""
        if not self._engine:
            return

        thinking = self.query_one("#thinking-indicator", Static)
        thinking.update("Thinking...")

        full_content = ""
        tool_calls_log: list[dict] = []

        try:
            async for output in self._engine.submit_message(user_input, self.model_override):
                if output.type == "chunk":
                    full_content += output.content
                    self._upsert_assistant_message(full_content)

                elif output.type == "tool_call":
                    calls = output.meta.get("calls", [])
                    thinking.update(f"🔧 Calling: {', '.join(calls)}")
                    tool_calls_log.append({"calls": calls, "results": []})

                elif output.type == "tool_result":
                    tool = output.meta.get("tool", "")
                    ok = output.meta.get("success", False)
                    icon = "✓" if ok else "✗"
                    thinking.update(f"  {icon} {tool}")
                    if tool_calls_log:
                        tool_calls_log[-1]["results"].append({
                            "tool": tool,
                            "success": ok,
                            "preview": output.content[:200].replace("\n", " "),
                        })

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

            if tool_calls_log:
                summary = self._format_tool_summary(tool_calls_log)
                self._add_message("status", summary)

            self._update_status()
            self._session = self._engine.session if self._engine else None

    # ── tool call display ─────────────────────────────────────────

    def _format_tool_summary(self, log: list[dict]) -> str:
        lines = []
        for batch in log:
            calls = batch.get("calls", [])
            results = batch.get("results", [])
            lines.append(f"🔧 Called: {', '.join(calls)}")
            for r in results:
                icon = "✓" if r["success"] else "✗"
                lines.append(f"  {icon} {r['tool']}: {r['preview'][:120]}")
        return "\n".join(lines)

    # ── message rendering helpers ────────────────────────────────

    def _mount_welcome(self) -> None:
        if not self._engine:
            return
        slot = self.query_one("#welcome-slot", Static)
        slot.update(
            WelcomePanel(
                model=self._engine.provider.resolve_model(self.model_override),
                session_id=self._engine.session_id,
                workspace=self._engine.workspace_root,
            ).render()
        )

    def _hide_welcome(self) -> None:
        slot = self.query_one("#welcome-slot", Static)
        slot.update("")

    def _add_message(self, role: str, content: str) -> MessageWidget:
        msg_list = self.query_one("#message-list", VerticalScroll)
        widget = MessageWidget(role, content)
        msg_list.mount(widget)
        msg_list.scroll_end(animate=False)
        return widget

    def _upsert_assistant_message(self, content: str) -> None:
        if self._current_assistant_msg is None:
            self._current_assistant_msg = self._add_message("assistant", content)
        else:
            self._current_assistant_msg.content = content
            self._current_assistant_msg.refresh()

    def _finalize_assistant_message(self, content: str) -> None:
        if self._current_assistant_msg and content.strip():
            self._current_assistant_msg.content = content
            self._current_assistant_msg.refresh()
        self._current_assistant_msg = None

    # ── status bar ───────────────────────────────────────────────

    def _update_status(self) -> None:
        if not self._engine:
            return
        try:
            bar = self.query_one(StatusBar)
            bar.update(
                model=self._engine.provider.resolve_model(self.model_override),
                session_id=self._engine.session_id,
                msg_count=self._engine.message_count,
            )
        except Exception:
            pass  # DOM not mounted (e.g. unit tests)
