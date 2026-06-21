"""Runner — execute test commands from an EvolutionProposal and collect results."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from roxy.evolution.proposal import EvolutionProposal


@dataclass
class TestResult:
    """Result of running one test command."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    passed: bool = False

    def __post_init__(self):
        self.passed = self.exit_code == 0


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
    """Execute test commands in an evolution workspace."""

    def __init__(self, repo_root: Path | None = None):
        self._repo = repo_root or Path.cwd()

    def run(self, proposal: EvolutionProposal) -> TestReport:
        """Execute all test commands from the proposal. Collects results."""
        results: list[TestResult] = []
        error = ""

        for cmd in proposal.test_commands:
            try:
                tr = self._run_one(cmd)
                results.append(tr)
            except Exception as exc:
                results.append(TestResult(command=cmd, exit_code=-1, stdout="", stderr=str(exc)))
                error = str(exc)

        return TestReport(proposal_id=proposal.id, results=results, error=error)

    def _run_one(self, command: str) -> TestResult:
        r = subprocess.run(
            command, shell=True, cwd=str(self._repo),
            capture_output=True, text=True, timeout=120,
        )
        return TestResult(
            command=command,
            exit_code=r.returncode,
            stdout=r.stdout[:2000],
            stderr=r.stderr[:1000],
        )
