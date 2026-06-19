"""ReadFileTool — read files within the workspace (risk=safe)."""

from pathlib import Path
from typing import Any

from roxy.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult


class ReadFileTool(BaseTool):
    """Read the contents of a file.

    Workspace-bounded: can only read files within the workspace root
    (with PermissionManager enforcement). Risk=safe.
    """

    name: str = "file_read"
    description: str = (
        "Read the contents of a file at the given path. "
        "Returns the file contents as text. The path must be within the workspace."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to read.",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based). Optional.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read. Optional, defaults to 2000.",
            },
        },
        "required": ["path"],
    }
    risk_level: RiskLevel = RiskLevel.safe
    workspace_bounded: bool = True

    async def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path_str = params["path"]
        offset = params.get("offset", 0)
        limit = params.get("limit", 2000)

        # Resolve path
        path = Path(path_str)
        if not path.is_absolute():
            path = ctx.workspace_root / path

        try:
            resolved = path.resolve()
        except Exception as exc:
            return ToolResult.fail(f"Cannot resolve path '{path_str}': {exc}")

        if not resolved.exists():
            return ToolResult.fail(f"File not found: {path_str}")
        if not resolved.is_file():
            return ToolResult.fail(f"Not a file: {path_str}")

        try:
            text = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = resolved.read_text(encoding="latin-1")
            except Exception as exc:
                return ToolResult.fail(f"Cannot read file (encoding error): {exc}")
        except Exception as exc:
            return ToolResult.fail(f"Cannot read file: {exc}")

        lines = text.split("\n")
        total_lines = len(lines)

        # Apply offset/limit
        start = max(0, offset - 1) if offset > 0 else 0
        end = start + limit if limit else len(lines)
        selected = lines[start:end]

        result_text = "\n".join(selected)
        if len(selected) < total_lines:
            result_text += f"\n\n[Showing lines {start + 1}–{min(end, total_lines)} of {total_lines}]"

        return ToolResult.ok(
            content=result_text,
            data={
                "path": str(resolved),
                "total_lines": total_lines,
                "start_line": start + 1,
                "end_line": min(end, total_lines),
            },
        )
