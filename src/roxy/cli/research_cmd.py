""""roxy research" — manual research operations."""

import asyncio

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("research")
def research_cmd() -> None:
    """Manual research operations.

    \b
    Examples:
      roxy research feeds list
      roxy research collect --url "https://example.com/feed.xml"
      roxy research collect --all
      roxy research digest
    """
    pass


# ── feeds ────────────────────────────────────────────────────────

@research_cmd.group("feeds")
def research_feeds() -> None:
    """Manage configured research feed sources.

    \b
    Examples:
      roxy research feeds add "My Feed" "https://example.com/rss"
      roxy research feeds list
      roxy research feeds remove "My Feed"
    """
    pass


@research_feeds.command("list")
def feeds_list() -> None:
    """List all configured RSS feed sources."""
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)
    feeds = sm.list_feeds()

    if not feeds:
        console.print("[yellow]No feeds configured.[/yellow]")
        console.print("Add one: [cyan]roxy research feeds add \"Name\" \"https://example.com/rss\"[/cyan]")
        return

    table = Table(title="Research Feeds")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="dim")
    table.add_column("Status")

    for f in feeds:
        status = "[green]enabled[/green]" if f.enabled else "[dim]disabled[/dim]"
        table.add_row(f.name, f.url, status)

    console.print(table)


@research_feeds.command("add")
@click.argument("name")
@click.argument("url")
def feeds_add(name: str, url: str) -> None:
    """Add a new RSS feed source.

    \b
    Example:
      roxy research feeds add "Hacker News" "https://hnrss.org/frontpage"
    """
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)

    try:
        feed = sm.add_feed(name, url)
        console.print(f"[green]✓[/green] Added feed: [cyan]{feed.name}[/cyan] ({feed.url})")
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")


@research_feeds.command("remove")
@click.argument("name")
def feeds_remove(name: str) -> None:
    """Remove a feed by name."""
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)

    if sm.remove_feed(name):
        console.print(f"[green]✓[/green] Removed feed: [cyan]{name}[/cyan]")
    else:
        console.print(f"[yellow]Feed not found: '{name}'[/yellow]")


@research_feeds.command("status")
@click.argument("name", required=False)
def feeds_status(name: str | None) -> None:
    """Show feed collection status.

    \b
    Without arguments: summary of all feeds.
    With a feed name: detailed status for that feed.
    """
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)

    if name:
        feed = sm.get_feed(name)
        if not feed:
            console.print(f"[yellow]Feed not found: '{name}'[/yellow]")
            return
        _print_feed_detail(feed)
    else:
        _print_feed_summary(sm)


@research_feeds.command("enable")
@click.argument("name")
def feeds_enable(name: str) -> None:
    """Enable a feed."""
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)
    if sm.set_enabled(name, True):
        console.print(f"[green]✓[/green] Enabled: [cyan]{name}[/cyan]")
    else:
        console.print(f"[yellow]Feed not found: '{name}'[/yellow]")


@research_feeds.command("disable")
@click.argument("name")
def feeds_disable(name: str) -> None:
    """Disable a feed (stops it from being collected with --all)."""
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)
    if sm.set_enabled(name, False):
        console.print(f"[green]✓[/green] Disabled: [cyan]{name}[/cyan]")
    else:
        console.print(f"[yellow]Feed not found: '{name}'[/yellow]")


# ── feed display helpers ────────────────────────────────────────


def _print_feed_detail(feed) -> None:
    from roxy.research.source_manager import FeedSource

    console.print()
    console.print(f"[bold cyan]{feed.name}[/bold cyan]")
    console.print(f"  URL:       {feed.url}")
    console.print(f"  Status:    {'[green]enabled[/green]' if feed.enabled else '[dim]disabled[/dim]'}")
    console.print(f"  Tags:      {', '.join(feed.tags) if feed.tags else '—'}")
    console.print(f"  Total collected: {feed.total_collected}")
    console.print(f"  Last run:  {feed.last_run_at[:19] if feed.last_run_at else 'never'}")
    console.print(f"  Last success: {feed.last_success_at[:19] if feed.last_success_at else 'never'}")
    if feed.last_error:
        console.print(f"  Last error: [red]{feed.last_error}[/red]")
    console.print()


def _print_feed_summary(sm) -> None:
    summary = sm.get_status_summary()
    console.print()
    console.print("[bold]Feed Status Summary[/bold]")
    console.print(f"  Total:   {summary['total']}")
    console.print(f"  Enabled: [green]{summary['enabled']}[/green]")
    console.print(f"  Disabled: {summary['disabled']}")
    if summary['with_errors']:
        console.print(f"  With errors: [red]{summary['with_errors']}[/red]")
    if summary['never_run']:
        console.print(f"  Never run: [yellow]{summary['never_run']}[/yellow]")
    console.print()

    if summary['feeds']:
        from rich.table import Table
        table = Table(title="Feeds")
        table.add_column("Name", style="cyan")
        table.add_column("Status")
        table.add_column("Collected", justify="right")
        table.add_column("Last Run")
        table.add_column("Last Error", style="red")

        for f in summary['feeds']:
            status = "[green]enabled[/green]" if f["enabled"] else "[dim]disabled[/dim]"
            last_run = f["last_run_at"][:16] if f["last_run_at"] else "never"
            err = f["last_error"][:40] if f["last_error"] else "—"
            table.add_row(f["name"], status, str(f["total_collected"]), last_run, err)

        console.print(table)
        console.print()


# ── collect ──────────────────────────────────────────────────────

@research_cmd.command("collect")
@click.option("--channel", "-c", default="rss", help="Channel to collect from (default: rss).")
@click.option("--url", "-u", default="", help="Feed URL or search URL for the channel.")
@click.option("--all", "collect_all", is_flag=True, help="Collect from ALL configured feeds.")
@click.option("--topic", "-t", default="", help="Topic filter.")
@click.option("--since", default=None, help="ISO 8601 date — only items after this.")
@click.option("--max-items", default=50, help="Max items per feed.")
def research_collect(
    channel: str,
    url: str,
    collect_all: bool,
    topic: str,
    since: str | None,
    max_items: int,
) -> None:
    """Collect research items and store in the knowledge base.

    \b
    Examples:
      roxy research collect --channel rss --url "https://example.com/feed.xml"
      roxy research collect --all
    """
    from roxy.config.loader import Config
    from roxy.research.collector import ContentCollector
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()

    async def _collect_one(ch: str, u: str, fn: str = "") -> dict:
        collector = ContentCollector(cfg)
        return await collector.collect(
            channel_name=ch,
            feed_url=u,
            topic=topic,
            since=since,
            max_items=max_items,
            feed_name=fn,
        )

    if collect_all:
        sm = SourceManager(cfg)
        feeds = sm.list_feeds(enabled_only=True)
        if not feeds:
            console.print("[yellow]No enabled feeds configured.[/yellow]")
            console.print("Add one: [cyan]roxy research feeds add \"Name\" \"URL\"[/cyan]")
            return

        console.print(f"[dim]Collecting from [cyan]{len(feeds)}[/cyan] feed(s)...[/dim]")
        collector = ContentCollector(cfg)

        for feed in feeds:
            console.print(f"  [cyan]{feed.name}[/cyan]...", end=" ")
            try:
                result = asyncio.run(_collect_one("rss", feed.url, fn=feed.name))
                new_c = result.get("items_new", 0)
                dup_c = result.get("items_duplicate", 0)
                errs = result.get("errors", [])
                if errs:
                    console.print(f"[red]✗ {errs[0]}[/red]")
                else:
                    console.print(f"[green]{new_c} new[/green], {dup_c} dup")
            except Exception as exc:
                console.print(f"[red]✗ {exc}[/red]")

        console.print()
        console.print("[bold green]Collection complete.[/bold green]")
        console.print(f"  View: [cyan]roxy research runs latest[/cyan]")
        console.print()
        return

    # Single URL mode
    if not url and channel == "rss":
        console.print("[red]Error: --url is required (or use --all for configured feeds).[/red]")
        console.print("Example: roxy research collect --url \"https://example.com/feed.xml\"")
        return

    console.print(f"[dim]Collecting from [cyan]{channel}[/cyan]: {url}...[/dim]")
    try:
        result = asyncio.run(_collect_one(channel, url))
    except Exception as exc:
        console.print(f"[red]Collection failed: {exc}[/red]")
        return

    if result.get("errors"):
        for err in result["errors"]:
            console.print(f"[red]  Error: {err}[/red]")
        return

    console.print()
    console.print("[bold green]Collection complete:[/bold green]")
    console.print(f"  Items found:      {result['items_found']}")
    console.print(f"  New entries:      [green]{result['items_new']}[/green]")
    console.print(f"  Duplicates:       [yellow]{result['items_duplicate']}[/yellow]")
    console.print()


# ── runs ─────────────────────────────────────────────────────────

@research_cmd.group("runs")
def research_runs() -> None:
    """View collection run history.

    \b
    Examples:
      roxy research runs list
      roxy research runs latest
      roxy research runs show <run_id>
    """
    pass


@research_runs.command("list")
@click.option("--limit", "-n", default=10, help="Max runs to show.")
def runs_list(limit: int) -> None:
    """List recent collection runs."""
    from roxy.research.run_history import RunHistory

    rh = RunHistory()
    runs = rh.list_runs(limit=limit)

    if not runs:
        console.print("[yellow]No collection runs yet.[/yellow]")
        console.print("Run: [cyan]roxy research collect --all[/cyan]")
        return

    from rich.table import Table
    table = Table(title="Collection Run History")
    table.add_column("Run ID", style="cyan")
    table.add_column("Started")
    table.add_column("Feeds")
    table.add_column("New", justify="right")
    table.add_column("Errors", justify="right")

    for r in runs:
        started = r["started_at"][:16] if r["started_at"] else "—"
        err_str = f"[red]{r['error_count']}[/red]" if r["error_count"] else "0"
        table.add_row(r["run_id"][:8], started, str(r["feed_count"]),
                      str(r["total_new"]), err_str)

    console.print(table)
    console.print(f"\n[dim]{len(runs)} run(s)[/dim]")


@research_runs.command("latest")
def runs_latest() -> None:
    """Show the most recent collection run."""
    from roxy.research.run_history import RunHistory

    rh = RunHistory()
    run = rh.latest_run()

    if not run:
        console.print("[yellow]No collection runs yet.[/yellow]")
        return

    _print_run_detail(run)


@research_runs.command("show")
@click.argument("run_id")
def runs_show(run_id: str) -> None:
    """Show details of a specific run."""
    from roxy.research.run_history import RunHistory

    rh = RunHistory()
    run = rh.get_run(run_id)
    if not run:
        # Try prefix match
        runs = rh.list_runs()
        matches = [r for r in runs if r["run_id"].startswith(run_id)]
        if len(matches) == 1:
            run = rh.get_run(matches[0]["run_id"])
        elif len(matches) > 1:
            console.print(f"[yellow]Ambiguous prefix. Matches: {', '.join(r['run_id'][:8] for r in matches)}[/yellow]")
            return

    if not run:
        console.print(f"[yellow]Run '{run_id}' not found.[/yellow]")
        return

    _print_run_detail(run)


def _print_run_detail(run: dict) -> None:
    console.print()
    console.print(f"[bold]Run [cyan]{run['run_id'][:8]}[/cyan][/bold]")
    console.print(f"  Started:    {run.get('started_at', '—')[:19]}")
    console.print(f"  Finished:   {run.get('finished_at', '—')[:19]}")
    console.print(f"  Feeds:      {run.get('feed_count', 0)}")
    console.print(f"  Total new:  [green]{run.get('total_new', 0)}[/green]")
    console.print(f"  Duplicates: {run.get('total_dup', 0)}")
    err_count = run.get('error_count', 0)
    console.print(f"  Errors:     {'[red]' + str(err_count) + '[/red]' if err_count else '0'}")
    console.print()

    feeds = run.get("feeds", [])
    if feeds:
        for f in feeds:
            icon = "[green]✓[/green]" if not f["errors"] else "[red]✗[/red]"
            src = f["source_name"] or f["channel_name"]
            console.print(f"  {icon} [cyan]{src}[/cyan] — "
                          f"{f['items_new']} new, {f['items_duplicate']} dup"
                          + (f" ([red]{f['errors'][:60]}[/red])" if f["errors"] else ""))
        console.print()


# ── digest ───────────────────────────────────────────────────────

@research_cmd.command("digest")
@click.option("--days", "-d", default=7, help="Look back this many days (default: 7).")
@click.option("--source", "-s", default=None, help="Filter by source (rss, web, manual).")
@click.option("--run", "-r", "run_id", default=None, help="Generate digest for a specific run (latest, or <id>).")
@click.option("--group-by", "-g", default="source", help="Group by: source (default), date, or tag.")
@click.option("--out", "-o", default=None, help="Write report to file (Markdown).")
@click.option("--json", "as_json", is_flag=True, help="Output as structured JSON.")
def research_digest(
    days: int,
    source: str | None,
    run_id: str | None,
    group_by: str,
    out: str | None,
    as_json: bool,
) -> None:
    """Generate a structured research digest from the knowledge base.

    \b
    Examples:
      roxy research digest --days 3 --group-by source
      roxy research digest --run latest --out digest.md
      roxy research digest --json --group-by tag
    """
    from pathlib import Path
    from roxy.research.digest import ResearchDigest

    # Resolve --run latest
    resolved_run = None
    if run_id:
        if run_id.lower() == "latest":
            from roxy.research.run_history import RunHistory
            rh = RunHistory()
            latest = rh.latest_run()
            if latest:
                resolved_run = latest["run_id"]
            else:
                console.print("[yellow]No collection runs found. Use --days instead.[/yellow]")
                return
        else:
            resolved_run = run_id

    # Validate group_by
    if group_by not in ("source", "date", "tag"):
        console.print(f"[yellow]Invalid --group-by '{group_by}'. Use: source, date, or tag.[/yellow]")
        return

    dg = ResearchDigest()
    result = dg.generate(
        days=days,
        collected_via=source,
        run_id=resolved_run,
        group_by=group_by,
    )

    # Write to file
    if out:
        dg.write_report(result, Path(out))
        console.print(f"[green]✓[/green] Digest written to [cyan]{out}[/cyan]")

    # JSON output
    if as_json:
        import json
        # Remove report_md from JSON (it's the markdown version)
        json_out = {k: v for k, v in result.items() if k != "report_md"}
        click.echo(json.dumps(json_out, indent=2, ensure_ascii=False, default=str))
        return

    # Terminal display: show report_md directly
    if not out:
        console.print()
        console.print(result["report_md"])
    elif not as_json:
        console.print(f"  Period: {result['period']}")
        console.print(f"  Entries: {result['entry_count']}")
        console.print(f"  Groups: {len(result['groups'])}")
        if resolved_run:
            console.print(f"  Run: [cyan]{resolved_run[:8]}[/cyan]")
