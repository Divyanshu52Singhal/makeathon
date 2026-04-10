"""
Aggregated Scorer: Combines black, white, and gray box scores into
a final deployability verdict.
"""

import datetime
import statistics
from collections import defaultdict
from typing import List

from agent_eval.core.base import (
    AgentInterface,
    EvalMode,
    EvaluationReport,
    FailureCategory,
    TestResult,
    TestType,
)


class AggregatedScorer:
    """
    Computes per-mode scores, weighted aggregate, and deployability verdict.

    Weights:
      Gray-box  45% (most practical, balanced)
      Black-box 30% (end-user perspective)
      White-box 25% (structural depth)
    """

    BB_WEIGHT = 0.30
    WB_WEIGHT = 0.25
    GB_WEIGHT = 0.45

    def build_report(
        self,
        agent: AgentInterface,
        results: List[TestResult],
        deploy_threshold: float,
    ) -> EvaluationReport:
        bb_results = [r for r in results if r.eval_mode == EvalMode.BLACK_BOX]
        wb_results = [r for r in results if r.eval_mode == EvalMode.WHITE_BOX]
        gb_results = [r for r in results if r.eval_mode == EvalMode.GRAY_BOX]

        bb_score = self._avg_score(bb_results)
        wb_score = self._avg_score(wb_results)
        gb_score = self._avg_score(gb_results)

        modes_present = sum([
            1 if bb_results else 0,
            1 if wb_results else 0,
            1 if gb_results else 0,
        ])

        if modes_present == 0:
            aggregated = 0.0
        elif modes_present == 1:
            aggregated = (bb_score or wb_score or gb_score)
        elif modes_present == 2:
            present = [(s, w) for s, w in [
                (bb_score, self.BB_WEIGHT),
                (wb_score, self.WB_WEIGHT),
                (gb_score, self.GB_WEIGHT),
            ] if s > 0]
            total_weight = sum(w for _, w in present)
            aggregated = sum(s * w for s, w in present) / total_weight
        else:
            aggregated = (
                bb_score * self.BB_WEIGHT
                + wb_score * self.WB_WEIGHT
                + gb_score * self.GB_WEIGHT
            )

        deployable = aggregated >= deploy_threshold

        failure_analysis = self._analyze_failures(results)
        benchmark = self._benchmark_summary(results)
        summary = self._build_summary(results, bb_score, wb_score, gb_score, aggregated)

        report = EvaluationReport(
            agent_name=agent.name,
            agent_version=agent.version,
            timestamp=datetime.datetime.now().isoformat(),
            total_scenarios=len(set(r.scenario_id for r in results)),
            results=results,
            black_box_score=round(bb_score, 2),
            white_box_score=round(wb_score, 2),
            gray_box_score=round(gb_score, 2),
            aggregated_score=round(aggregated, 2),
            deployable=deployable,
            summary=summary,
            failure_analysis=failure_analysis,
            benchmark=benchmark,
        )

        return report

    def _avg_score(self, results: List[TestResult]) -> float:
        if not results:
            return 0.0
        return statistics.mean(r.score for r in results)

    def _analyze_failures(self, results: List[TestResult]) -> List[dict]:
        failures = [r for r in results if not r.passed]
        if not failures:
            return []

        by_category = defaultdict(list)
        for f in failures:
            by_category[f.failure_category.value].append(f)

        analysis = []
        for category, items in by_category.items():
            analysis.append({
                "category": category,
                "count": len(items),
                "scenarios": [i.scenario_name for i in items],
                "avg_score": round(statistics.mean(i.score for i in items), 2),
                "recommendation": self._get_recommendation(FailureCategory(category)),
            })

        return sorted(analysis, key=lambda x: x["count"], reverse=True)

    def _get_recommendation(self, category: FailureCategory) -> str:
        recommendations = {
            FailureCategory.MODEL_LIMITATION: "Consider upgrading the model or fine-tuning on domain-specific data.",
            FailureCategory.PROMPT_DESIGN: "Refine the system prompt for clarity, structure, and edge case handling.",
            FailureCategory.TOOL_INTEGRATION: "Review tool definitions, API contracts, and error handling in tool calls.",
            FailureCategory.SCENARIO_COVERAGE: "Expand training data or add few-shot examples for uncovered scenarios.",
            FailureCategory.SECURITY_VIOLATION: "Strengthen guardrails, add refusal patterns, and review safety filters.",
            FailureCategory.NONE: "Review individual test results for specific improvement areas.",
        }
        return recommendations.get(category, "Review and iterate on agent configuration.")

    def _benchmark_summary(self, results: List[TestResult]) -> dict:
        by_type = defaultdict(list)
        for r in results:
            by_type[r.test_type.value].append(r.score)

        return {
            test_type: {
                "avg_score": round(statistics.mean(scores), 2),
                "pass_rate": round(
                    sum(1 for r in results if r.test_type.value == test_type and r.passed)
                    / len(scores) * 100,
                    1,
                ),
            }
            for test_type, scores in by_type.items()
        }

    def _build_summary(
        self,
        results: List[TestResult],
        bb: float,
        wb: float,
        gb: float,
        total: float,
    ) -> dict:
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]

        latencies = [
            r.response.latency
            for r in results
            if r.response and r.response.latency > 0
        ]

        return {
            "total_tests": len(results),
            "passed": len(passed),
            "failed": len(failed),
            "pass_rate_pct": round(len(passed) / len(results) * 100, 1) if results else 0.0,
            "avg_latency_s": round(statistics.mean(latencies), 3) if latencies else 0.0,
            "mode_scores": {
                "black_box": round(bb, 2),
                "white_box": round(wb, 2),
                "gray_box": round(gb, 2),
            },
            "aggregated_score": round(total, 2),
        }
