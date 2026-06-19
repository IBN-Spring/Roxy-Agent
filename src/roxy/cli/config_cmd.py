""""roxy config" — manage configuration values."""

import click
from rich.console import Console
from rich.table import Table

from roxy.config.loader import Config

console = Console()


@click.group("config")
def config_cmd() -> None:
    """Manage Roxy configuration.

    \b
    Examples:
      roxy config set models.default openai/gpt-4.1
      roxy config get user.name
      roxy config list
      roxy config path
    """
    pass


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a config value. Dotted keys create nested sections.

    \b
    Examples:
      roxy config set user.name "Alice"
      roxy config set models.providers.openai.api_key sk-xxx
    """
    cfg = Config()
    cfg.load()

    # Try to coerce value type
    typed_value = _coerce_value(value)
    cfg.set(key, typed_value)
    cfg.save()
    console.print(f"[green]✓[/green] Set [cyan]{key}[/cyan] = [dim]{_mask_if_secret(key, value)}[/dim]")


@config_cmd.command("get")
@click.argument("key")
def config_get(key: str) -> None:
    """Get a config value.

    Example:
      roxy config get user.name
    """
    cfg = Config()
    cfg.load()
    value = cfg.get(key)
    if value is None or value == "":
        console.print(f"[yellow]{key} = (not set)[/yellow]")
    else:
        display = _mask_if_secret(key, str(value))
        console.print(f"[cyan]{key}[/cyan] = {display}")


@config_cmd.command("list")
def config_list() -> None:
    """List all configuration values (secrets are masked)."""
    cfg = Config()
    cfg.load()

    table = Table(title="Roxy Configuration", title_style="bold")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="dim")

    data = cfg.to_dict(mask_secrets=True)
    for key in sorted(data.keys()):
        value = data[key]
        table.add_row(key, str(value))

    console.print(table)
    console.print(f"\nConfig file: [dim]{cfg._path}[/dim]")


@config_cmd.command("path")
def config_path() -> None:
    """Show the path to the config file."""
    cfg = Config()
    console.print(f"Config file: [cyan]{cfg._path}[/cyan]")
    if cfg._path.exists():
        console.print("[green]✓[/green] File exists")
    else:
        console.print("[yellow]![/yellow] File not found (run `roxy init` to create)")


# ── helpers ──────────────────────────────────────────────────────

def _coerce_value(value: str):
    """Try to coerce a string value to int, float, bool, or list."""
    # Booleans
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    # Integers
    try:
        return int(value)
    except ValueError:
        pass
    # Floats
    try:
        return float(value)
    except ValueError:
        pass
    # Comma-separated lists
    if "," in value:
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


def _mask_if_secret(key: str, value: str) -> str:
    """Mask secret-looking values."""
    secret_hints = ["api_key", "token", "password", "secret", "cookie"]
    for hint in secret_hints:
        if hint in key.lower():
            if len(value) <= 12:
                return value[:4] + "****"
            return value[:6] + "..." + value[-4:]
    return value
