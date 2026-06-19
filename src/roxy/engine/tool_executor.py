"""ToolExecutor — execute tool calls in parallel with permission gating."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from roxy.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult
from roxy.tools.permissions import PermissionManager
from roxy.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ToolCallResult:
    """The outcome of a single tool call within a batch."""

    tool_name: str
    call_id: str
    result: ToolResult
    approved: bool = True
    denied_reason: str = ""


@dataclass
class BatchResult:
    """The outcome of executing a batch of tool calls."""

    results: list[ToolCallResult] = field(default_factory=list)
    denied_count: int = 0
    error_count: int = 0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.result.success)

    @property
    def total(self) -> int:
        return len(self.results)


class ToolExecutor:
    """Executes tool calls emitted by the model.

    Responsibilities:
    1. Look up each tool in the registry.
    2. Check permissions via PermissionManager.
    3. Execute independent calls in parallel (asyncio.gather).
    4. Collect and return results.

    Usage:
        executor = ToolExecutor(registry, permissions, ctx)
        batch = await executor.execute_batch(tool_calls_from_model)
    """

    def __init__(
        self,
        registry: ToolRegistry,
        permissions: PermissionManager,
        ctx: ToolContext,
    ):
        self.registry = registry
        self.permissions = permissions
        self.ctx = ctx

    async def execute_batch(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> BatchResult:
        """Execute a batch of tool calls in parallel.

        Args:
            tool_calls: List of tool call dicts in OpenAI format:
                [{"id": "call_xxx", "function": {"name": "...", "arguments": "..."}}]

        Returns:
            BatchResult with one ToolCallResult per tool call.
        """
        if not tool_calls:
            return BatchResult()

        # Create a task for each tool call
        tasks = [self._execute_one(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        batch = BatchResult()
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                tc = tool_calls[i]
                batch.results.append(
                    ToolCallResult(
                        tool_name=tc.get("function", {}).get("name", "unknown"),
                        call_id=tc.get("id", ""),
                        result=ToolResult.fail(str(result)),
                        denied_reason=str(result),
                    )
                )
                batch.error_count += 1
            else:
                batch.results.append(result)
                if not result.approved:
                    batch.denied_count += 1
                if not result.result.success:
                    batch.error_count += 1

        return batch

    async def _execute_one(self, tool_call: dict[str, Any]) -> ToolCallResult:
        """Execute a single tool call: lookup → permission check → execute."""
        call_id = tool_call.get("id", "")
        func = tool_call.get("function", {})
        tool_name = func.get("name", "")
        arguments_str = func.get("arguments", "{}")

        # Parse arguments
        import json

        try:
            params = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
        except json.JSONDecodeError as exc:
            return ToolCallResult(
                tool_name=tool_name,
                call_id=call_id,
                result=ToolResult.fail(f"Invalid JSON arguments: {exc}"),
                denied_reason="bad_arguments",
            )

        # Look up tool
        tool = self.registry.get(tool_name)
        if tool is None:
            return ToolCallResult(
                tool_name=tool_name,
                call_id=call_id,
                result=ToolResult.fail(f"Unknown tool: '{tool_name}'"),
                denied_reason="unknown_tool",
            )

        # Permission check
        perm_result = self.permissions.check_tool(tool, params, self.ctx)
        if not perm_result.allowed:
            logger.warning(f"Tool '{tool_name}' denied: {perm_result.reason}")
            return ToolCallResult(
                tool_name=tool_name,
                call_id=call_id,
                result=ToolResult.fail(f"Permission denied: {perm_result.reason}"),
                approved=False,
                denied_reason=perm_result.reason,
            )

        # Execute
        try:
            result = await tool.execute(params, self.ctx)
            return ToolCallResult(
                tool_name=tool_name,
                call_id=call_id,
                result=result,
            )
        except Exception as exc:
            logger.error(f"Tool '{tool_name}' execution error: {exc}")
            return ToolCallResult(
                tool_name=tool_name,
                call_id=call_id,
                result=ToolResult.fail(str(exc)),
                denied_reason="execution_error",
            )
