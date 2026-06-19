"""Tests for BaseTool, ToolResult, RiskLevel."""

import pytest

from roxy.tools.base import (
    BaseTool,
    RiskLevel,
    ToolContext,
    ToolResult,
)


class TestRiskLevel:
    def test_ordering(self):
        assert RiskLevel.safe < RiskLevel.caution
        assert RiskLevel.caution < RiskLevel.dangerous
        assert RiskLevel.dangerous < RiskLevel.blocked

    def test_safe_not_greater_than_caution(self):
        assert not RiskLevel.safe > RiskLevel.caution

    def test_le_same_level(self):
        assert RiskLevel.safe <= RiskLevel.safe


class TestToolResult:
    def test_ok(self):
        r = ToolResult.ok("done", {"lines": 42})
        assert r.success
        assert r.content == "done"
        assert r.data == {"lines": 42}
        assert r.error is None

    def test_fail(self):
        r = ToolResult.fail("not found")
        assert not r.success
        assert r.error == "not found"
        assert "not found" in r.content


class TestToolContext:
    def test_init(self, tmp_path):
        ctx = ToolContext(workspace_root=tmp_path, session_id="s1")
        assert ctx.workspace_root == tmp_path
        assert ctx.session_id == "s1"


class TestBaseToolConcrete:
    """Test BaseTool through a minimal concrete subclass."""

    class _EchoTool(BaseTool):
        name = "echo"
        description = "Echoes input"
        parameters = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }
        risk_level = RiskLevel.safe

        async def execute(self, params, ctx):
            return ToolResult.ok(f"echo: {params['text']}")

    def test_to_openai_schema(self):
        tool = self._EchoTool()
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "echo"
        assert "text" in str(schema["function"]["parameters"])

    def test_dry_run_default(self):
        tool = self._EchoTool()
        dr = tool.dry_run({"text": "hello"})
        assert "dry-run" in dr.lower()
        assert "echo" in dr

    @pytest.mark.asyncio
    async def test_execute(self, tmp_path):
        tool = self._EchoTool()
        ctx = ToolContext(workspace_root=tmp_path)
        result = await tool.execute({"text": "hello"}, ctx)
        assert result.success
        assert "echo: hello" in result.content
