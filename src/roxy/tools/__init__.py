"""Tool system — contracts, registry, permissions, built-in tools."""

from roxy.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult
from roxy.tools.registry import ToolRegistry
from roxy.tools.permissions import PermissionManager, ApprovalMode
from roxy.tools.builtin import ReadFileTool, WebFetchTool

__all__ = [
    "BaseTool",
    "RiskLevel",
    "ToolContext",
    "ToolResult",
    "ToolRegistry",
    "PermissionManager",
    "ApprovalMode",
    "ReadFileTool",
    "WebFetchTool",
]
