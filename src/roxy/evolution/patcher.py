"""Patcher — apply deterministic code changes based on EvolutionProposal targets.

v0.8: structured, predictable patches for 3 target types.
Does NOT use LLM to generate arbitrary code. Each patch type is
a known, reviewable transformation applied to specific files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roxy.evolution.proposal import EvolutionProposal
from roxy.evolution.workspace import EvolutionWorkspace


class EvolutionPatcher:
    """Applies deterministic patches in an isolated workspace."""

    def __init__(self, workspace: EvolutionWorkspace | None = None):
        self.ws = workspace or EvolutionWorkspace()

    def prepare(self, proposal: EvolutionProposal) -> str:
        """Create isolated branch. Returns branch name."""
        return self.ws.prepare(proposal.id)

    def apply(self, proposal: EvolutionProposal) -> dict[str, Any]:
        """Apply the patch described in the proposal. Returns patch result.

        Returns: {success, files_changed, error}
        """
        target = proposal.target
        repo = self.ws._repo

        if target == "context-compaction":
            return self._patch_context_compaction(repo)
        elif target == "tool-descriptions":
            return self._patch_tool_descriptions(repo)
        elif target == "system-prompt":
            return self._patch_system_prompt(repo)
        else:
            return {"success": False, "files_changed": [], "error": f"Unknown target: {target}"}

    def _patch_context_compaction(self, repo: Path) -> dict:
        """Adjust MicroCompact thresholds for large tool outputs."""
        changed = []
        try:
            micro_path = repo / "src" / "roxy" / "context" / "micro_compact.py"
            if not micro_path.exists():
                return {"success": False, "files_changed": [], "error": f"File not found: {micro_path}"}

            content = micro_path.read_text(encoding="utf-8")
            # Deterministic patch: increase max chars for fresh tool results
            updated = content.replace(
                "MAX_TOOL_RESULT_CHARS: int = 4000",
                "MAX_TOOL_RESULT_CHARS: int = 6000",
            ).replace(
                "MAX_OLD_TOOL_RESULT_CHARS: int = 1500",
                "MAX_OLD_TOOL_RESULT_CHARS: int = 2500",
            )
            if updated != content:
                micro_path.write_text(updated, encoding="utf-8")
                changed.append(str(micro_path.relative_to(repo)))

            # Also update auto-compact threshold if needed
            auto_path = repo / "src" / "roxy" / "context" / "auto_compact.py"
            if auto_path.exists():
                auto_content = auto_path.read_text(encoding="utf-8")
                updated_auto = auto_content.replace(
                    "AUTOCOMPACT_TOKEN_THRESHOLD: int = 40_000",
                    "AUTOCOMPACT_TOKEN_THRESHOLD: int = 50_000",
                )
                if updated_auto != auto_content:
                    auto_path.write_text(updated_auto, encoding="utf-8")
                    changed.append(str(auto_path.relative_to(repo)))

            return {"success": len(changed) > 0, "files_changed": changed, "error": ""}
        except Exception as exc:
            return {"success": False, "files_changed": changed, "error": str(exc)}

    def _patch_tool_descriptions(self, repo: Path) -> dict:
        """Enhance tool descriptions with usage examples."""
        changed = []
        try:
            tools_dir = repo / "src" / "roxy" / "tools" / "builtin"
            enhancements = {
                "knowledge_query.py": (
                    'description: str = (\n        "Search the Roxy knowledge base',
                    'description: str = (\n        "Search the Roxy knowledge base for stored research items. '
                    'Use this when the user asks about topics you have previously collected, '
                    'wants to find articles, or needs to recall stored information. '
                    'Examples: /kb protein folding, what have I collected about AI?"\n'
                    '        "Search the Roxy knowledge base'
                ),
                "file_read.py": (
                    'description: str = (\n        "Read the contents of a file',
                    'description: str = (\n        "Read the contents of a file at the given path. '
                    'Use this when the user asks you to read, open, or show a file. '
                    'Examples: read AGENTS.md, show me the config file."\n'
                    '        "Read the contents of a file'
                ),
                "web_fetch.py": (
                    'description: str = (\n        "Fetch the content',
                    'description: str = (\n        "Fetch the content of a web page and return it as readable text. '
                    'Use this when the user asks you to check a URL, read an article, '
                    'or get information from a webpage. Examples: fetch https://example.com."\n'
                    '        "Fetch the content'
                ),
            }
            # v0.8.1 fix: use marker check instead of flawed substring logic
            _MARKERS = {
                "knowledge_query.py": "Examples: /kb protein folding",
                "file_read.py": "Examples: read AGENTS.md",
                "web_fetch.py": "Examples: fetch https://example.com",
            }
            for filename, (old, new) in enhancements.items():
                path = tools_dir / filename
                if not path.exists():
                    continue
                content = path.read_text(encoding="utf-8")
                # Check that old fragment exists AND marker is not yet present
                marker = _MARKERS.get(filename, "")
                if old in content and marker not in content:
                    updated = content.replace(old, new, 1)
                    path.write_text(updated, encoding="utf-8")
                    changed.append(str(path.relative_to(repo)))

            return {"success": len(changed) > 0, "files_changed": changed, "error": ""}
        except Exception as exc:
            return {"success": False, "files_changed": changed, "error": str(exc)}

    def _patch_system_prompt(self, repo: Path) -> dict:
        """Add response quality guidelines to system prompt."""
        changed = []
        try:
            mgr_path = repo / "src" / "roxy" / "context" / "manager.py"
            if not mgr_path.exists():
                return {"success": False, "files_changed": [], "error": f"File not found: {mgr_path}"}

            content = mgr_path.read_text(encoding="utf-8")
            snippet = 'You have access to tools'
            guideline = (
                'When responding, include source attribution (URLs), relevant dates, '
                'and actionable next steps when applicable. '
                'You have access to tools'
            )
            if snippet in content and guideline not in content:
                updated = content.replace(snippet, guideline)
                mgr_path.write_text(updated, encoding="utf-8")
                changed.append(str(mgr_path.relative_to(repo)))

            return {"success": len(changed) > 0, "files_changed": changed, "error": ""}
        except Exception as exc:
            return {"success": False, "files_changed": changed, "error": str(exc)}
