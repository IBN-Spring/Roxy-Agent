""""roxy chat" — launch the interactive TUI."""

import sys

import click
from rich.console import Console

console = Console()


@click.command("chat")
@click.option("--model", "-m", default=None, help="Override the default model.")
@click.option("--session", "-s", default=None, help="Resume a specific session ID.")
@click.option("--workspace", "-w", default=None, help="Set workspace directory.")
@click.option("--no-tui", is_flag=True, help="Use plain terminal REPL instead of TUI.")
def chat_cmd(model: str | None, session: str | None, workspace: str | None, no_tui: bool) -> None:
    """Start interactive chat (default command).

    Launches the Roxy TUI for conversation with your configured LLM.
    """
    from roxy.config.loader import Config

    cfg = Config()
    cfg.load()

    # Apply CLI overrides
    if model:
        cfg.set_cli_override("models.default", model)
    if workspace:
        cfg.set_cli_override("workspace.path", workspace)

    if no_tui:
        _launch_repl(cfg, model, session)
    else:
        _launch_tui(cfg, model, session)


def _launch_tui(cfg, model: str | None, session: str | None) -> None:
    """Launch the Textual TUI."""
    try:
        from roxy.tui.app import launch_tui

        # Ensure UTF-8 on Windows
        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding="utf-8")
                sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass

        launch_tui(config=cfg, session_id=session, model=model)
    except ImportError as exc:
        console.print()
        console.print(f"[red]Error: {exc}[/red]")
        console.print()
        console.print(
            "[yellow]The TUI requires the 'textual' package.[/yellow]"
        )
        console.print("Install it with: [cyan]pip install roxy[tui][/cyan]")
        console.print()
        console.print("Or use the plain REPL: [cyan]roxy chat --no-tui[/cyan]")
        console.print()


def _launch_repl(cfg, model: str | None, session: str | None) -> None:
    """Launch a plain terminal REPL (no TUI)."""
    import asyncio

    from roxy.engine.query_engine import QueryEngine
    from roxy.engine.session import SessionManager

    console.print()
    console.print("[bold cyan]Roxy Chat (REPL mode)[/bold cyan]")
    console.print("[dim]Type your messages. /exit to quit, /help for commands.[/dim]")
    console.print()

    sm = SessionManager()
    sess = None
    if session:
        sess = sm.load(session)
        if sess:
            console.print(f"[dim]Resumed session: {session}[/dim]")
        else:
            console.print(f"[yellow]Session '{session}' not found. Starting new.[/yellow]")

    engine = QueryEngine(cfg, sess)

    async def process_message(text: str) -> None:
        console.print()
        full = ""
        async for output in engine.submit_message(text, model):
            if output.type == "status":
                console.print(f"[dim]{output.content}[/dim]")
            elif output.type == "chunk":
                console.print(output.content, end="")
                full += output.content
            elif output.type == "error":
                console.print(f"\n[red]Error: {output.content}[/red]")
            elif output.type == "done":
                console.print()
        console.print()

    async def repl_loop() -> None:
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not text:
                continue
            if text == "/exit":
                break
            if text == "/help":
                console.print("[dim]/exit  Quit[/dim]")
                console.print("[dim]/help  Show this message[/dim]")
                console.print("[dim]/model Show current model[/dim]")
                continue
            if text == "/model":
                model_name = engine.provider.resolve_model(model)
                console.print(f"[dim]Model: {model_name}[/dim]")
                continue

            await process_message(text)

    try:
        asyncio.run(repl_loop())
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")

    console.print(f"\n[dim]Session: {engine.session_id}[/dim]")
