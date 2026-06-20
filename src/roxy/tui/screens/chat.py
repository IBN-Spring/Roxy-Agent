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

# well-known env var mapping (duplicated from provider.py to avoid circular import)
_ENV_MAP = {
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "cohere": "COHERE_API_KEY",
}


def _KNOWN_ENV_FOR(provider: str) -> str:
    return _ENV_MAP.get(provider.lower(), "")

# ── slash commands ──────────────────────────────────────────────

HELP_TEXT = """\
[b]Chat Commands[/b]

  /help              Show this message
  /status            Master status overview
  /key               Show API key status + configure
  /clear             Clear the screen (session kept)
  /doctor            Show provider, tools, channels, KB status
  /model             Show current model
  /model [name]      Switch model for this session
  /sessions          List recent sessions
  /resume [id]       Resume a previous session
  /exit              Exit Roxy

[b]Research Commands[/b]

  /feeds             Show feed source status
  /collect           Collect from all enabled feeds
  /runs              Show recent collection runs
  /digest            Generate 7-day digest summary
  /digest 30         30-day digest
  /digest latest     Digest for latest collection run
  /kb [query]        Search the knowledge base
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
            "/key": self._cmd_key,
            "/clear": self._cmd_clear,
            "/doctor": self._cmd_doctor,
            "/model": lambda a: self._cmd_model(a),
            "/sessions": self._cmd_sessions,
            "/resume": lambda a: self._cmd_resume(a),
            "/exit": self._cmd_exit,
            "/status": self._cmd_status,
            "/feeds": self._cmd_feeds,
            "/collect": self._cmd_collect,
            "/runs": self._cmd_runs,
            "/digest": lambda a: self._cmd_digest(a),
            "/kb": lambda a: self._cmd_kb(a),
        }

        handler = handlers.get(cmd)
        if handler:
            return handler(arg)
        return f"[yellow]Unknown command: {cmd}[/yellow]\nType /help to see available commands."

    # ── individual commands ──────────────────────────────────────

    def _cmd_help(self, _arg: str) -> str:
        return HELP_TEXT

    def _cmd_key(self, _arg: str) -> str:
        """Show API key status and configuration instructions."""
        if not self._engine:
            return "[yellow]Engine not initialized.[/yellow]"

        model = self._engine.provider.resolve_model(self.model_override)
        provider = model.split("/")[0] if "/" in model else model
        has_key = self._engine.provider.has_api_key(model)
        key_src = self._engine.provider.get_key_source(model)

        lines = ["[b]API Key Status[/b]", ""]

        if has_key:
            src_label = "environment variable" if key_src == "env" else "config file"
            lines.append(f"  [green]✓[/green] API key configured for [cyan]{provider}[/cyan]")
            lines.append(f"  Source: {src_label}")
            lines.append(f"  Model:  [cyan]{model}[/cyan]")
        else:
            lines.append(f"  [yellow]⚠[/yellow] No API key for [cyan]{provider}[/cyan]")
            lines.append("")
            lines.append("[b]To configure:[/b]")
            lines.append(f"  [cyan]roxy config set models.providers.{provider}.api_key \"<your-key>\"[/cyan]")
            env_var = _KNOWN_ENV_FOR(provider)
            if env_var:
                lines.append(f"  or: [cyan]export {env_var}=\"<your-key>\"[/cyan]")

            lines.append("")
            lines.append("[b]Other providers:[/b]")
            lines.append("  [cyan]roxy config set models.providers.<name>.api_key \"<key>\"[/cyan]")
            lines.append("  [cyan]roxy config set models.default \"<provider>/<model>\"[/cyan]")

        return "\n".join(lines)

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

    # ── research commands ───────────────────────────────────────

    def _cmd_feeds(self, _arg: str) -> str:
        """Show feed source status."""
        try:
            from roxy.research.source_manager import SourceManager
            sm = SourceManager(self.config)
            summary = sm.get_status_summary()
            if summary["total"] == 0:
                return (
                    "[b]Feed Sources[/b]\n\n"
                    "[dim]No feeds configured yet.[/dim]\n\n"
                    "To add a feed:\n"
                    "  [cyan]roxy research feeds add \"Name\" \"URL\"[/cyan]\n"
                    "Then: /collect"
                )

            lines = [f"[b]Feed Sources[/b] ({summary['enabled']} on, {summary['disabled']} off)", ""]
            for f in summary["feeds"]:
                if f["enabled"]:
                    icon = "[green]✓[/green]"
                else:
                    icon = "[dim]○[/dim]"

                err = ""
                if f.get("last_error"):
                    err = f"\n         [red]⚠ {f['last_error'][:80]}[/red]"

                last = f["last_run_at"][:16] if f.get("last_run_at") else "never"
                total = f["total_collected"]
                lines.append(f"  {icon} [cyan]{f['name']}[/cyan] | last: {last} | total: {total}{err}")

            # Show disabled hint
            if summary["disabled"] > 0:
                lines.append("")
                lines.append(f"[dim]{summary['disabled']} feed(s) disabled. Enable: /feeds, then roxy research feeds enable <name>[/dim]")

            if summary["with_errors"] > 0:
                lines.append(f"[yellow]{summary['with_errors']} feed(s) have errors. Check details with roxy research feeds status.[/yellow]")

            lines.append("")
            lines.append("Actions: /collect  |  /runs  |  /digest")
            return "\n".join(lines)
        except Exception as exc:
            return f"[red]Error loading feeds: {exc}[/red]"

    def _cmd_collect(self, _arg: str) -> str:
        """Collect from all enabled feeds."""
        import asyncio as _asyncio
        try:
            from roxy.research.source_manager import SourceManager
            from roxy.research.collector import ContentCollector
            sm = SourceManager(self.config)
            all_feeds = sm.list_feeds()
            feeds = sm.list_feeds(enabled_only=True)

            if not all_feeds:
                return (
                    "[b]Collection[/b]\n\n"
                    "[yellow]No feeds configured.[/yellow]\n\n"
                    "To add a feed:\n"
                    "  [cyan]roxy research feeds add \"Name\" \"URL\"[/cyan]\n"
                    "Then: /collect"
                )

            if not feeds:
                disabled = len(all_feeds)
                names = ", ".join(f"[cyan]{f.name}[/cyan]" for f in all_feeds[:5])
                return (
                    f"[b]Collection[/b]\n\n"
                    f"[yellow]All {disabled} feed(s) are disabled.[/yellow]\n\n"
                    f"Disabled: {names}\n\n"
                    "To enable:\n"
                    "  [cyan]roxy research feeds enable \"<name>\"[/cyan]\n"
                    "Then: /collect"
                )

            collector = ContentCollector(self.config)
            result = _asyncio.run(collector.collect_feeds(feeds))

            lines = [f"[b]Collection Complete[/b]", ""]
            lines.append(f"  Run: [cyan]{result['run_id'][:8]}[/cyan]  |  Feeds: {result['feeds_processed']}")
            lines.append(f"  New: [green]{result['total_new']}[/green]  |  Duplicates: {result['total_dup']}")
            if result.get("errors"):
                lines.append(f"  Errors: [red]{len(result['errors'])}[/red]")
            lines.append("")

            for r in result["results"]:
                if "error" in r:
                    icon = "[red]✗[/red]"
                    detail = f" — [red]{r['error'][:60]}[/red]"
                else:
                    icon = "[green]✓[/green]"
                    detail = f" — {r['items_new']} new, {r['items_duplicate']} dup"
                lines.append(f"  {icon} [cyan]{r['feed']}[/cyan]{detail}")

            # Per-error fix suggestions
            errors = result.get("errors", [])
            if errors:
                lines.append("")
                lines.append("[b]Fix suggestions:[/b]")
                for err in errors:
                    err_lower = err.lower()
                    if "refused" in err_lower or "connect" in err_lower:
                        lines.append(f"  [yellow]• Network error — check the URL or try again later[/yellow]")
                    elif "not found" in err_lower or "404" in err_lower:
                        lines.append(f"  [yellow]• Feed URL may be invalid — check with roxy research feeds status[/yellow]")
                    elif "timeout" in err_lower:
                        lines.append(f"  [yellow]• Feed timed out — the server may be slow, try again[/yellow]")
                    else:
                        lines.append(f"  [yellow]• {err[:100]}[/yellow]")

            lines.append("")
            lines.append("Next: /runs  |  /digest latest  |  /kb <topic>")
            return "\n".join(lines)
        except Exception as exc:
            return (
                f"[red]Collection failed: {exc}[/red]\n\n"
                "Check: /feeds  |  roxy doctor  |  network connection"
            )

    def _cmd_runs(self, _arg: str) -> str:
        """Show recent collection runs."""
        try:
            from roxy.research.run_history import RunHistory
            rh = RunHistory()
            runs = rh.list_runs(limit=8)
            if not runs:
                return (
                    "[b]Collection Runs[/b]\n\n"
                    "[dim]No runs yet.[/dim]\n\n"
                    "To collect: /collect\n"
                    "To add feeds: roxy research feeds add \"Name\" \"URL\""
                )

            lines = ["[b]Recent Runs[/b]", ""]
            for r in runs:
                started = r["started_at"][:16] if r["started_at"] else "—"
                err = f" [red]{r['error_count']} err[/red]" if r["error_count"] else ""
                lines.append(f"  [cyan]{r['run_id'][:8]}[/cyan] {started} — "
                             f"{r['feed_count']} feeds, [green]{r['total_new']} new[/green]{err}")
            lines.append("")
            lines.append("Details: /digest latest  |  /digest <id>")
            return "\n".join(lines)
        except Exception as exc:
            return f"[red]Error loading runs: {exc}[/red]"

    def _cmd_digest(self, arg: str) -> str:
        """Generate a digest summary inline."""
        try:
            from roxy.research.digest import ResearchDigest
            from roxy.research.run_history import RunHistory

            dg = ResearchDigest()
            run_id = None
            days = 7

            arg = arg.strip()
            if arg.lower() == "latest":
                rh = RunHistory()
                latest = rh.latest_run()
                if latest:
                    run_id = latest["run_id"]
                else:
                    return (
                        "[b]Digest[/b]\n\n"
                        "[yellow]No collection runs found.[/yellow]\n\n"
                        "Try:\n"
                        "  /collect          Run collection first\n"
                        "  /digest 7         Show last 7 days\n"
                        "  roxy research collect --all"
                    )
            elif arg.isdigit():
                days = min(int(arg), 365)
            elif len(arg) >= 6:
                run_id = arg

            result = dg.generate(days=days, run_id=run_id, group_by="source")

            if result["entry_count"] == 0:
                suggestions = [
                    "[b]Digest[/b]",
                    "",
                    f"[yellow]No entries found for {result['period']}.[/yellow]",
                    "",
                    "To get started:",
                    "  1. Add a feed:  [cyan]roxy research feeds add \"Name\" \"URL\"[/cyan]",
                    "  2. Collect:     [cyan]/collect[/cyan]",
                    "  3. Try again:   [cyan]/digest[/cyan]",
                ]
                if run_id:
                    suggestions.append(f"\n[dim]Run {run_id[:8]} exists but produced no new entries (all duplicates).[/dim]")
                return "\n".join(suggestions)

            lines = [f"[b]Research Digest[/b] — {result['period']}", ""]
            lines.append(f"  Entries: {result['entry_count']}  |  Sources: {len(result['groups'])}")

            for name, group in sorted(result["groups"].items()):
                count = group["count"]
                lines.append(f"  [cyan]{name}[/cyan] ({count})")
                for entry in group["entries"][:3]:
                    title = entry.get("title", "(untitled)")
                    lines.append(f"    - {title}")

            lines.append("")
            lines.append("Full report: roxy research digest --out digest.md")
            return "\n".join(lines)
        except Exception as exc:
            return f"[red]Digest failed: {exc}[/red]"

    def _cmd_kb(self, arg: str) -> str:
        """Search the knowledge base."""
        query = arg.strip()
        if not query:
            return "[yellow]Usage: /kb <query>[/yellow]\nExample: /kb protein folding"

        try:
            from roxy.knowledge.store import KnowledgeStore
            from roxy.knowledge.query import KnowledgeQuery
            store = KnowledgeStore()
            store.init_db()
            q = KnowledgeQuery(store)
            results = q.search(query, limit=8)

            if not results:
                stats = store.get_stats()
                if stats["entry_count"] == 0:
                    return (
                        f"[b]KB Search: '{query}'[/b]\n\n"
                        "[dim]Knowledge base is empty.[/dim]\n\n"
                        "To get started:\n"
                        "  1. Add a feed:  [cyan]roxy research feeds add \"Name\" \"URL\"[/cyan]\n"
                        "  2. Collect:     [cyan]/collect[/cyan]\n"
                        "  3. Then:        [cyan]/kb {query}[/cyan]"
                    )
                return (
                    f"[b]KB Search: '{query}'[/b]\n\n"
                    f"[dim]No results found. {stats['entry_count']} entries exist with different keywords.[/dim]\n\n"
                    "Try:\n"
                    "  • Different keywords\n"
                    "  • /digest to browse all recent entries\n"
                    "  • roxy knowledge search \"{query}\" for more results"
                )

            lines = [f"[b]KB Search: '{query}'[/b] ({len(results)} results)", ""]
            for i, e in enumerate(results, 1):
                date = e.published_at[:10] if e.published_at else "—"
                src = e.collected_via or "—"
                lines.append(f"  {i}. [cyan]{e.title}[/cyan] ({date}, {src})")
                if e.canonical_url:
                    lines.append(f"     [dim]{e.canonical_url}[/dim]")
            return "\n".join(lines)
        except Exception as exc:
            return f"[red]KB search failed: {exc}[/red]"

    def _cmd_status(self, _arg: str) -> str:
        """Unified status overview."""
        lines = ["[b]Roxy Status[/b]", ""]

        # Model
        if self._engine:
            model = self._engine.provider.resolve_model(self.model_override)
            provider = model.split("/")[0] if "/" in model else model
            try:
                has_key = self._engine.provider.has_api_key(model)
            except Exception:
                has_key = True  # Assume OK if we can't check (tests)
            key_icon = "[green]✓[/green]" if has_key else "[yellow]⚠[/yellow]"
            lines.append(f"[b]Model[/b]")
            lines.append(f"  {key_icon} [cyan]{model}[/cyan] (provider: {provider})")
            if not has_key:
                lines.append(f"  [dim]Configure: /key[/dim]")
            lines.append("")

        # Feeds
        try:
            from roxy.research.source_manager import SourceManager
            sm = SourceManager(self.config)
            s = sm.get_status_summary()
            lines.append(f"[b]Feeds[/b]")
            lines.append(f"  Total: {s['total']} | Enabled: [green]{s['enabled']}[/green] | Disabled: {s['disabled']}")
            if s['with_errors']:
                lines.append(f"  With errors: [red]{s['with_errors']}[/red]")
            if s['never_run']:
                lines.append(f"  Never run: [yellow]{s['never_run']}[/yellow]")
            if s['total'] == 0:
                lines.append(f"  [dim]Add: roxy research feeds add \"Name\" \"URL\"[/dim]")
            lines.append("")
        except Exception:
            pass

        # KB
        try:
            from roxy.knowledge.store import KnowledgeStore
            ks = KnowledgeStore()
            ks.init_db()
            stats = ks.get_stats()
            lines.append(f"[b]Knowledge Base[/b]")
            lines.append(f"  Entries: {stats['entry_count']} | Tags: {stats['tag_count']}")
            if stats['entry_count'] == 0:
                lines.append(f"  [dim]Empty — /collect first, then /kb <topic>[/dim]")
            if stats['latest_entry']:
                lines.append(f"  Latest: [dim]{stats['latest_entry'].get('title', '—')[:60]}[/dim]")
            lines.append("")
        except Exception:
            pass

        # Last Run
        try:
            from roxy.research.run_history import RunHistory
            rh = RunHistory()
            last = rh.latest_run()
            lines.append(f"[b]Last Run[/b]")
            if last:
                started = last["started_at"][:16] if last["started_at"] else "—"
                err_str = f" [red]{last['error_count']} errors[/red]" if last["error_count"] else ""
                lines.append(f"  [cyan]{last['run_id'][:8]}[/cyan] {started} — "
                             f"{last['feed_count']} feeds, [green]{last['total_new']} new[/green]{err_str}")
            else:
                lines.append(f"  [dim]No runs yet — /collect[/dim]")
            lines.append("")
        except Exception:
            pass

        # Workspace
        if self._engine:
            try:
                ws = self._engine.workspace_root
                lines.append(f"[b]Workspace[/b]")
                lines.append(f"  [dim]{ws}[/dim]")
                lines.append("")
            except Exception:
                pass

        lines.append("[dim]Commands: /feeds  /collect  /runs  /digest  /kb[/dim]")
        return "\n".join(lines)

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
        model = self._engine.provider.resolve_model(self.model_override)
        has_key = self._engine.provider.has_api_key(model)
        key_src = self._engine.provider.get_key_source(model)
        slot = self.query_one("#welcome-slot", Static)
        slot.update(
            WelcomePanel(
                model=model,
                session_id=self._engine.session_id,
                workspace=self._engine.workspace_root,
                has_api_key=has_key,
                key_source=key_src,
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
