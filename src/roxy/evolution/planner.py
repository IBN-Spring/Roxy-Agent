"""Planner — assemble observations into structured EvolutionProposals."""

from __future__ import annotations

from roxy.evolution.observer import EvolutionObserver
from roxy.evolution.proposal import EvolutionProposal
from roxy.evolution.store import ProposalStore


class EvolutionPlanner:
    """Produces structured EvolutionProposals from evidence."""

    def __init__(self):
        self.observer = EvolutionObserver()
        self.store = ProposalStore()

    def observe(self) -> list[dict]:
        """Run observation and return findings."""
        return self.observer.observe()

    def propose(self, target: str, from_eval: str = "") -> EvolutionProposal | None:
        """Generate a proposal for a specific target.

        Args:
            target: one of context-compaction, tool-descriptions, system-prompt
            from_eval: optional path to eval report for evidence enrichment
        """
        template = self.observer.generate_proposal(target, from_eval)
        if not template:
            return None

        proposal = EvolutionProposal(
            title=template["title"],
            target=template["target"],
            problem=template["problem"],
            evidence=template["evidence"],
            proposed_change=template["proposed_change"],
            target_files=template["target_files"],
            test_commands=template["test_commands"],
            rollback=template["rollback"],
            risk=template["risk"],
            risk_rationale=template["risk_rationale"],
        )

        self.store.save(proposal)
        return proposal

    def list_proposals(self) -> list[EvolutionProposal]:
        return self.store.list_all()

    def show_proposal(self, proposal_id: str) -> EvolutionProposal | None:
        return self.store.get(proposal_id)
