""""roxy init" — first-time setup wizard."""

from typing import Any

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from roxy.config.loader import Config


console = Console()


@click.command("init")
@click.option("--force", is_flag=True, help="Re-initialize even if already configured.")
def init_cmd(force: bool) -> None:
    """Interactive first-time setup wizard.

    Asks for your name, identity, research domain, topics, info sources,
    and preferred LLM provider — then writes ~/.roxy/config.yaml.
    """
    cfg = Config()
    cfg.load()

    already_configured = cfg.is_configured("user")
    if already_configured and not force:
        name = cfg.get("user.name")
        console.print(f"[yellow]Already configured for '{name}'.[/yellow]")
        if not Confirm.ask("Re-run setup?", default=False):
            return

    console.print()
    console.print("[bold cyan]╔══════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║       Welcome to Roxy Setup!        ║[/bold cyan]")
    console.print("[bold cyan]╚══════════════════════════════════════╝[/bold cyan]")
    console.print()
    console.print("I'll ask a few questions to set up your research profile.")
    console.print("[dim](Press Enter to skip any question)[/dim]")
    console.print()

    # ── User profile ────────────────────────────────────────────

    name = Prompt.ask("  What should I call you?", default=cfg.get("user.name", ""))
    if name:
        cfg.set("user.name", name)

    identity = Prompt.ask(
        "  What's your role / profession?",
        default=cfg.get("user.identity", ""),
    )
    if identity:
        cfg.set("user.identity", identity)

    domain = Prompt.ask(
        "  What's your primary research domain?",
        default=cfg.get("user.research_domain", ""),
    )
    if domain:
        cfg.set("user.research_domain", domain)

    # ── Topics ──────────────────────────────────────────────────

    existing_topics: list = cfg.get("user.topics", [])
    topics_str = Prompt.ask(
        "  Research topics (comma-separated)",
        default=", ".join(existing_topics) if existing_topics else "",
    )
    if topics_str.strip():
        cfg.set("user.topics", [t.strip() for t in topics_str.split(",") if t.strip()])

    # ── Info sources ────────────────────────────────────────────

    existing_sources: list = cfg.get("user.info_sources", [])
    console.print("  [dim]Info sources — RSS feeds, websites, etc. (comma-separated)[/dim]")
    sources_str = Prompt.ask(
        "  Information sources",
        default=", ".join(existing_sources) if existing_sources else "",
    )
    if sources_str.strip():
        cfg.set("user.info_sources", [s.strip() for s in sources_str.split(",") if s.strip()])

    # ── LLM provider ────────────────────────────────────────────

    console.print()
    console.print("[bold]LLM Provider Setup[/bold]")
    console.print("[dim]You can add more providers later via `roxy config set models.providers.<name>.api_key <key>`[/dim]")

    add_provider = Confirm.ask("  Configure a model provider now?", default=True)
    if add_provider:
        provider_name = Prompt.ask("  Provider name", default="openai")
        provider_key_map: dict[str, Any] = cfg.get(f"models.providers.{provider_name}", {}) or {}
        api_key = Prompt.ask(f"  API key for '{provider_name}'", default=provider_key_map.get("api_key", ""), password=True)
        if api_key:
            cfg.set(f"models.providers.{provider_name}.api_key", api_key)

        base_url = Prompt.ask(
            f"  Base URL (optional, press Enter for default)",
            default=provider_key_map.get("base_url", ""),
        )
        if base_url:
            cfg.set(f"models.providers.{provider_name}.base_url", base_url)

        model = Prompt.ask(
            "  Default model",
            default=cfg.get("models.default", f"{provider_name}/gpt-4.1-mini"),
        )
        cfg.set("models.default", model)

    # ── Save ─────────────────────────────────────────────────────

    console.print()
    cfg.save()
    console.print(f"[green]✓ Configuration saved to {cfg._path}[/green]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  [cyan]roxy doctor[/cyan]   Check everything is working")
    console.print(f"  [cyan]roxy chat[/cyan]     Start chatting (Phase 1)")
    console.print()
