"""BaseTool ABC — the contract every Roxy tool must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RiskLevel(Enum):
    """How dangerous a tool execution could be.

    Used by PermissionManager to gate execution:
      - safe:       never needs approval (e.g., file_read, web_fetch GET)
      - caution:    needs approval in "always" mode (e.g., file_write in workspace)
      - dangerous:  always needs approval unless mode is "none" (e.g., bash with network)
      - blocked:    never approved — permanently rejected
    """

    safe = "safe"
    caution = "caution"
    dangerous = "dangerous"
    blocked = "blocked"

    def __lt__(self, other: RiskLevel) -> bool:
        order = {"safe": 0, "caution": 1, "dangerous": 2, "blocked": 3}
        return order[self.value] < order[other.value]

    def __le__(self, other: RiskLevel) -> bool:
        return self == other or self < other


# ── ToolContext ──────────────────────────────────────────────────

@dataclass
class ToolContext:
    """Context passed to every tool execution.

    Carries the workspace root (for sandbox checks), the current session id,
    and a reference to PermissionManager so tools can self-check.
    """

    workspace_root: Path
    session_id: str = ""
    permissions: Any = None  # PermissionManager reference (avoid circular import)


# ── ToolResult ───────────────────────────────────────────────────

@dataclass
class ToolResult:
    """The outcome of a tool execution.

    Fields:
        success: True if the tool completed its task.
        content: Human-readable output (shown to the model and user).
        data: Structured data for programmatic consumption (optional).
        error: Error message if success is False.
    """

    success: bool
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def ok(cls, content: str, data: dict[str, Any] | None = None) -> "ToolResult":
        return cls(success=True, content=content, data=data or {})

    @classmethod
    def fail(cls, error: str, content: str = "") -> "ToolResult":
        return cls(success=False, content=content or error, error=error)


# ── BaseTool ─────────────────────────────────────────────────────

class BaseTool(ABC):
    """Abstract base class for all Roxy tools.

    Every tool must declare its risk level, whether it is workspace-bounded,
    and its JSON Schema parameters. This contract enables the PermissionManager
    to gate execution before any code runs.

    Subclasses override `execute()` and optionally `dry_run()`.
    """

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}  # JSON Schema for the model
    risk_level: RiskLevel = RiskLevel.safe
    workspace_bounded: bool = True  # True if confined to workspace root

    @abstractmethod
    async def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Execute the tool. Called after permission checks pass."""
        ...

    def dry_run(self, params: dict[str, Any]) -> str:
        """Return a human-readable description of what WOULD happen.

        Required for caution+ tools. The default is a simple summary.
        """
        return f"[dry-run] {self.name}: {self.description} with params {params}"

    def to_openai_schema(self) -> dict[str, Any]:
        """Return an OpenAI-compatible function schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
