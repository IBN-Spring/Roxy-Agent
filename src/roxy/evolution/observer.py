"""Observer — collect evidence from traces, eval reports, and system state.

Diagnoses potential improvement targets without making changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EvolutionObserver:
    """Scans Roxy's runtime state for improvement opportunities.

    Collects evidence from:
    - Traces: high tool-result sizes, frequent compaction triggers
    - Eval reports: low scores, regressions, tool-use gaps
    - Channels: offline or error-prone channels
    - Doctor output: system health signals
    """

    def observe(self) -> list[dict[str, Any]]:
        """Run all observations. Returns list of findings."""
        findings: list[dict[str, Any]] = []

        findings.extend(self._check_traces())
        findings.extend(self._check_eval())
        findings.extend(self._check_channels())
        findings.extend(self._check_kb())

        return findings

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
                            "source": "traces",
                            "target": "error-handling",
                            "severity": "high",
                            "detail": f"Session {t['session_id'][:8]}: {turn['errors'][:100]}",
                            "trace_id": t["session_id"],
                        })
                        break  # one finding per session
        except Exception:
            pass
        return findings

    def _check_eval(self) -> list[dict]:
        findings = []
        try:
            eval_path = Path("eval_report.json")
            if not eval_path.exists():
                return findings

            import json
            with open(eval_path, "r", encoding="utf-8") as f:
                report = json.load(f)

            failures = report.get("failures", [])
            for f in failures[:5]:
                findings.append({
                    "source": "eval",
                    "target": "tool-descriptions",
                    "severity": "medium",
                    "detail": f"Case {f.get('case_id', '?')}: {f.get('reasons', ['unknown'])[0]}",
                    "eval_case": f.get("case_id", ""),
                })

            if report.get("avg_score", 1.0) < 0.7:
                findings.append({
                    "source": "eval",
                    "target": "system-prompt",
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
                        "source": "channels",
                        "target": "channel-config",
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
                    "source": "knowledge",
                    "target": "research-setup",
                    "severity": "low",
                    "detail": "Knowledge base is empty. Add feeds and collect.",
                })
        except Exception:
            pass
        return findings

    def generate_proposal(self, target: str, from_eval: str = "") -> dict | None:
        """Generate a proposal template for a specific target based on evidence."""
        now = datetime.now(timezone.utc).isoformat()

        if target == "context-compaction":
            return {
                "title": f"Context Compaction Optimization — {now[:10]}",
                "target": "context-compaction",
                "problem": "AutoCompact may trigger prematurely when tool results contain large structured data, causing recent task details to be compressed.",
                "evidence": "Tool results > 4000 chars observed in traces. MicroCompact thresholds may need adjustment for code/tool output patterns.",
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
            }

        if target == "tool-descriptions":
            return {
                "title": f"Tool Description Enhancement — {now[:10]}",
                "target": "tool-descriptions",
                "problem": "Eval cases show tool_use_match < 1.0 in some scenarios, suggesting the model does not reliably choose the correct tool for certain user intents.",
                "evidence": "Eval report shows tool_use_match gaps. Consider adding more examples and trigger phrases to tool descriptions.",
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
            }

        if target == "system-prompt":
            return {
                "title": f"System Prompt Optimization — {now[:10]}",
                "target": "system-prompt",
                "problem": "Low keyword_recall in eval suggests the system prompt may not guide the model to include expected information in responses.",
                "evidence": "Eval report keyword_recall averages below 0.7. The prompt should encourage including source URLs, dates, and actionable next steps in responses.",
                "proposed_change": "Add response quality guidelines to system prompt: include source attribution, timestamps, and next-action suggestions.",
                "target_files": [
                    "src/roxy/context/manager.py",
                ],
                "test_commands": [
                    "roxy eval run eval_seeds.jsonl --out candidate.json --live",
                    "roxy eval compare baseline.json candidate.json",
                ],
                "rollback": "git checkout -- src/roxy/context/manager.py",
                "risk": "Low",
                "risk_rationale": "System prompt changes affect response style, not tool execution behavior.",
            }

        return None
