""""roxy evolve" — source-level controlled evolution."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group("evolve")
def evolve_cmd() -> None:
    """Source-level controlled evolution.

    \b
    Observe system health, generate improvement proposals, and manage
    the evolution pipeline. All changes require human confirmation.
    """
    pass


@evolve_cmd.command("observe")
@click.option("--from-eval", default="", help="Path to eval report for evidence.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def evolve_observe(from_eval: str, as_json: bool) -> None:
    """Scan for improvement opportunities across traces, eval, channels."""
    from roxy.evolution.planner import EvolutionPlanner

    if from_eval:
        from pathlib import Path
        if not Path(from_eval).exists():
            console.print(f"[red]Eval report not found: {from_eval}[/red]")
            raise SystemExit(1)

    planner = EvolutionPlanner()
    findings = planner.observe(from_eval=from_eval)

    if as_json:
        import json
        click.echo(json.dumps(findings, indent=2, ensure_ascii=False))
        return

    if not findings:
        console.print("[green]✓[/green] No issues found — system looks healthy.")
        return

    console.print(f"\n[bold]Observations[/bold] — {len(findings)} finding(s)\n")
    for f in findings:
        sev = f["severity"]
        icon = {"high": "[red]●[/red]", "medium": "[yellow]●[/yellow]", "low": "[dim]●[/dim]"}.get(sev, "●")
        console.print(f"  {icon} [{sev}] {f['source']}: {f['detail'][:120]}")
    console.print()


@evolve_cmd.command("propose")
@click.option("--target", "-t", required=True, help="Target: context-compaction, tool-descriptions, system-prompt.")
@click.option("--from-eval", default="", help="Path to eval report for evidence.")
def evolve_propose(target: str, from_eval: str) -> None:
    """Generate a source-level evolution proposal.

    \b
    Targets:
      context-compaction  Micro-compact / auto-compact thresholds
      tool-descriptions   Tool descriptions for model routing
      system-prompt       System prompt response quality
    """
    from roxy.evolution.planner import EvolutionPlanner

    valid = {"context-compaction", "tool-descriptions", "system-prompt"}
    if target not in valid:
        console.print(f"[yellow]Unknown target: '{target}'[/yellow]")
        console.print(f"Valid targets: {', '.join(sorted(valid))}")
        return

    if from_eval:
        from pathlib import Path
        if not Path(from_eval).exists():
            console.print(f"[red]Eval report not found: {from_eval}[/red]")
            raise SystemExit(1)

    planner = EvolutionPlanner()
    try:
        proposal = planner.propose(target, from_eval=from_eval)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    if proposal is None:
        console.print(f"[yellow]Could not generate proposal for '{target}'.[/yellow]")
        return

    console.print()
    console.print(Panel(proposal.to_markdown(), title=f"Proposal: {proposal.id}", border_style="cyan"))
    console.print()
    console.print(f"[green]✓[/green] Proposal saved → [cyan]{proposal.id}[/cyan]")
    console.print(f"View all: [cyan]roxy evolve proposals list[/cyan]")


@evolve_cmd.group("proposals")
def evolve_proposals() -> None:
    """Manage evolution proposals."""
    pass


@evolve_proposals.command("list")
def proposals_list() -> None:
    """List all proposals."""
    from roxy.evolution.planner import EvolutionPlanner

    planner = EvolutionPlanner()
    proposals = planner.list_proposals()

    if not proposals:
        console.print("[dim]No proposals yet. Create one: roxy evolve propose --target context-compaction[/dim]")
        return

    table = Table(title="Evolution Proposals")
    table.add_column("ID", style="cyan")
    table.add_column("Target")
    table.add_column("Status")
    table.add_column("Risk")
    table.add_column("Created")

    for p in proposals:
        status_style = {"draft": "yellow", "patched": "cyan", "tested": "green", "merged": "bold green", "rejected": "red"}
        status = f"[{status_style.get(p.status, 'dim')}]{p.status}[/{status_style.get(p.status, 'dim')}]"
        table.add_row(p.id[:20], p.target, status, p.risk, p.created_at[:10])

    console.print(table)
    console.print(f"\n[dim]{len(proposals)} proposal(s)[/dim]")


@evolve_proposals.command("show")
@click.argument("proposal_id")
def proposals_show(proposal_id: str) -> None:
    """Show a proposal in detail."""
    from roxy.evolution.planner import EvolutionPlanner

    planner = EvolutionPlanner()
    try:
        proposal = planner.show_proposal(proposal_id)
    except ValueError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        return

    if proposal is None:
        console.print(f"[yellow]Proposal not found: '{proposal_id}'[/yellow]")
        return

    console.print()
    console.print(Panel(proposal.to_markdown(), title=f"Proposal: {proposal.id}", border_style="cyan"))
    console.print()
