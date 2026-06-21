"""Runner — execute test commands from an EvolutionProposal and collect results.

v0.8.1: no shell=True, command allowlist enforced, shlex-based parsing.
"""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from roxy.evolution.proposal import EvolutionProposal

logger = logging.getLogger(__name__)

# Only these command prefixes are allowed. Everything else needs approval.
ALLOWED_COMMAND_PREFIXES: list[str] = [
    "python -m pytest",
    "python -m roxy eval run",
    "python -m roxy eval compare",
    "python -m roxy dev check",
    "python -m roxy doctor",
    "pytest",
    "roxy eval run",
    "roxy eval compare",
    "roxy dev check",
    "roxy doctor",
]


@dataclass
class TestResult:
    """Result of running one test command."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    passed: bool = False
    blocked: bool = False  # True if blocked by allowlist

    def __post_init__(self):
        self.passed = self.exit_code == 0 and not self.blocked


@dataclass
class TestReport:
    """Aggregate test results for a proposal."""
    proposal_id: str
    results: list[TestResult] = field(default_factory=list)
    all_passed: bool = True
    error: str = ""

    def __post_init__(self):
        if self.results:
            self.all_passed = all(r.passed for r in self.results)


class EvolutionRunner:
    """Execute test commands in an evolution workspace. No shell=True."""

    def __init__(self, repo_root: Path | None = None):
        self._repo = repo_root or Path.cwd()

    # Shell metacharacters that indicate injection/chain attempts
    DANGEROUS_CHARS = re.compile(r"[;&|`$(){}\[\]<>]")

    @classmethod
    def is_allowed(cls, command: str) -> bool:
        """Check if a command is in the allowlist and free of shell metacharacters."""
        cmd_stripped = command.strip()
        # Block commands containing shell metacharacters
        if cls.DANGEROUS_CHARS.search(cmd_stripped):
            return False
        for prefix in ALLOWED_COMMAND_PREFIXES:
            if cmd_stripped.startswith(prefix):
                return True
        return False

    def run(self, proposal: EvolutionProposal) -> TestReport:
        """Execute all test commands. Blocked commands are skipped with warning."""
        results: list[TestResult] = []
        error = ""

        for cmd in proposal.test_commands:
            # Check allowlist
            if not self.is_allowed(cmd):
                blocked = TestResult(
                    command=cmd, exit_code=-1, stdout="",
                    stderr=(f"Command blocked by allowlist: '{cmd}'. "
                            f"Only pre-approved test commands can run automatically. "
                            f"Allowed prefixes: {', '.join(ALLOWED_COMMAND_PREFIXES[:5])}..."),
                    blocked=True,
                )
                results.append(blocked)
                logger.warning(f"Blocked command: {cmd}")
                continue

            try:
                tr = self._run_one(cmd)
                results.append(tr)
            except Exception as exc:
                results.append(TestResult(command=cmd, exit_code=-1, stdout="", stderr=str(exc)))
                error = str(exc)

        return TestReport(proposal_id=proposal.id, results=results, error=error)

    def _run_one(self, command: str) -> TestResult:
        """Execute a single command safely using shlex.split — no shell=True."""
        try:
            args = shlex.split(command)
        except ValueError:
            return TestResult(
                command=command, exit_code=-1, stdout="",
                stderr=f"Cannot parse command: {command}", blocked=True,
            )

        r = subprocess.run(
            args, cwd=str(self._repo), capture_output=True, text=True, timeout=120,
        )
        return TestResult(
            command=command, exit_code=r.returncode,
            stdout=r.stdout[:2000], stderr=r.stderr[:1000],
        )
