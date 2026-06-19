""""roxy doctor" — health check command."""

import click
from rich.console import Console
from rich.table import Table

from roxy.config.loader import Config
from roxy.models.health import ProviderHealth

console = Console()


@click.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed probe results.")
def doctor_cmd(as_json: bool, verbose: bool) -> None:
    """Check the health of your Roxy installation.

    Verifies configuration, provider connectivity, and workspace state.
    """
    cfg = Config()
    cfg.load()

    if as_json:
        _doctor_json(cfg, verbose)
    else:
        _doctor_rich(cfg, verbose)


def _doctor_rich(cfg: Config, verbose: bool) -> None:
    """Print a Rich-formatted health report."""
    console.print()
    console.print("[bold]Roxy Doctor Report[/bold]", highlight=False)
    console.print()

    # ── Config ──────────────────────────────────────────────────
    config_path = cfg._path
    if config_path.exists():
        console.print(f"[green]✓[/green] Config found at {config_path}")
    else:
        console.print(f"[yellow]![/yellow] No config found. Run [cyan]roxy init[/cyan] first.")
        return

    # ── User profile ─────────────────────────────────────────────
    console.print()
    console.print("[bold]User Profile:[/bold]")
    name = cfg.get("user.name")
    identity = cfg.get("user.identity")
    domain = cfg.get("user.research_domain")
    topics = cfg.get("user.topics", [])

    if name:
        console.print(f"  Name:             {name}")
    else:
        console.print("  [yellow]Name: not set[/yellow]")
    if identity:
        console.print(f"  Identity:         {identity}")
    if domain:
        console.print(f"  Research domain:  {domain}")
    if topics:
        console.print(f"  Topics:           {', '.join(topics)}")

    # ── Workspace ────────────────────────────────────────────────
    workspace = cfg.get("workspace.path", "")
    console.print()
    console.print("[bold]Workspace:[/bold]")
    if workspace:
        import os
        wspath = os.path.expanduser(workspace)
        if os.path.isdir(wspath):
            console.print(f"[green]✓[/green] {wspath}")
        else:
            console.print(f"[yellow]![/yellow] {wspath} (directory does not exist)")
    else:
        console.print("[dim]  No workspace set (defaults to current directory)[/dim]")

    # ── Providers ────────────────────────────────────────────────
    console.print()
    health = ProviderHealth(cfg)
    results = health.check_all()
    console.print(health.format_report(results))

    # ── Tools ────────────────────────────────────────────────────
    console.print()
    console.print("[bold]Available Tools:[/bold]")
    try:
        from roxy.tools.registry import ToolRegistry
        from roxy.tools.builtin import ReadFileTool, WebFetchTool

        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(WebFetchTool())

        for t in registry.get_all():
            risk_style = {"safe": "green", "caution": "yellow", "dangerous": "red"}.get(t.risk_level.value, "dim")
            ws = "📁" if t.workspace_bounded else "🌐"
            console.print(f"  [{risk_style}]{t.name}[/{risk_style}] {ws} {t.description}")
    except Exception:
        console.print("  [dim]Tools not available (install roxy with all dependencies)[/dim]")

    # ── Summary ──────────────────────────────────────────────────
    console.print()
    ok_count = sum(1 for r in results.values() if r["status"] == "ok")
    warn_count = sum(1 for r in results.values() if r["status"] == "warn")
    total = len(results) if results else 1
    default_model = cfg.get("models.default", "not set")
    console.print(f"Default model: [cyan]{default_model}[/cyan]")
    console.print(f"Providers: {ok_count} ok, {warn_count} warn, {total - ok_count - warn_count} error")
    console.print()

    if ok_count == 0 and warn_count == 0:
        console.print("[yellow]No providers configured. Run [cyan]roxy init[/cyan] to set up.[/yellow]")
    elif ok_count > 0:
        console.print("[green]Ready to chat! Run [cyan]roxy chat[/cyan] (Phase 1).[/green]")
    else:
        console.print("[yellow]Providers configured but keys may be missing.[/yellow]")
        console.print("Set a key: [cyan]roxy config set models.providers.<name>.api_key <key>[/cyan]")


def _doctor_json(cfg: Config, verbose: bool) -> None:
    """Print JSON health report."""
    import json

    health = ProviderHealth(cfg)
    results = health.check_all()

    # Tool summary
    tools_info: list[dict] = []
    try:
        from roxy.tools.registry import ToolRegistry
        from roxy.tools.builtin import ReadFileTool, WebFetchTool
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(WebFetchTool())
        tools_info = registry.tool_summary()
    except Exception:
        pass

    report = {
        "config_path": str(cfg._path),
        "config_exists": cfg._path.exists(),
        "user": {
            "name": cfg.get("user.name"),
            "identity": cfg.get("user.identity"),
            "research_domain": cfg.get("user.research_domain"),
            "topics": cfg.get("user.topics"),
        },
        "default_model": cfg.get("models.default"),
        "providers": {k: v for k, v in results.items()},
        "tools": tools_info,
    }
    click.echo(json.dumps(report, indent=2, ensure_ascii=False))
