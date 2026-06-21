""""roxy evolve" — source-level controlled evolution."""

import json
import re
from pathlib import Path

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


# ── v0.7+: observe, propose, proposals ──────────────────────────

@evolve_cmd.command("observe")
@click.option("--from-eval", default="", help="Path to eval report for evidence.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def evolve_observe(from_eval: str, as_json: bool) -> None:
    """Scan for improvement opportunities across traces, eval, channels."""
    from roxy.evolution.planner import EvolutionPlanner
    if from_eval:
        if not Path(from_eval).exists():
            console.print(f"[red]Eval report not found: {from_eval}[/red]")
            raise SystemExit(1)
    planner = EvolutionPlanner()
    findings = planner.observe(from_eval=from_eval)
    if as_json:
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
    """Generate a source-level evolution proposal."""
    from roxy.evolution.planner import EvolutionPlanner
    valid = {"context-compaction", "tool-descriptions", "system-prompt"}
    if target not in valid:
        console.print(f"[yellow]Unknown target: '{target}'[/yellow]")
        console.print(f"Valid targets: {', '.join(sorted(valid))}")
        return
    if from_eval and not Path(from_eval).exists():
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


# ── v0.8: Sandboxed Patch Pipeline ──────────────────────────────

def _load_proposal(proposal_id: str):
    from roxy.evolution.planner import EvolutionPlanner
    planner = EvolutionPlanner()
    try:
        proposal = planner.show_proposal(proposal_id)
    except ValueError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise SystemExit(1)
    if proposal is None:
        console.print(f"[yellow]Proposal not found: '{proposal_id}'[/yellow]")
        raise SystemExit(1)
    return proposal


@evolve_cmd.group("patch")
def evolve_patch() -> None:
    """Sandboxed patch operations (isolated git branches, never main)."""
    pass


@evolve_patch.command("prepare")
@click.argument("proposal_id")
@click.option("--force", is_flag=True, help="Overwrite existing evolution branch.")
def patch_prepare(proposal_id: str, force: bool) -> None:
    """Create an isolated git branch for a proposal. Must be on main branch."""
    proposal = _load_proposal(proposal_id)
    from roxy.evolution.workspace import EvolutionWorkspace
    ws = EvolutionWorkspace()
    info = ws.status()
    if not info.is_clean:
        console.print("[yellow]Working tree not clean. Commit or stash first.[/yellow]")
        raise SystemExit(1)
    try:
        branch = ws.prepare(proposal.id, force=force)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)
    proposal.branch = branch
    proposal.patch_status = "prepared"
    proposal.status = "patched"
    from roxy.evolution.planner import EvolutionPlanner
    EvolutionPlanner().store.save(proposal)
    console.print(f"[green]✓[/green] Branch created: [cyan]{branch}[/cyan]")
    console.print(f"Next: roxy evolve patch apply {proposal.id[:20]}")


@evolve_patch.command("apply")
@click.argument("proposal_id")
def patch_apply(proposal_id: str) -> None:
    """Apply deterministic patch on the proposal's branch."""
    proposal = _load_proposal(proposal_id)
    from roxy.evolution.workspace import EvolutionWorkspace
    from roxy.evolution.patcher import EvolutionPatcher
    ws = EvolutionWorkspace()
    patcher = EvolutionPatcher(ws)
    info = ws.status()
    expected = f"evolve/{proposal.id}"
    if info.current_branch != expected:
        console.print(f"[yellow]Expected branch '{expected}', on '{info.current_branch}'. Run patch prepare first.[/yellow]")
        raise SystemExit(1)
    result = patcher.apply(proposal)
    if not result["success"]:
        console.print(f"[red]✗ Patch failed: {result.get('error', '?')}[/red]")
        raise SystemExit(1)
    proposal.patch_status = "applied"
    from roxy.evolution.planner import EvolutionPlanner
    EvolutionPlanner().store.save(proposal)
    console.print(f"[green]✓[/green] {len(result['files_changed'])} file(s) changed")
    for f in result["files_changed"]:
        console.print(f"  [cyan]{f}[/cyan]")
    console.print(f"Next: roxy evolve test {proposal.id[:20]}")


@evolve_cmd.command("test")
@click.argument("proposal_id")
def evolve_test(proposal_id: str) -> None:
    """Run test commands from the proposal on its branch."""
    proposal = _load_proposal(proposal_id)
    from roxy.evolution.runner import EvolutionRunner
    runner = EvolutionRunner()
    report = runner.run(proposal)
    proposal.test_status = "passed" if report.all_passed else "failed"
    from roxy.evolution.planner import EvolutionPlanner
    EvolutionPlanner().store.save(proposal)
    console.print(f"\n[bold]Test Results[/bold] — {proposal.id[:20]}")
    for tr in report.results:
        icon = "[green]✓[/green]" if tr.passed else "[red]✗[/red]"
        console.print(f"  {icon} `{tr.command}` (exit {tr.exit_code})")
    console.print()
    if report.all_passed:
        console.print("[green]All tests passed.[/green]")
        console.print(f"Next: roxy evolve review {proposal.id[:20]}")
    else:
        console.print("[red]Some tests failed.[/red]")


@evolve_cmd.command("review")
@click.argument("proposal_id")
def evolve_review(proposal_id: str) -> None:
    """Generate patch review report with diff, tests, eval compare."""
    proposal = _load_proposal(proposal_id)
    from roxy.evolution.workspace import EvolutionWorkspace
    from roxy.evolution.runner import EvolutionRunner
    from roxy.evolution.reviewer import EvolutionReviewer
    ws = EvolutionWorkspace()
    diff = ws.get_diff(proposal.id)
    changed = ws.get_changed_files(proposal.id)
    runner = EvolutionRunner()
    test_report = runner.run(proposal)
    eval_compare = None
    try:
        from roxy.evolution.eval_runner import compare_reports
        if Path("baseline.json").exists() and Path("candidate.json").exists():
            with open("baseline.json") as f:
                base = json.load(f)
            with open("candidate.json") as f:
                cand = json.load(f)
            eval_compare = compare_reports(base, cand)
    except Exception:
        pass
    reviewer = EvolutionReviewer()
    report_md = reviewer.generate(
        proposal, {"files_changed": changed, "success": True},
        test_report, diff, eval_compare,
    )
    proposal.report_path = str(reviewer.run_dir(proposal.id) / "report.md")
    proposal.test_status = "passed" if test_report.all_passed else "failed"
    from roxy.evolution.planner import EvolutionPlanner
    EvolutionPlanner().store.save(proposal)
    console.print()
    console.print(f"[green]✓[/green] Report saved → [cyan]{proposal.report_path}[/cyan]")
    console.print(f"Next: roxy evolve merge {proposal.id[:20]} --confirm")


@evolve_cmd.command("merge")
@click.argument("proposal_id")
@click.option("--confirm", is_flag=True, help="Actually merge. Without --confirm, dry-run only.")
def evolve_merge(proposal_id: str, confirm: bool) -> None:
    """Merge evolution branch into main. Requires --confirm and safety gates."""
    proposal = _load_proposal(proposal_id)
    if not confirm:
        console.print(f"[dim]Dry-run: would merge 'evolve/{proposal.id}' into main.[/dim]")
        console.print("[dim]Use --confirm to actually merge.[/dim]")
        console.print(f"  Rollback: git checkout main && git branch -D evolve/{proposal.id}")
        return

    # ── Safety gates ──────────────────────────────────────
    failures = []

    # Gate 1: patch must be applied
    if proposal.patch_status != "applied":
        failures.append(f"Patch not applied (status: {proposal.patch_status}). Run: roxy evolve patch apply {proposal.id[:20]}")

    # Gate 2: tests must pass
    if proposal.test_status != "passed":
        failures.append(f"Tests not passing (status: {proposal.test_status}). Run: roxy evolve test {proposal.id[:20]}")

    # Gate 3: review report must exist
    if not proposal.report_path or not Path(proposal.report_path).exists():
        failures.append("Review report not found. Run: roxy evolve review {proposal.id[:20]}")

    # Gate 4: working tree must be clean
    from roxy.evolution.workspace import EvolutionWorkspace
    ws = EvolutionWorkspace()
    info = ws.status()
    if not info.is_clean:
        failures.append("Working tree not clean. Commit or stash changes first.")
    if info.current_branch != "main":
        failures.append(f"Must be on main branch to merge. Currently on: {info.current_branch}")

    # Gate 5: eval regressions
    if proposal.report_path and Path(proposal.report_path).exists():
        report_text = Path(proposal.report_path).read_text(encoding="utf-8")
        reg_match = re.search(r"Regressions:\s*(\d+)", report_text)
        if reg_match and int(reg_match.group(1)) > 0:
            failures.append(
                f"Eval report shows {reg_match.group(1)} regression(s). "
                f"Review the report and re-run with --allow-regressions if approved."
            )

    if failures:
        console.print("[red]Merge blocked — safety gates not met:[/red]")
        for f in failures:
            console.print(f"  [red]✗[/red] {f}")
        raise SystemExit(1)

    try:
        commit = ws.merge_to_main(proposal.id)
        proposal.status = "merged"
        proposal.patch_status = "merged"
        from roxy.evolution.planner import EvolutionPlanner
        EvolutionPlanner().store.save(proposal)
        console.print(f"[green]✓[/green] Merged → [cyan]{commit}[/cyan]")
    except Exception as exc:
        console.print(f"[red]Merge failed: {exc}[/red]")
        raise SystemExit(1)
