"""ToolRegistry — register, filter, and assemble tools for model consumption."""

from __future__ import annotations

from typing import Any

from roxy.tools.base import BaseTool, RiskLevel


class ToolRegistry:
    """Holds all registered tools and provides filtered views.

    Usage:
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        tools_for_model = registry.get_for_model()
        read_tool = registry.get("file_read")
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    # ── registration ─────────────────────────────────────────────

    def register(self, tool: BaseTool) -> None:
        """Register a tool. Raises ValueError on duplicate name."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def register_all(self, tools: list[BaseTool]) -> None:
        """Register multiple tools at once."""
        for tool in tools:
            self.register(tool)

    # ── queries ──────────────────────────────────────────────────

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_for_model(self, max_risk: RiskLevel | None = None) -> list[dict[str, Any]]:
        """Return tools as OpenAI-compatible function schemas.

        Args:
            max_risk: If set, only return tools at or below this risk level.
                      Default (None) returns all tools.
        """
        tools = self._tools.values()
        if max_risk is not None:
            tools = [t for t in tools if t.risk_level <= max_risk]
        return [t.to_openai_schema() for t in tools]

    def filter_by_risk(self, max_risk: RiskLevel) -> list[BaseTool]:
        """Return tools at or below a given risk level."""
        return [t for t in self._tools.values() if t.risk_level <= max_risk]

    # ── info ─────────────────────────────────────────────────────

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    def list_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def tool_summary(self) -> list[dict[str, Any]]:
        """Return a summary of each tool (name, description, risk)."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk_level": t.risk_level.value,
                "workspace_bounded": t.workspace_bounded,
            }
            for t in sorted(self._tools.values(), key=lambda t: t.name)
        ]
