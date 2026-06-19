"""PermissionManager — gates tool execution behind workspace boundaries and risk policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from roxy.tools.base import BaseTool, RiskLevel


class ApprovalMode(Enum):
    """When to require user approval before executing a tool.

    always:         every tool (even safe) prompts for approval
    dangerous_only: only caution+ tools need approval (recommended default)
    none:           never prompt (⚠ only for trusted/automated environments)
    """

    always = "always"
    dangerous_only = "dangerous_only"
    none = "none"


# ── PermissionResult ────────────────────────────────────────────

@dataclass
class PermissionResult:
    """The outcome of a permission check.

    allowed: True if the tool can execute.
    reason: Human-readable explanation.
    risk_level: The tool's risk level.
    requires_approval: True if this needs explicit user confirmation.
    """

    allowed: bool
    reason: str
    risk_level: RiskLevel
    requires_approval: bool = False

    @classmethod
    def grant(cls, risk: RiskLevel, reason: str = "") -> "PermissionResult":
        return cls(allowed=True, reason=reason, risk_level=risk)

    @classmethod
    def deny(cls, risk: RiskLevel, reason: str) -> "PermissionResult":
        return cls(allowed=False, reason=reason, risk_level=risk)


# ── PermissionManager ───────────────────────────────────────────

class PermissionManager:
    """Gates tool execution behind workspace boundaries, risk policy, and blocklists.

    Usage:
        pm = PermissionManager(workspace_root=Path.cwd(), approval_mode="dangerous_only")
        result = pm.check_tool(tool, {"path": "/etc/passwd"}, ctx)
        if not result.allowed:
            raise PermissionError(result.reason)
        if result.requires_approval:
            approved = await pm.request_approval(tool, params)
    """

    # Commands/patterns always blocked in file paths
    BLOCKED_PATH_PATTERNS: list[str] = [
        # System-critical paths
        "/etc/passwd", "/etc/shadow", "/etc/sudoers",
        # Windows system
        "C:\\Windows\\System32", "C:\\Windows\\System",
        # Generic dangerous patterns
        "/dev/", "/proc/", "/sys/",
    ]

    def __init__(
        self,
        workspace_root: Path | None = None,
        approval_mode: str = "dangerous_only",
    ):
        self.workspace_root = workspace_root or Path.cwd().resolve()
        self.approval_mode = ApprovalMode(approval_mode)

    # ── public API ───────────────────────────────────────────────

    def check_tool(
        self,
        tool: BaseTool,
        params: dict[str, Any],
        ctx: Any = None,
    ) -> PermissionResult:
        """Check whether a tool can execute with the given parameters.

        Returns a PermissionResult — callers MUST respect it.
        """
        # 1. Blocked-level tools are never allowed
        if tool.risk_level == RiskLevel.blocked:
            return PermissionResult.deny(
                RiskLevel.blocked,
                f"Tool '{tool.name}' is permanently blocked by policy.",
            )

        # 2. Start with tool's declared risk; may be elevated by path checks
        effective_risk = tool.risk_level

        # 3. Workspace check for bounded tools
        if tool.workspace_bounded:
            path = params.get("path") or params.get("file_path") or params.get("file")
            if path:
                path_result = self.check_file_access(Path(path), "r")
                if not path_result.allowed:
                    return path_result
                # Elevate risk if the path check found a higher level
                if path_result.risk_level > effective_risk:
                    effective_risk = path_result.risk_level

        # 4. Determine if approval is required
        requires_approval = self._needs_approval(effective_risk)

        return PermissionResult(
            allowed=True,
            reason="ok",
            risk_level=effective_risk,
            requires_approval=requires_approval,
        )

    def check_file_access(self, path: Path, mode: str = "r") -> PermissionResult:
        """Check whether a file path is safe to access.

        Rules:
        1. Path must resolve within workspace_root (symlink-aware).
        2. Path must not match any BLOCKED_PATH_PATTERNS.
        3. Write mode on files outside workspace is denied.
        """
        try:
            resolved = path.resolve()
        except Exception:
            return PermissionResult.deny(
                RiskLevel.blocked,
                f"Cannot resolve path: {path}",
            )

        # Check blocked patterns
        path_str = str(resolved).replace("\\", "/")
        for pattern in self.BLOCKED_PATH_PATTERNS:
            if pattern.replace("\\", "/") in path_str:
                return PermissionResult.deny(
                    RiskLevel.blocked,
                    f"Access to '{path}' is blocked (matches protected path pattern).",
                )

        # Check workspace containment
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError:
            # Outside workspace — only allow read-only access
            if "w" in mode or "a" in mode or "x" in mode:
                return PermissionResult.deny(
                    RiskLevel.dangerous,
                    f"Write access to '{path}' is denied (outside workspace).",
                )
            # Read-only outside workspace is caution-level
            return PermissionResult(
                allowed=True,
                reason=f"Read-only access outside workspace: {path}",
                risk_level=RiskLevel.caution,
                requires_approval=self._needs_approval(RiskLevel.caution),
            )

        return PermissionResult.grant(RiskLevel.safe)

    # ── helpers ──────────────────────────────────────────────────

    def _needs_approval(self, risk: RiskLevel) -> bool:
        """Return True if this risk level requires user approval under current mode."""
        if self.approval_mode == ApprovalMode.none:
            return False
        if self.approval_mode == ApprovalMode.always:
            return True
        # dangerous_only: approve if risk >= caution
        return risk != RiskLevel.safe
