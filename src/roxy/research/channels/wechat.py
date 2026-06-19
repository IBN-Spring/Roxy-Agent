"""WechatChannel — read articles from a wechat-query SQLite database.

This is an EXTERNAL adapter: it reads the SQLite DB that the wechat-query
service produces. Roxy does NOT import or depend on wechat-query source code.
Point `research.wechat.db_path` in your Roxy config to the wechat-query rss.db.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roxy.config.loader import Config
from roxy.research.channels.base import Channel, ResearchItem

logger = logging.getLogger(__name__)


class WechatChannel(Channel):
    """Read WeChat public account articles from a wechat-query SQLite DB.

    Tier 1 — requires a running wechat-query instance with a populated DB.

    Usage:
        channel = WechatChannel()
        ok, msg = await channel.check(config)
        items = await channel.collect(config, since="2025-01-01")
    """

    name: str = "wechat"
    description: str = "WeChat public account articles (via wechat-query SQLite)"
    tier: int = 1  # needs wechat-query setup

    DEFAULT_DB_PATH: str = "~/wechat-query/data/rss.db"

    async def check(self, config: Config) -> tuple[str, str]:
        """Verify the wechat-query SQLite DB is accessible."""
        db_path = self._resolve_db_path(config)

        if not db_path.exists():
            return (
                "off",
                f"wechat-query database not found at {db_path}. "
                "Set research.wechat.db_path in config, or run wechat-query first.",
            )

        try:
            conn = _connect_readonly(db_path)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('articles', 'subscriptions')"
            ).fetchall()
            conn.close()

            if len(tables) >= 1:
                return "ok", f"wechat-query DB found at {db_path}"
            return "warn", f"DB at {db_path} exists but missing expected tables"
        except Exception as exc:
            return "error", str(exc)

    async def collect(
        self,
        config: Config,
        topic: str = "",
        since: str | None = None,
        feed_url: str = "",
        max_items: int = 50,
    ) -> list[ResearchItem]:
        """Collect recent articles from the wechat-query SQLite DB.

        Args:
            config: Roxy config (reads research.wechat.db_path).
            topic: Ignored for wechat channel (subscription is the source selector).
            since: ISO 8601 — only articles published after this date.
            feed_url: Ignored (wechat uses configured subscriptions).
            max_items: Max articles to return.
        """
        db_path = self._resolve_db_path(config)

        if not db_path.exists():
            logger.warning(f"WechatChannel: DB not found at {db_path}")
            return []

        try:
            conn = _connect_readonly(db_path)
            conn.row_factory = sqlite3.Row
        except Exception as exc:
            logger.error(f"WechatChannel: cannot open DB at {db_path}: {exc}")
            return []

        try:
            items = self._query_articles(conn, since, max_items)
        finally:
            conn.close()

        return items

    # ── helpers ──────────────────────────────────────────────────

    def _resolve_db_path(self, config: Config) -> Path:
        """Resolve the wechat-query DB path from config."""
        db_path_str = config.get("research.wechat.db_path", "")
        if not db_path_str:
            db_path_str = self.DEFAULT_DB_PATH
        return Path(db_path_str).expanduser().resolve()

    def _query_articles(
        self,
        conn: sqlite3.Connection,
        since: str | None,
        max_items: int,
    ) -> list[ResearchItem]:
        """Query articles from the wechat-query DB and convert to ResearchItems."""
        query = """
            SELECT
                a.id, a.title, a.link, a.author,
                a.plain_content, a.content, a.publish_time
            FROM articles a
        """
        params: list[Any] = []

        if since:
            # Convert ISO 8601 to Unix timestamp
            try:
                since_dt = datetime.fromisoformat(since)
                since_ts = int(since_dt.timestamp())
                query += " WHERE a.publish_time > ?"
                params.append(since_ts)
            except ValueError:
                pass

        query += " ORDER BY a.publish_time DESC LIMIT ?"
        params.append(max_items)

        try:
            rows = conn.execute(query, params).fetchall()
        except sqlite3.OperationalError as exc:
            logger.error(f"WechatChannel: query failed: {exc}")
            return []

        items: list[ResearchItem] = []
        collection_time = datetime.now(timezone.utc).isoformat()

        for row in rows:
            published = ""
            publish_ts = row["publish_time"]
            if publish_ts:
                try:
                    published = datetime.fromtimestamp(
                        int(publish_ts), tz=timezone.utc
                    ).isoformat()
                except (ValueError, OSError):
                    pass

            content_md = row["content"] or ""
            content_plain = row["plain_content"] or ""

            if content_plain and not content_md:
                content_md = content_plain
            if content_md and not content_plain:
                content_plain = content_md[:500]

            item = ResearchItem(
                title=row["title"] or "(untitled)",
                canonical_url=row["link"] or "",
                content_md=content_md,
                content_plain=content_plain[:1000],
                summary=content_plain[:300],
                authors=[row["author"]] if row["author"] else [],
                published_at=published,
                collected_at=collection_time,
                collected_via="wechat",
                source_type="wechat_mp",
                source_feed_url="",
                source_channel="WeChat Public Account",
            )

            if item.title and item.canonical_url:
                items.append(item)

        return items


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite database in read-only URI mode."""
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
