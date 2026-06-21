"""ProposalStore — JSONL-based persistence for EvolutionProposals."""

from __future__ import annotations

import json
from pathlib import Path

from roxy.config.paths import roxy_home
from roxy.evolution.proposal import EvolutionProposal


class ProposalStore:
    """Store and retrieve EvolutionProposals as JSONL."""

    def __init__(self, base_dir: Path | None = None):
        self._dir = base_dir or (roxy_home() / "proposals")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "proposals.jsonl"

    def save(self, proposal: EvolutionProposal) -> None:
        proposal.updated_at = proposal.created_at if not proposal.updated_at else proposal.updated_at
        # Update if exists, else append
        all_proposals = self.list_all()
        updated = False
        for i, p in enumerate(all_proposals):
            if p.id == proposal.id:
                all_proposals[i] = proposal
                updated = True
                break
        if not updated:
            all_proposals.append(proposal)
        self._write_all(all_proposals)

    def get(self, proposal_id: str) -> EvolutionProposal | None:
        """Get a proposal by ID or unique prefix. Returns None if not found.

        Raises ValueError if prefix matches multiple proposals.
        """
        matches = []
        for p in self.list_all():
            if p.id == proposal_id:
                return p
            if p.id.startswith(proposal_id):
                matches.append(p)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            ids = ", ".join(p.id[:16] for p in matches)
            raise ValueError(
                f"Prefix '{proposal_id}' matches {len(matches)} proposals: {ids}. "
                f"Use a longer prefix."
            )
        return None

    def list_all(self) -> list[EvolutionProposal]:
        if not self._path.exists():
            return []
        proposals = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        proposals.append(EvolutionProposal.from_dict(json.loads(line)))
                    except Exception:
                        pass
        return sorted(proposals, key=lambda p: p.created_at, reverse=True)

    def _write_all(self, proposals: list[EvolutionProposal]) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            for p in proposals:
                f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")
