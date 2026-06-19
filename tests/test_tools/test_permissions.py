"""Tests for PermissionManager."""

from pathlib import Path

from roxy.tools.base import RiskLevel, ToolContext, ToolResult, BaseTool
from roxy.tools.permissions import PermissionManager, ApprovalMode


class _SafeReadTool(BaseTool):
    name = "safe_read"
    description = "Reads a file safely"
    risk_level = RiskLevel.safe
    workspace_bounded = True

    async def execute(self, params, ctx):
        return ToolResult.ok("read")


class _BlockedTool(BaseTool):
    name = "rm"
    description = "Remove files"
    risk_level = RiskLevel.blocked
    workspace_bounded = False

    async def execute(self, params, ctx):
        return ToolResult.ok("deleted")


class _DangerousTool(BaseTool):
    name = "unsafe_write"
    description = "Writes anywhere"
    risk_level = RiskLevel.dangerous
    workspace_bounded = False

    async def execute(self, params, ctx):
        return ToolResult.ok("written")


class TestPermissionManager:
    def test_blocked_tool_always_denied(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        result = pm.check_tool(_BlockedTool(), {})
        assert not result.allowed
        assert "blocked" in result.reason.lower()

    def test_safe_tool_in_workspace(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        (tmp_path / "test.txt").write_text("hello")
        result = pm.check_tool(_SafeReadTool(), {"path": str(tmp_path / "test.txt")})
        assert result.allowed
        assert result.risk_level == RiskLevel.safe

    def test_file_read_outside_workspace(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        # Use a path outside workspace but NOT in the blocklist
        result = pm.check_tool(_SafeReadTool(), {"path": "/tmp/somefile"})
        assert result.allowed  # read-only outside workspace is caution, not denied
        assert result.risk_level == RiskLevel.caution

    def test_blocked_system_path(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        result = pm.check_file_access(Path("/etc/passwd"), "r")
        assert not result.allowed
        assert "blocked" in result.reason.lower()

    def test_approval_mode_always(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path, approval_mode="always")
        (tmp_path / "f.txt").write_text("hi")
        result = pm.check_tool(_SafeReadTool(), {"path": str(tmp_path / "f.txt")})
        assert result.allowed
        assert result.requires_approval  # always mode requires approval even for safe

    def test_approval_mode_dangerous_only(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path, approval_mode="dangerous_only")
        (tmp_path / "f.txt").write_text("hi")
        result = pm.check_tool(_SafeReadTool(), {"path": str(tmp_path / "f.txt")})
        assert result.allowed
        assert not result.requires_approval  # safe tools don't need approval

    def test_approval_mode_none(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path, approval_mode="none")
        result = pm.check_tool(_DangerousTool(), {})
        assert result.allowed
        assert not result.requires_approval  # none mode never requires approval

    def test_dangerous_tool_needs_approval_in_default_mode(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)  # default: dangerous_only
        result = pm.check_tool(_DangerousTool(), {})
        assert result.allowed
        assert result.requires_approval
