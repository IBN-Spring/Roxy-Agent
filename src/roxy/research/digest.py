"""ResearchDigest 2.0 — generate structured research reports from the KB."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from roxy.knowledge.query import KnowledgeQuery
from roxy.knowledge.schema import KnowledgeEntry
from roxy.knowledge.store import KnowledgeStore
from roxy.research.run_history import RunHistory


class ResearchDigest:
    """Generate a structured research digest from KB entries.

    Supports: run-based, date-based, grouped, markdown output, OKF JSON report.
    """

    def __init__(self, store: KnowledgeStore | None = None):
        self.store = store or KnowledgeStore()
        self.store.init_db()
        self.query = KnowledgeQuery(self.store)

    def generate(
        self,
        days: int = 7,
        limit: int = 50,
        collected_via: str | None = None,
        run_id: str | None = None,
        group_by: str = "source",
    ) -> dict:
        """Generate a structured digest.

        Args:
            days: Look back this many days (ignored if run_id is set).
            limit: Max entries.
            collected_via: Filter by source channel.
            run_id: Generate digest for a specific collection run.
            group_by: How to group entries — "source", "date", or "tag".

        Returns:
            Dict with {title, generated_at, period, entry_count, groups, entries, report_md}.
        """
        now = datetime.now(timezone.utc)

        # Get entries: by run or by time
        if run_id:
            entries = self._entries_by_run(run_id, collected_via)
            period_label = f"Run {run_id[:8]}"
        else:
            since = (now - timedelta(days=days)).isoformat()
            entries = self.query.search(query="", limit=limit, since=since, collected_via=collected_via)
            if not entries:
                entries = self._fallback_recent(limit, since, collected_via)
            period_label = f"Last {days} days"

        # Get run info if available
        run_info = None
        if run_id:
            rh = RunHistory(self.store)
            run_info = rh.get_run(run_id)

        # Group entries
        groups = self._group_entries(entries, group_by)

        # Build markdown report
        report_md = self._build_markdown(
            entries, groups, group_by, period_label, run_info, now
        )

        return {
            "title": f"Research Digest — {period_label}",
            "generated_at": now.isoformat(),
            "period": period_label,
            "run_id": run_id,
            "run_info": run_info,
            "entry_count": len(entries),
            "group_by": group_by,
            "groups": {
                name: {
                    "count": len(items),
                    "entries": [e.to_okf_dict() for e in items],
                }
                for name, items in groups.items()
            },
            "entries": [e.to_okf_dict() for e in entries],
            "report_md": report_md,
        }

    # ── entry retrieval ──────────────────────────────────────────

    def _entries_by_run(self, run_id: str, collected_via: str | None) -> list[KnowledgeEntry]:
        """Get entries collected in a specific run by matching time ranges."""
        rh = RunHistory(self.store)
        run = rh.get_run(run_id)
        if not run:
            return []

        # Use the run's time window to find entries
        started = run.get("started_at", "")
        finished = run.get("finished_at", "")

        if not started:
            return []

        # Query entries collected during this run's time window
        end = finished or datetime.now(timezone.utc).isoformat()
        entries = self.query.search(query="", limit=200, since=started, collected_via=collected_via)
        # Filter to only those collected before run ended
        entries = [e for e in entries if e.collected_at <= end]

        # Also try to match by source_name if the run has feeds
        feed_sources = {f["source_name"] for f in run.get("feeds", []) if f.get("source_name")}
        if feed_sources:
            entries = [e for e in entries if e.source_channel in feed_sources or e.collected_via in feed_sources]

        return entries[:100]

    def _fallback_recent(self, limit, since, collected_via):
        entries = self.query.list_recent(limit=limit)
        return [e for e in entries
                if e.collected_at >= since
                and (not collected_via or e.collected_via == collected_via)]

    # ── grouping ─────────────────────────────────────────────────

    def _group_entries(self, entries: list[KnowledgeEntry], group_by: str) -> dict[str, list[KnowledgeEntry]]:
        groups: dict[str, list[KnowledgeEntry]] = {}

        for e in entries:
            if group_by == "date":
                key = e.collected_at[:10] if e.collected_at else "unknown"
            elif group_by == "tag":
                tags = e.tags if e.tags else ["untagged"]
                for tag in tags:
                    groups.setdefault(tag, []).append(e)
                continue  # multi-key, already added
            else:  # source (default)
                key = e.collected_via or e.source_channel or "unknown"

            groups.setdefault(key, []).append(e)

        return groups

    # ── markdown report ──────────────────────────────────────────

    def _build_markdown(
        self,
        entries: list[KnowledgeEntry],
        groups: dict[str, list[KnowledgeEntry]],
        group_by: str,
        period_label: str,
        run_info: dict | None,
        now: datetime,
    ) -> str:
        lines: list[str] = []

        # Title
        lines.append(f"# Roxy Research Digest")
        lines.append(f"**{period_label}** — Generated {now.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("")

        # Overview
        lines.append("## Overview")
        lines.append(f"- **Entries**: {len(entries)}")
        lines.append(f"- **Grouped by**: {group_by}")
        unique_sources = len({e.collected_via for e in entries})
        lines.append(f"- **Sources**: {unique_sources}")
        if entries:
            dates = [e.collected_at[:10] for e in entries if e.collected_at]
            if dates:
                lines.append(f"- **Date range**: {min(dates)} to {max(dates)}")
        lines.append("")

        # Run summary (if available)
        if run_info:
            lines.append("## Collection Run")
            lines.append(f"- **Run ID**: `{run_info['run_id'][:8]}`")
            lines.append(f"- **Started**: {run_info.get('started_at', '—')[:19]}")
            lines.append(f"- **Feeds processed**: {run_info.get('feed_count', 0)}")
            lines.append(f"- **New entries**: {run_info.get('total_new', 0)}")
            lines.append(f"- **Duplicates**: {run_info.get('total_dup', 0)}")
            err_count = run_info.get('error_count', 0)
            if err_count:
                lines.append(f"- **Errors**: {err_count}")
            lines.append("")

        # Source/group sections
        group_label = {"source": "Source", "date": "Date", "tag": "Tag"}.get(group_by, "Group")
        for group_name, items in sorted(groups.items()):
            display_name = group_name or "unknown"
            lines.append(f"## {group_label}: {display_name} ({len(items)} entries)")
            lines.append("")
            for item in items[:15]:  # top 15 per group
                date = item.published_at[:10] if item.published_at else "—"
                title = item.title or "(untitled)"
                url = item.canonical_url or ""
                summary = item.summary or item.content_plain or ""
                if len(summary) > 200:
                    summary = summary[:200] + "..."

                lines.append(f"### {title}")
                lines.append(f"- **Date**: {date}")
                if url:
                    lines.append(f"- **URL**: {url}")
                if item.authors:
                    lines.append(f"- **Authors**: {', '.join(item.authors)}")
                if item.tags:
                    lines.append(f"- **Tags**: {', '.join(item.tags)}")
                if summary:
                    lines.append(f"- **Summary**: {summary}")
                lines.append("")
            lines.append("")

        # Key entries (top across all groups by title uniqueness)
        lines.append("## Key Entries")
        seen_titles = set()
        key_count = 0
        for item in sorted(entries, key=lambda e: e.collected_at or "", reverse=True):
            title = item.title or "(untitled)"
            if title in seen_titles:
                continue
            seen_titles.add(title)
            url = item.canonical_url or ""
            lines.append(f"- [{title}]({url})" if url else f"- {title}")
            key_count += 1
            if key_count >= 20:
                break
        lines.append("")

        # Follow-up questions
        follow_ups = [e for e in entries if hasattr(e, 'follow_ups') and e.to_okf_dict().get('follow_ups')]
        if follow_ups:
            lines.append("## Follow-up Questions")
            for e in follow_ups[:5]:
                for fq in e.to_okf_dict().get("follow_ups", [])[:3]:
                    lines.append(f"- [{fq.get('status', 'open')}] {fq.get('question', '')}")
            lines.append("")

        # Links
        urls = [e.canonical_url for e in entries if e.canonical_url]
        if urls:
            lines.append("## Links")
            for url in urls[:30]:
                lines.append(f"- {url}")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Generated by Roxy — {now.strftime('%Y-%m-%d %H:%M UTC')}*")

        return "\n".join(lines)

    def write_report(self, result: dict, path: Path) -> None:
        """Write the markdown report to a file."""
        path.write_text(result["report_md"], encoding="utf-8")
