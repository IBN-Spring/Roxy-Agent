"""EvolutionProposal — structured source-level improvement RFC."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class EvolutionProposal:
    """A structured, source-level improvement proposal.

    Generated from evidence (traces, eval reports, doctor checks).
    Human review required before any code change.
    """

    id: str = ""
    title: str = ""
    status: str = "draft"  # draft | patched | tested | merged | rejected
    target: str = ""       # system-prompt | tool-descriptions | context-compaction | ...
    created_at: str = ""
    updated_at: str = ""

    # v0.8: patch execution state
    patch_status: str = ""    # prepared | applied | failed
    test_status: str = ""     # pending | passed | failed
    report_path: str = ""     # path to patch report markdown
    branch: str = ""          # git branch name

    # Evidence
    problem: str = ""      # What is wrong
    evidence: str = ""     # Data backing the claim (trace ids, eval case ids, metrics)

    # Plan
    proposed_change: str = ""      # Human-readable description of the fix
    target_files: list[str] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=list)
    rollback: str = ""

    # Risk
    risk: str = "Low"      # Low | Medium | High
    risk_rationale: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.target}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "status": self.status,
            "target": self.target, "created_at": self.created_at,
            "updated_at": self.updated_at,
            "patch_status": self.patch_status, "test_status": self.test_status,
            "report_path": self.report_path, "branch": self.branch,
            "problem": self.problem, "evidence": self.evidence,
            "proposed_change": self.proposed_change,
            "target_files": self.target_files,
            "test_commands": self.test_commands,
            "rollback": self.rollback,
            "risk": self.risk, "risk_rationale": self.risk_rationale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvolutionProposal":
        return cls(
            id=d.get("id", ""), title=d.get("title", ""),
            status=d.get("status", "draft"), target=d.get("target", ""),
            created_at=d.get("created_at", ""), updated_at=d.get("updated_at", ""),
            patch_status=d.get("patch_status", ""), test_status=d.get("test_status", ""),
            report_path=d.get("report_path", ""), branch=d.get("branch", ""),
            problem=d.get("problem", ""), evidence=d.get("evidence", ""),
            proposed_change=d.get("proposed_change", ""),
            target_files=d.get("target_files", []),
            test_commands=d.get("test_commands", []),
            rollback=d.get("rollback", ""),
            risk=d.get("risk", "Low"), risk_rationale=d.get("risk_rationale", ""),
        )

    def to_markdown(self) -> str:
        """Render as a structured RFC markdown document."""
        lines = [
            f"# Evolution Proposal: {self.id}",
            "",
            f"**Status**: {self.status} | **Target**: {self.target} | **Risk**: {self.risk}",
            f"**Created**: {self.created_at[:19]}",
            "",
            "## Problem",
            self.problem,
            "",
            "## Evidence",
            self.evidence,
            "",
            "## Proposed Change",
            self.proposed_change,
            "",
            "## Target Files",
        ]
        for f in sorted(self.target_files):
            lines.append(f"- `{f}`")
        lines.append("")
        lines.append("## Test Commands")
        for cmd in self.test_commands:
            lines.append(f"- `{cmd}`")
        lines.append("")
        lines.append("## Rollback")
        lines.append(self.rollback)
        lines.append("")
        lines.append("## Risk Assessment")
        lines.append(f"**Level**: {self.risk}")
        lines.append(self.risk_rationale)
        return "\n".join(lines)
