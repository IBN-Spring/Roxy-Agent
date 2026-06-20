"""EvalRunner — run eval cases against the current agent and produce metrics.

v0.5.1: baseline evaluation only. No optimization.
Uses a mock provider by default; --live required for real API calls.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EvalCase:
    """One evaluation test case."""

    id: str = ""
    task_input: str = ""
    expected_tools: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    disallowed_behavior: list[str] = field(default_factory=list)
    difficulty: str = "easy"
    category: str = ""
    source: str = ""
    source_trace_id: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "EvalCase":
        return cls(
            id=d.get("id", ""),
            task_input=d.get("task_input", ""),
            expected_tools=d.get("expected_tools", []),
            expected_keywords=d.get("expected_keywords", d.get("expected_behavior", "").split() if isinstance(d.get("expected_behavior"), str) else []),
            disallowed_behavior=d.get("disallowed_behavior", []),
            difficulty=d.get("difficulty", "easy"),
            category=d.get("category", ""),
            source=d.get("source", ""),
            source_trace_id=d.get("source_trace_id", ""),
        )


@dataclass
class EvalResult:
    """Result of running one eval case."""

    case_id: str
    task_input: str = ""
    passed: bool = False
    tool_use_match: float = 0.0     # 0..1 — did it use the expected tools?
    keyword_recall: float = 0.0      # 0..1 — did response contain expected keywords?
    no_error: bool = True
    latency_seconds: float = 0.0
    final_score: float = 0.0
    model_used: str = ""
    response: str = ""
    errors: str = ""
    tools_used: list[str] = field(default_factory=list)


class MockProvider:
    """Mock LLM provider for eval without real API calls."""

    async def complete(self, prompt, messages=None, system=None, model=None):
        return "This is a mock response for eval testing."


class EvalRunner:
    """Run eval cases and produce a baseline report."""

    def __init__(self, live: bool = False):
        self.live = live
        self.results: list[EvalResult] = []

    def load_cases(self, path: Path) -> list[EvalCase]:
        cases = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    case = EvalCase.from_dict(data)
                    if not case.id:
                        case.id = f"case_{len(cases) + 1}"
                    cases.append(case)
                except json.JSONDecodeError:
                    pass
        return cases

    async def run(self, cases: list[EvalCase], model: str = "mock") -> list[EvalResult]:
        """Run all eval cases and return results."""
        self.results = []
        for case in cases:
            result = await self._run_one(case, model)
            self.results.append(result)
        return self.results

    async def _run_one(self, case: EvalCase, model: str) -> EvalResult:
        t_start = time.time()

        if self.live:
            # Real LLM call
            try:
                from roxy.config.loader import Config
                from roxy.models.provider import ModelProvider, ProviderError
                cfg = Config()
                cfg.load()
                provider = ModelProvider(cfg)
                response = await provider.complete(case.task_input, model=model or None)
                errors = ""
                tools_used: list[str] = []
            except ProviderError as exc:
                response = ""
                errors = exc.message
                tools_used = []
            except Exception as exc:
                response = ""
                errors = str(exc)
                tools_used = []
        else:
            # Mock: simulate a response
            mp = MockProvider()
            response = await mp.complete(case.task_input)
            errors = ""
            tools_used = case.expected_tools[:1] if case.expected_tools else []

        latency = round(time.time() - t_start, 3)

        # Score
        tool_use_match = self._score_tools(tools_used, case.expected_tools)
        keyword_recall = self._score_keywords(response, case.expected_keywords)
        no_error = (errors == "")

        final_score = round((tool_use_match * 0.3 + keyword_recall * 0.5 + (1.0 if no_error else 0.0) * 0.2), 3)

        return EvalResult(
            case_id=case.id, task_input=case.task_input[:120],
            passed=final_score >= 0.5,
            tool_use_match=tool_use_match, keyword_recall=keyword_recall,
            no_error=no_error, latency_seconds=latency,
            final_score=final_score, model_used="mock" if not self.live else model,
            response=response[:500], errors=errors, tools_used=tools_used,
        )

    @staticmethod
    def _score_tools(used: list[str], expected: list[str]) -> float:
        if not expected:
            return 1.0
        used_set = set(used)
        expected_set = set(expected)
        if not expected_set:
            return 1.0
        return len(used_set & expected_set) / len(expected_set)

    @staticmethod
    def _score_keywords(response: str, keywords: list[str]) -> float:
        if not keywords:
            return 1.0
        response_lower = response.lower()
        hits = sum(1 for kw in keywords if kw.lower() in response_lower)
        return hits / len(keywords)

    def build_report(self, model: str = "mock") -> dict:
        """Build a summary report from results."""
        if not self.results:
            return {"total": 0, "passed": 0, "failed": 0, "avg_score": 0}

        scores = [r.final_score for r in self.results]
        passed = sum(1 for r in self.results if r.passed)
        avg_latency = sum(r.latency_seconds for r in self.results) / len(self.results)

        failures = []
        for r in self.results:
            if not r.passed:
                reasons = []
                if r.tool_use_match < 0.5:
                    reasons.append(f"tool_use_match={r.tool_use_match}")
                if r.keyword_recall < 0.5:
                    reasons.append(f"keyword_recall={r.keyword_recall}")
                if not r.no_error:
                    reasons.append(f"errors: {r.errors[:60]}")
                failures.append({"case_id": r.case_id, "reasons": reasons, "score": r.final_score})

        return {
            "model": model,
            "live": self.live,
            "total": len(self.results),
            "passed": passed,
            "failed": len(self.results) - passed,
            "avg_score": round(sum(scores) / len(scores), 3),
            "avg_latency": round(avg_latency, 3),
            "min_score": round(min(scores), 3),
            "max_score": round(max(scores), 3),
            "failures": failures,
            "results": [
                {
                    "case_id": r.case_id,
                    "task_input": r.task_input,
                    "passed": r.passed,
                    "tool_use_match": r.tool_use_match,
                    "keyword_recall": r.keyword_recall,
                    "no_error": r.no_error,
                    "final_score": r.final_score,
                    "latency": r.latency_seconds,
                    "tools_used": r.tools_used,
                }
                for r in self.results
            ],
        }
