"""Tests for v0.7.1 evolution: observer, planner, store, CLI."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from roxy.evolution.proposal import EvolutionProposal
from roxy.evolution.store import ProposalStore
from roxy.evolution.observer import EvolutionObserver
from roxy.evolution.planner import EvolutionPlanner
from roxy.cli.evolve_cmd import evolve_cmd


class TestEvolutionProposal:
    def test_has_unique_id(self):
        p1 = EvolutionProposal(target="test", title="T1")
        p2 = EvolutionProposal(target="test", title="T2")
        assert p1.id != p2.id
        assert p1.created_at

    def test_to_dict_and_from_dict(self):
        p = EvolutionProposal(
            target="context-compaction", title="Test", problem="P",
            evidence="E", risk="Medium",
            target_files=["a.py"], test_commands=["pytest"],
        )
        d = p.to_dict()
        p2 = EvolutionProposal.from_dict(d)
        assert p2.id == p.id
        assert p2.target == "context-compaction"
        assert p2.target_files == ["a.py"]

    def test_to_markdown(self):
        p = EvolutionProposal(target="test", title="T", problem="P",
                              evidence="E", proposed_change="Fix it",
                              target_files=["f.py"], test_commands=["pytest"],
                              rollback="git reset", risk="Low")
        md = p.to_markdown()
        assert "# Evolution Proposal:" in md
        assert "P" in md
        assert "f.py" in md
        assert "pytest" in md
        assert "Low" in md

    def test_status_transitions(self):
        p = EvolutionProposal(target="test")
        assert p.status == "draft"
        p.status = "patched"
        assert p.status == "patched"


class TestProposalStore:
    def test_save_and_get(self, tmp_path: Path):
        store = ProposalStore(base_dir=tmp_path)
        p = EvolutionProposal(target="test", title="Save Test")
        store.save(p)
        loaded = store.get(p.id)
        assert loaded is not None
        assert loaded.title == "Save Test"
        assert loaded.id == p.id

    def test_get_by_prefix(self, tmp_path: Path):
        store = ProposalStore(base_dir=tmp_path)
        p = EvolutionProposal(target="test", title="Prefix Test")
        store.save(p)
        # Get by short prefix
        loaded = store.get(p.id[:12])
        assert loaded is not None
        assert loaded.id == p.id

    def test_get_ambiguous_prefix_raises(self, tmp_path: Path):
        store = ProposalStore(base_dir=tmp_path)
        # Create two proposals with similar prefixes
        p1 = EvolutionProposal(id="context-compaction-20260101-abc123", target="test")
        p2 = EvolutionProposal(id="context-compaction-20260102-def456", target="test")
        store.save(p1)
        store.save(p2)
        # Short prefix should match both
        with pytest.raises(ValueError, match="matches 2 proposals"):
            store.get("context-compaction-2")

    def test_get_nonexistent(self, tmp_path: Path):
        store = ProposalStore(base_dir=tmp_path)
        assert store.get("nonexistent") is None

    def test_list_all(self, tmp_path: Path):
        store = ProposalStore(base_dir=tmp_path)
        store.save(EvolutionProposal(target="t1", title="A"))
        store.save(EvolutionProposal(target="t2", title="B"))
        assert len(store.list_all()) == 2

    def test_update_existing(self, tmp_path: Path):
        store = ProposalStore(base_dir=tmp_path)
        p = EvolutionProposal(target="test", title="Original")
        store.save(p)
        p.title = "Updated"
        p.status = "patched"
        store.save(p)
        loaded = store.get(p.id)
        assert loaded.title == "Updated"
        assert loaded.status == "patched"
        # Still only 1 record
        assert len(store.list_all()) == 1


class TestEvolutionObserver:
    def test_generate_proposal_context_compaction(self):
        obs = EvolutionObserver()
        tmpl = obs.generate_proposal("context-compaction")
        assert tmpl is not None
        assert tmpl["target"] == "context-compaction"
        assert "micro_compact" in str(tmpl["target_files"]).lower()
        assert tmpl["risk"] == "Medium"

    def test_generate_proposal_tool_descriptions(self):
        obs = EvolutionObserver()
        tmpl = obs.generate_proposal("tool-descriptions")
        assert tmpl is not None
        assert tmpl["target"] == "tool-descriptions"

    def test_generate_proposal_system_prompt(self):
        obs = EvolutionObserver()
        tmpl = obs.generate_proposal("system-prompt")
        assert tmpl is not None
        assert tmpl["risk"] == "Low"

    def test_generate_proposal_unknown_target(self):
        obs = EvolutionObserver()
        assert obs.generate_proposal("unknown") is None

    def test_generate_proposal_with_eval(self, tmp_path: Path):
        eval_path = tmp_path / "eval.json"
        eval_data = {
            "total": 3, "passed": 2, "failed": 1, "avg_score": 0.5,
            "failures": [{"case_id": "c1", "score": 0.3, "reasons": ["tool_use_match=0"]}],
            "results": [
                {"case_id": "c1", "tool_use_match": 0.0, "keyword_recall": 0.5, "passed": False},
                {"case_id": "c2", "tool_use_match": 1.0, "keyword_recall": 0.8, "passed": True},
            ],
        }
        eval_path.write_text(json.dumps(eval_data))
        obs = EvolutionObserver()
        tmpl = obs.generate_proposal("tool-descriptions", from_eval=str(eval_path))
        assert tmpl is not None
        assert "c1" in tmpl["evidence"]
        assert "c2" in tmpl["evidence"]
        assert "0.5" in tmpl["evidence"]  # avg_score

    def test_generate_proposal_missing_eval(self):
        obs = EvolutionObserver()
        with pytest.raises(FileNotFoundError):
            obs.generate_proposal("tool-descriptions", from_eval="/nonexistent.json")

    def test_read_eval_report(self, tmp_path: Path):
        path = tmp_path / "report.json"
        path.write_text(json.dumps({"avg_score": 0.8}))
        obs = EvolutionObserver()
        report = obs.read_eval_report(str(path))
        assert report["avg_score"] == 0.8

    def test_read_eval_report_missing(self):
        obs = EvolutionObserver()
        with pytest.raises(FileNotFoundError):
            obs.read_eval_report("/nonexistent.json")


class TestEvolutionPlanner:
    def test_propose_saves_and_lists(self, tmp_path: Path):
        planner = EvolutionPlanner()
        planner.store = ProposalStore(base_dir=tmp_path)
        proposal = planner.propose("tool-descriptions")
        assert proposal is not None
        assert len(planner.list_proposals()) == 1

    def test_show_proposal(self, tmp_path: Path):
        planner = EvolutionPlanner()
        planner.store = ProposalStore(base_dir=tmp_path)
        p = planner.propose("context-compaction")
        shown = planner.show_proposal(p.id)
        assert shown is not None
        assert shown.id == p.id


class TestEvolveCLI:
    def test_observe_json(self):
        result = CliRunner().invoke(evolve_cmd, ["observe", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_observe_with_missing_eval(self, tmp_path: Path):
        result = CliRunner().invoke(evolve_cmd, [
            "observe", "--from-eval", str(tmp_path / "nope.json"),
        ])
        assert result.exit_code == 1

    def test_propose_missing_eval(self, tmp_path: Path):
        result = CliRunner().invoke(evolve_cmd, [
            "propose", "--target", "tool-descriptions",
            "--from-eval", str(tmp_path / "nope.json"),
        ])
        assert result.exit_code == 1

    def test_propose_unknown_target(self):
        result = CliRunner().invoke(evolve_cmd, [
            "propose", "--target", "nonexistent",
        ])
        assert result.exit_code == 0  # prints error, not crash

    def test_propose_and_list(self, tmp_path: Path, monkeypatch):
        # Redirect store to temp dir
        from roxy.evolution import store as store_module
        monkeypatch.setattr(store_module, "roxy_home", lambda: tmp_path)

        result = CliRunner().invoke(evolve_cmd, ["propose", "--target", "system-prompt"])
        assert result.exit_code == 0
        assert "Proposal saved" in result.output

        result2 = CliRunner().invoke(evolve_cmd, ["proposals", "list"])
        assert result2.exit_code == 0
        assert "system-prompt" in result2.output

    def test_proposals_show_nonexistent(self, tmp_path: Path, monkeypatch):
        from roxy.evolution import store as store_module
        monkeypatch.setattr(store_module, "roxy_home", lambda: tmp_path)
        result = CliRunner().invoke(evolve_cmd, ["proposals", "show", "nonexistent12345"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_observe_finds_issues(self):
        result = CliRunner().invoke(evolve_cmd, ["observe"])
        assert result.exit_code == 0
        # Should find at least channel issues or KB empty
        output = result.output.lower()
        assert any(x in output for x in ["channels", "knowledge", "issue", "finding", "healthy"])

    def test_help(self):
        result = CliRunner().invoke(evolve_cmd, ["--help"])
        assert result.exit_code == 0
        assert "observe" in result.output
        assert "propose" in result.output
        assert "proposals" in result.output
