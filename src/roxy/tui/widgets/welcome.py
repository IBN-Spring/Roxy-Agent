"""Welcome panel for the Roxy chat TUI — v1.0 product-style."""

from __future__ import annotations

from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widget import Widget

from roxy import __version__


class WelcomePanel(Widget):
    """Product landing screen. Tells you what Roxy is and what to do next."""

    DEFAULT_CSS = """
    WelcomePanel {
        width: 100%;
        height: auto;
        padding: 1 2 0 2;
    }
    """

    def __init__(
        self,
        model: str,
        session_id: str,
        workspace: Path,
        has_api_key: bool = False,
        evolution_status: str = "",
        kb_entries: int = 0,
        channels_count: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model = model
        self.session_id = session_id
        self.workspace = workspace
        self.has_api_key = has_api_key
        self.evolution_status = evolution_status
        self.kb_entries = kb_entries
        self.channels_count = channels_count

    def render(self) -> Panel:
        # ── Title block ──────────────────────────────────────
        title = Text("Roxy", style="bold cyan")
        title.append("  ", style="")
        title.append("source-level self-evolving agent", style="dim italic")

        # ── Status bar ───────────────────────────────────────
        status = Table.grid(padding=(0, 2))
        status.add_column()
        status.add_column()
        status.add_column()
        status.add_column()

        model_short = self.model.split("/")[-1] if "/" in self.model else (self.model or "—")
        key_icon = "[green]●[/green]" if self.has_api_key else "[yellow]○[/yellow]"
        kb_str = f"{self.kb_entries} entries" if self.kb_entries else "empty"
        ch_str = f"{self.channels_count} channels" if self.channels_count else "—"

        status.add_row(
            Text(f"{key_icon} Model: {model_short}", style=""),
            Text(f"Session: {self.session_id[:8]}", style="dim"),
            Text(f"KB: {kb_str}", style="dim"),
            Text(f"Channels: {ch_str}", style="dim"),
        )

        # ── Tips ─────────────────────────────────────────────
        tips = Table.grid(padding=(0, 1))
        tips.add_column(style="cyan", width=16)
        tips.add_column(style="dim")
        tips.add_row("/status", "Runtime dashboard")
        tips.add_row("/evolve", "Source evolution pipeline")
        tips.add_row("/kb <query>", "Search knowledge base")
        tips.add_row("/help", "Command palette")

        # ── No key warning ───────────────────────────────────
        warning = Text()
        if not self.has_api_key:
            provider = self.model.split("/")[0] if "/" in self.model else "openai"
            warning.append("\n", style="")
            warning.append("╔══════════════════════════╗\n", style="yellow")
            warning.append("║  No API key configured  ║\n", style="bold yellow")
            warning.append("╚══════════════════════════╝\n", style="yellow")
            warning.append(f"Configure: roxy config set models.providers.{provider}.api_key \"<key>\"\n", style="cyan")
            warning.append(f"Or: export {provider.upper()}_API_KEY=\"<key>\"\n", style="cyan")

        # ── Assembly ─────────────────────────────────────────
        content = Table.grid(padding=(1, 0))
        content.add_row(title)
        content.add_row(Text("Roxy sees failure → proposes fixes → patches itself → tests → waits for you to confirm.", style="dim"))
        content.add_row("")
        content.add_row(status)
        if warning.plain:
            content.add_row(warning)
        content.add_row("")
        content.add_row(tips)

        subtitle = "type a message or /help"
        if not self.has_api_key:
            subtitle = "⚠ no API key — /key for setup"

        return Panel(
            content,
            title=f"Roxy Agent v{__version__}",
            subtitle=subtitle,
            border_style="yellow" if not self.has_api_key else "cyan",
            padding=(1, 2),
        )
