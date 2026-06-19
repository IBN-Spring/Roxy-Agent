"""Roxy CLI — main command group."""

import sys

import click

from roxy import __version__
from roxy.cli.init_cmd import init_cmd
from roxy.cli.doctor_cmd import doctor_cmd
from roxy.cli.config_cmd import config_cmd


@click.group(invoke_without_command=True)
@click.option("--version", "-V", is_flag=True, help="Show version and exit.")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.pass_context
def main(ctx: click.Context, version: bool, verbose: bool) -> None:
    """Roxy — A vertical-domain autonomous research Agent CLI/TUI.

    Default command launches the interactive TUI chat.
    """
    if version:
        click.echo(f"roxy {__version__}")
        ctx.exit()

    # Ensure UTF-8 on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Default to chat if no subcommand
    if ctx.invoked_subcommand is None:
        from roxy.cli.chat_cmd import chat_cmd
        ctx.invoke(chat_cmd)


main.add_command(init_cmd)
main.add_command(doctor_cmd)
main.add_command(config_cmd)


# chat_cmd is added during Phase 1 — placeholder for now
# Import error is caught so Phase 0 can run without the chat module
try:
    from roxy.cli.chat_cmd import chat_cmd
    main.add_command(chat_cmd)
except ImportError:
    pass
