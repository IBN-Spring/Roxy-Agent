"""Observer — collect evidence from traces, eval reports, and system state.

v0.7.1: --from-eval properly wired through to enrich proposal evidence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EvolutionObserver:
    """Scans Roxy's runtime state for improvement opportunities."""

    def observe(self, from_eval: str = "") -> list[dict[str, Any]]:
        """Run all observations. Returns list of findings."""
        findings: list[dict[str, Any]] = []

        findings.extend(self._check_traces())
        findings.extend(self._check_eval(from_eval))
        findings.extend(self._check_channels())
        findings.extend(self._check_kb())

        return findings

    def read_eval_report(self, path: str) -> dict | None:
        """Read an eval report from a file path. Raises FileNotFoundError if missing."""
        eval_path = Path(path)
        if not eval_path.exists():
            raise FileNotFoundError(f"Eval report not found: {path}")
        with open(eval_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _check_traces(self) -> list[dict]:
        findings = []
        try:
            from roxy.evolution.tracer import TraceRecorder
            traces = TraceRecorder.list_all_traces(limit=10)
            for t in traces:
                recorder = TraceRecorder(t["session_id"])
                turns = recorder.list_turns()
                for turn in turns[-5:]:
                    if turn.get("errors"):
                        findings.append({
                            "source": "traces", "target": "error-handling",
                            "severity": "high",
                            "detail": f"Session {t['session_id'][:8]}: {turn['errors'][:100]}",
                            "trace_id": t["session_id"],
                        })
                        break
        except Exception:
            pass
        return findings

    def _check_eval(self, from_eval: str = "") -> list[dict]:
        findings = []
        report = None

        try:
            if from_eval:
                report = self.read_eval_report(from_eval)
            else:
                default = Path("eval_report.json")
                if default.exists():
                    with open(default, "r", encoding="utf-8") as f:
                        report = json.load(f)
        except FileNotFoundError:
            raise  # Re-raise for CLI to handle
        except Exception:
            return findings

        if not report:
            return findings

        try:
            failures = report.get("failures", [])
            for f in failures[:5]:
                findings.append({
                    "source": "eval", "target": "tool-descriptions",
                    "severity": "medium",
                    "detail": f"Case {f.get('case_id', '?')}: {f.get('reasons', ['unknown'])[0]}",
                    "eval_case": f.get("case_id", ""),
                    "eval_score": f.get("score"),
                })

            if report.get("avg_score", 1.0) < 0.7:
                findings.append({
                    "source": "eval", "target": "system-prompt",
                    "severity": "high",
                    "detail": f"Average eval score is low: {report['avg_score']}",
                })
        except Exception:
            pass
        return findings

    def _check_channels(self) -> list[dict]:
        findings = []
        try:
            import asyncio
            from roxy.config.loader import Config
            from roxy.research.channels import ALL_CHANNELS
            cfg = Config(); cfg.load()
            for ch in ALL_CHANNELS:
                try:
                    status, msg = asyncio.run(ch.check(cfg))
                except Exception:
                    status, msg = "error", "check failed"
                if status != "ok":
                    findings.append({
                        "source": "channels", "target": "channel-config",
                        "severity": "medium",
                        "detail": f"Channel '{ch.name}' is {status}: {msg[:100]}",
                        "channel": ch.name,
                    })
        except Exception:
            pass
        return findings

    def _check_kb(self) -> list[dict]:
        findings = []
        try:
            from roxy.knowledge.store import KnowledgeStore
            ks = KnowledgeStore(); ks.init_db()
            stats = ks.get_stats()
            if stats["entry_count"] == 0:
                findings.append({
                    "source": "knowledge", "target": "research-setup",
                    "severity": "low",
                    "detail": "Knowledge base is empty. Add feeds and collect.",
                })
        except Exception:
            pass
        return findings

    def generate_proposal(self, target: str, from_eval: str = "") -> dict | None:
        """Generate proposal for a target, enriched with real eval data."""
        now = datetime.now(timezone.utc).isoformat()

        # Read eval report for evidence
        eval_data = None
        if from_eval:
            try:
                eval_data = self.read_eval_report(from_eval)
            except FileNotFoundError:
                raise
            except Exception:
                pass

        base = _PROPOSAL_TEMPLATES.get(target)
        if not base:
            return None

        # Enrich evidence with real eval data
        evidence = base["evidence"]
        if eval_data:
            failures = eval_data.get("failures", [])
            avg = eval_data.get("avg_score", 0)
            evidence = f"Eval report '{from_eval}': avg_score={avg}, {len(failures)} failures, {eval_data.get('total', 0)} total cases.\n"
            for f in failures[:3]:
                evidence += (
                    f"- Case {f.get('case_id', '?')}: score={f.get('score')}, "
                    f"reasons={f.get('reasons', [])}\n"
                )
            # Add per-case metrics from results
            for r in eval_data.get("results", [])[:5]:
                evidence += (
                    f"- Case {r.get('case_id', '?')}: tool={r.get('tool_use_match', 0)} "
                    f"kw={r.get('keyword_recall', 0)} passed={r.get('passed')}\n"
                )

        return {
            "title": f"{base['title_prefix']} — {now[:10]}",
            "target": target,
            "problem": base["problem"],
            "evidence": evidence,
            "proposed_change": base["proposed_change"],
            "target_files": list(base["target_files"]),
            "test_commands": list(base["test_commands"]),
            "rollback": base["rollback"],
            "risk": base["risk"],
            "risk_rationale": base["risk_rationale"],
        }


_PROPOSAL_TEMPLATES = {
    "context-compaction": {
        "title_prefix": "Context Compaction Optimization",
        "problem": "AutoCompact may trigger prematurely when tool results contain large structured data, causing recent task details to be compressed.",
        "evidence": "Tool results > 4000 chars observed in traces. MicroCompact thresholds may need adjustment.",
        "proposed_change": "Adjust MicroCompact tiered thresholds and add structured summary strategy for code blocks and tool outputs.",
        "target_files": [
            "src/roxy/context/micro_compact.py",
            "src/roxy/context/auto_compact.py",
            "tests/test_context/test_micro_compact.py",
        ],
        "test_commands": [
            "python -m pytest tests/test_context/",
            "roxy eval run eval_seeds.jsonl --out candidate.json",
            "roxy eval compare baseline.json candidate.json",
        ],
        "rollback": "git branch -D evolve/context-compaction",
        "risk": "Medium",
        "risk_rationale": "Context behavior affects all chat sessions. Test thoroughly before merging.",
    },
    "tool-descriptions": {
        "title_prefix": "Tool Description Enhancement",
        "problem": "Eval cases show tool_use_match < 1.0 in some scenarios, suggesting the model does not reliably choose the correct tool.",
        "evidence": "Eval report shows tool_use_match gaps.",
        "proposed_change": "Enhance tool descriptions with concrete usage examples and trigger phrases to improve model routing.",
        "target_files": [
            "src/roxy/tools/builtin/knowledge_query.py",
            "src/roxy/tools/builtin/file_read.py",
            "src/roxy/tools/builtin/web_fetch.py",
        ],
        "test_commands": [
            "roxy eval run eval_seeds.jsonl --out candidate.json",
            "roxy eval compare baseline.json candidate.json",
        ],
        "rollback": "git checkout -- src/roxy/tools/builtin/",
        "risk": "Low",
        "risk_rationale": "Tool description changes only affect model routing, not execution behavior.",
    },
    "system-prompt": {
        "title_prefix": "System Prompt Optimization",
        "problem": "Low keyword_recall in eval suggests the system prompt may not guide the model to include expected information in responses.",
        "evidence": "Eval report keyword_recall averages below 0.7.",
        "proposed_change": "Add response quality guidelines to system prompt: source attribution, timestamps, and next-action suggestions.",
        "target_files": ["src/roxy/context/manager.py"],
        "test_commands": [
            "roxy eval run eval_seeds.jsonl --out candidate.json --live",
            "roxy eval compare baseline.json candidate.json",
        ],
        "rollback": "git checkout -- src/roxy/context/manager.py",
        "risk": "Low",
        "risk_rationale": "System prompt changes affect response style, not tool execution behavior.",
    },
}
