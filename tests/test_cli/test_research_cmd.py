"""Tests for the research CLI."""

from click.testing import CliRunner

from roxy.cli.research_cmd import research_cmd


def test_collect_wechat_does_not_require_url(monkeypatch):
    """Wechat is config-driven and should not be blocked by RSS URL validation."""

    class FakeContentCollector:
        def __init__(self, config):
            pass

        async def collect(self, **kwargs):
            assert kwargs["channel_name"] == "wechat"
            assert kwargs["feed_url"] == ""
            return {
                "items_found": 0,
                "items_new": 0,
                "items_duplicate": 0,
                "errors": [],
            }

    monkeypatch.setattr("roxy.research.collector.ContentCollector", FakeContentCollector)

    result = CliRunner().invoke(research_cmd, ["collect", "--channel", "wechat"])

    assert result.exit_code == 0
    assert "Collection complete" in result.output
