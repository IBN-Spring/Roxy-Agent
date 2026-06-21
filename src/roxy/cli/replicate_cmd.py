""""roxy replicate / deploy" — portable runtime replication."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group("replicate")
def replicate_cmd() -> None:
    """Export and validate portable Roxy runtime bundles.

    \b
    Never includes API keys, tokens, or raw secrets.
    """
    pass


@replicate_cmd.command("export")
@click.option("--out", "-o", default="roxy-bundle.zip", help="Output bundle path.")
@click.option("--no-kb", is_flag=True, help="Skip knowledge base export.")
def replicate_export(out: str, no_kb: bool) -> None:
    """Export a portable Roxy runtime bundle.

    \b
    Bundle includes: source code, OKF knowledge, eval seeds,
    config template (sanitized), skills, and a signed manifest.

    No API keys or secrets are ever included.
    """
    from roxy.replication.replicate import Replicator

    replicator = Replicator()
    manifest = replicator.export_bundle(Path(out), include_kb=not no_kb)

    console.print(f"\n[green]✓[/green] Bundle exported → [cyan]{out}[/cyan]")
    console.print(f"  Version: {manifest['roxy_version']}")
    console.print(f"  Commit:  {manifest['git_commit']}")
    console.print(f"  Contents:")
    for key, info in manifest.get("contents", {}).items():
        console.print(f"    [cyan]{info['file']}[/cyan] ({key})")
    console.print()
    console.print(f"Validate:  [cyan]roxy replicate validate {out}[/cyan]")
    console.print(f"Deploy plan: [cyan]roxy deploy plan --from {out}[/cyan]")


@replicate_cmd.command("validate")
@click.argument("bundle_path", default="roxy-bundle.zip")
def replicate_validate(bundle_path: str) -> None:
    """Validate a replication bundle.

    \b
    Checks: manifest integrity, file hashes, OKF schema compliance,
    config template validity.
    """
    from roxy.replication.replicate import Replicator

    replicator = Replicator()
    result = replicator.validate_bundle(Path(bundle_path))

    if result["valid"]:
        console.print(f"\n[green]✓[/green] Bundle is valid")
        m = result.get("manifest", {})
        console.print(f"  Version: {m.get('roxy_version', '?')}")
        console.print(f"  Contents: {len(m.get('contents', {}))} files")
    else:
        console.print(f"\n[red]✗[/red] Bundle validation failed")
        for err in result["errors"]:
            console.print(f"  [red]{err}[/red]")
        raise SystemExit(1)


@click.group("deploy")
def deploy_cmd() -> None:
    """Deployment planning (dry-run only, no auto-deploy)."""
    pass


@deploy_cmd.command("plan")
@click.option("--from", "-f", "bundle_path", default="roxy-bundle.zip", help="Bundle to deploy.")
@click.option("--target", "-t", default="/opt/roxy", help="Target deployment directory.")
def deploy_plan(bundle_path: str, target: str) -> None:
    """Generate a deployment plan (dry-run only).

    \b
    Outputs a step-by-step checklist. Never executes anything.
    """
    from roxy.replication.replicate import Replicator

    replicator = Replicator()
    plan = replicator.generate_deploy_plan(Path(bundle_path), target)

    console.print()
    console.print(Panel(plan, title="Deployment Plan", border_style="cyan"))
    console.print()
    console.print("[yellow]This is a dry-run plan only. No changes were made.[/yellow]")
