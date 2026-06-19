"""Tests for ToolRegistry."""

import pytest

from roxy.tools.base import RiskLevel, ToolContext, ToolResult, BaseTool
from roxy.tools.registry import ToolRegistry


class _SafeTool(BaseTool):
    name = "safe_tool"
    description = "A safe tool"
    risk_level = RiskLevel.safe

    async def execute(self, params, ctx):
        return ToolResult.ok("safe")


class _DangerousTool(BaseTool):
    name = "dangerous_tool"
    description = "A dangerous tool"
    risk_level = RiskLevel.dangerous

    async def execute(self, params, ctx):
        return ToolResult.ok("danger")


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = _SafeTool()
        reg.register(tool)
        assert reg.get("safe_tool") is tool

    def test_register_duplicate_raises(self):
        reg = ToolRegistry()
        reg.register(_SafeTool())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_SafeTool())

    def test_register_all(self):
        reg = ToolRegistry()
        reg.register_all([_SafeTool(), _DangerousTool()])
        assert reg.tool_count == 2

    def test_get_missing(self):
        reg = ToolRegistry()
        assert reg.get("nope") is None

    def test_get_all(self):
        reg = ToolRegistry()
        reg.register(_SafeTool())
        reg.register(_DangerousTool())
        assert len(reg.get_all()) == 2

    def test_get_for_model(self):
        reg = ToolRegistry()
        reg.register(_SafeTool())
        schemas = reg.get_for_model()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "safe_tool"

    def test_get_for_model_filters_by_risk(self):
        reg = ToolRegistry()
        reg.register(_SafeTool())
        reg.register(_DangerousTool())

        # max_risk=safe should only return safe tools
        safe_only = reg.get_for_model(max_risk=RiskLevel.safe)
        assert len(safe_only) == 1
        assert safe_only[0]["function"]["name"] == "safe_tool"

        # max_risk=dangerous should return both (since safe < dangerous)
        all_tools = reg.get_for_model(max_risk=RiskLevel.dangerous)
        assert len(all_tools) == 2

    def test_filter_by_risk(self):
        reg = ToolRegistry()
        reg.register(_SafeTool())
        reg.register(_DangerousTool())
        safe = reg.filter_by_risk(RiskLevel.safe)
        assert len(safe) == 1

    def test_list_names(self):
        reg = ToolRegistry()
        reg.register(_DangerousTool())
        reg.register(_SafeTool())
        assert reg.list_names() == ["dangerous_tool", "safe_tool"]

    def test_tool_summary(self):
        reg = ToolRegistry()
        reg.register(_SafeTool())
        summary = reg.tool_summary()
        assert len(summary) == 1
        assert summary[0]["name"] == "safe_tool"
        assert summary[0]["risk_level"] == "safe"
