"""Workspace — manage isolated git branches for evolution patches.

All evolution work happens in branches, never on main.
Each proposal gets its own branch: evolve/<proposal-id>
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorkspaceInfo:
    """State of an evolution workspace."""
    proposal_id: str = ""
    branch: str = ""
    repo_root: Path | None = None
    is_clean: bool = True
    current_branch: str = "main"


class EvolutionWorkspace:
    """Manages git branches for sandboxed evolution patches."""

    def __init__(self, repo_root: Path | None = None):
        self._repo = repo_root or self._find_repo_root()

    @staticmethod
    def _find_repo_root() -> Path:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        return Path(r.stdout.strip())

    def status(self) -> WorkspaceInfo:
        """Return current workspace state."""
        branch = self._run(["git", "branch", "--show-current"]).strip()
        is_clean = self._run(["git", "status", "--porcelain"]).strip() == ""
        return WorkspaceInfo(
            repo_root=self._repo,
            current_branch=branch or "main",
            is_clean=is_clean,
        )

    def prepare(self, proposal_id: str, force: bool = False) -> str:
        """Create an isolated branch for a proposal. Returns branch name.

        Must be on main branch. Raises RuntimeError if not.
        Raises RuntimeError if old branch exists and --force not given.
        """
        branch = f"evolve/{proposal_id}"
        current = self._run(["git", "branch", "--show-current"]).strip()

        if current != "main":
            raise RuntimeError(
                f"Must be on 'main' branch to prepare an evolution patch. "
                f"Currently on '{current}'. Run: git checkout main"
            )

        # Check if old branch exists
        existing = self._run(["git", "branch", "--list", branch]).strip()
        if existing and not force:
            raise RuntimeError(
                f"Branch '{branch}' already exists. "
                f"Use --force to overwrite, or clean up with: git branch -D {branch}"
            )

        if existing and force:
            self._run(["git", "branch", "-D", branch])

        self._run(["git", "checkout", "-b", branch])
        return branch

    def get_diff(self, proposal_id: str) -> str:
        """Get the diff of changes on the branch vs main."""
        branch = f"evolve/{proposal_id}"
        return self._run(["git", "diff", "main...HEAD"])

    def get_changed_files(self, proposal_id: str) -> list[str]:
        """List files changed on the branch."""
        branch = f"evolve/{proposal_id}"
        output = self._run(["git", "diff", "--name-only", "main...HEAD"])
        return [f.strip() for f in output.split("\n") if f.strip()]

    def checkout_main(self) -> None:
        """Return to main branch. Does NOT merge."""
        self._run(["git", "checkout", "main"])

    def merge_to_main(self, proposal_id: str) -> str:
        """Merge the evolution branch into main. Returns merge commit hash."""
        branch = f"evolve/{proposal_id}"
        self._run(["git", "checkout", "main"])
        self._run(["git", "merge", "--no-ff", branch, "-m", f"evolve: merge {proposal_id}"])
        return self._run(["git", "rev-parse", "HEAD"]).strip()[:8]

    def cleanup(self, proposal_id: str) -> None:
        """Delete the evolution branch after merge/rejection."""
        branch = f"evolve/{proposal_id}"
        self._run(["git", "branch", "-D", branch], check=False)

    def _run(self, cmd: list[str], check: bool = True) -> str:
        r = subprocess.run(
            cmd, cwd=str(self._repo), capture_output=True, text=True, timeout=30,
        )
        if check and r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or f"Command failed: {' '.join(cmd)}")
        return r.stdout
