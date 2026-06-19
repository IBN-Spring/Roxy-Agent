"""Tests for WechatChannel — reading from wechat-query SQLite."""

import sqlite3
from pathlib import Path

import pytest

from roxy.config.loader import Config
from roxy.research.channels.wechat import WechatChannel, _connect_readonly


def _create_test_db(db_path: Path, articles: list[dict] | None = None):
    """Create a minimal wechat-query-style SQLite DB."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY,
            fakeid TEXT,
            title TEXT,
            link TEXT,
            author TEXT,
            plain_content TEXT,
            content TEXT,
            publish_time INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            fakeid TEXT PRIMARY KEY,
            nickname TEXT,
            alias TEXT
        )
    """)
    for a in (articles or []):
        conn.execute(
            "INSERT INTO articles (title, link, author, plain_content, content, publish_time) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                a.get("title", ""),
                a.get("link", ""),
                a.get("author", ""),
                a.get("plain_content", ""),
                a.get("content", ""),
                a.get("publish_time", 1700000000),
            ),
        )
    conn.commit()
    conn.close()


class TestWechatChannel:
    @pytest.mark.asyncio
    async def test_check_ok_when_db_exists(self, tmp_path: Path):
        db_path = tmp_path / "rss.db"
        _create_test_db(db_path)

        ch = WechatChannel()
        # Override the default DB path
        ch.DEFAULT_DB_PATH = str(db_path)

        cfg = Config()
        cfg.load()
        status, msg = await ch.check(cfg)
        assert status == "ok"

    @pytest.mark.asyncio
    async def test_check_off_when_db_missing(self, tmp_path: Path):
        ch = WechatChannel()
        ch.DEFAULT_DB_PATH = str(tmp_path / "nonexistent.db")

        cfg = Config()
        cfg.load()
        status, msg = await ch.check(cfg)
        assert status == "off"

    @pytest.mark.asyncio
    async def test_collect_returns_articles(self, tmp_path: Path):
        db_path = tmp_path / "rss.db"
        _create_test_db(db_path, [
            {
                "title": "WeChat Article 1",
                "link": "https://mp.weixin.qq.com/s/test1",
                "author": "TestAuthor",
                "plain_content": "This is article content.",
                "content": "<p>This is article content.</p>",
                "publish_time": 1700000000,
            },
            {
                "title": "WeChat Article 2",
                "link": "https://mp.weixin.qq.com/s/test2",
                "author": "AnotherAuthor",
                "plain_content": "Second article.",
                "content": "<p>Second article.</p>",
                "publish_time": 1700086400,
            },
        ])

        ch = WechatChannel()
        ch.DEFAULT_DB_PATH = str(db_path)

        cfg = Config()
        cfg.load()
        items = await ch.collect(cfg)

        assert len(items) == 2
        assert items[0].collected_via == "wechat"
        assert items[0].source_type == "wechat_mp"
        assert items[0].authors == ["AnotherAuthor"]  # newest first (descending)
        assert items[0].title == "WeChat Article 2"

    @pytest.mark.asyncio
    async def test_collect_respects_since_filter(self, tmp_path: Path):
        db_path = tmp_path / "rss.db"
        _create_test_db(db_path, [
            {
                "title": "Old Article",
                "link": "https://mp.weixin.qq.com/s/old",
                "publish_time": 1600000000,  # 2020-09-13
            },
            {
                "title": "New Article",
                "link": "https://mp.weixin.qq.com/s/new",
                "publish_time": 1700000000,  # 2023-11-14
            },
        ])

        ch = WechatChannel()
        ch.DEFAULT_DB_PATH = str(db_path)

        cfg = Config()
        cfg.load()
        # since=2023-01-01 should filter out the old article
        items = await ch.collect(cfg, since="2023-01-01T00:00:00+00:00")

        assert len(items) == 1
        assert items[0].title == "New Article"

    @pytest.mark.asyncio
    async def test_collect_respects_max_items(self, tmp_path: Path):
        db_path = tmp_path / "rss.db"
        articles = [
            {
                "title": f"Article {i}",
                "link": f"https://mp.weixin.qq.com/s/{i}",
                "publish_time": 1700000000 + i,
            }
            for i in range(20)
        ]
        _create_test_db(db_path, articles)

        ch = WechatChannel()
        ch.DEFAULT_DB_PATH = str(db_path)

        cfg = Config()
        cfg.load()
        items = await ch.collect(cfg, max_items=5)
        assert len(items) == 5

    @pytest.mark.asyncio
    async def test_config_db_path_overrides_default(self, tmp_path: Path):
        db_path = tmp_path / "custom.db"
        _create_test_db(db_path, [{"title": "Custom", "link": "https://x.com/1", "publish_time": 1700000000}])

        ch = WechatChannel()
        cfg = Config()
        cfg.load()
        cfg.set("research.wechat.db_path", str(db_path))

        items = await ch.collect(cfg)
        assert len(items) == 1
        assert items[0].title == "Custom"

    def test_connect_readonly_rejects_writes(self, tmp_path: Path):
        db_path = tmp_path / "readonly.db"
        _create_test_db(db_path)

        conn = _connect_readonly(db_path)
        try:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("INSERT INTO subscriptions (fakeid, nickname) VALUES ('x', 'y')")
        finally:
            conn.close()
