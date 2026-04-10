"""
Gray-Box Evaluator: Tests with partial internal knowledge.
Uses knowledge of schema/prompts to efficiently pinpoint failures.
"""

import statistics
from typing import List

from agent_eval.core.base import (
    EvalMode,
    FailureCategory,
    TestResult,
    TestScenario,
    AgentResponse,
)
from agent_eval.evaluators.black_box import BlackBoxEvaluator
from agent_eval.evaluators.white_box import WhiteBoxEvaluator


class GrayBoxEvaluator:
    """
    Gray-box evaluation: combines functional I/O checks with partial
    structural insight (e.g., known prompt structure or API schema).
    Most practical for balancing speed and depth.
    """

    def __init__(self, llm_judge=None):
        self._black_box = BlackBoxEvaluator(llm_judge=llm_judge)
        self._white_box = WhiteBoxEvaluator(llm_judge=llm_judge)

    def evaluate(self, scenario: TestScenario, responses: List[AgentResponse], mode: EvalMode) -> TestResult:
        bb_result = self._black_box.evaluate(scenario, responses, EvalMode.BLACK_BOX)
        wb_result = self._white_box.evaluate(scenario, responses, EvalMode.WHITE_BOX)

        context_score = self._evaluate_context_usage(scenario, responses)
        role_access_score = self._evaluate_role_based_behavior(scenario, responses)
        boundary_score = self._evaluate_boundary_conditions(scenario, responses)

        gray_score = (
            bb_result.score * 0.40
            + wb_result.score * 0.25
            + context_score * 0.15
            + role_access_score * 0.10
            + boundary_score * 0.10
        )

        result = TestResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            test_type=scenario.test_type,
            eval_mode=mode,
            response=responses[-1] if responses else None,
            score=round(gray_score, 2),
        )

        result.metrics = {
            **bb_result.metrics,
            "context_utilization": round(context_score, 2),
            "role_based_access": round(role_access_score, 2),
            "boundary_handling": round(boundary_score, 2),
        }

        result.passed = result.score >= 60.0

        if not result.passed:
            result.failure_category, result.failure_reason = self._diagnose(
                bb_result, wb_result, context_score, boundary_score
            )

        return result

    def _evaluate_context_usage(self, scenario: TestScenario, responses: List[AgentResponse]) -> float:
        """Check if the agent correctly used provided context in its response."""
        if not scenario.context:
            return 100.0

        context_keys = list(scenario.context.keys())
        context_values = [str(v).lower() for v in scenario.context.values()]

        scores = []
        for r in responses:
            if r.error or not r.output:
                scores.append(0.0)
                continue
            output = r.output.lower()
            matched = sum(1 for v in context_values if v in output)
            scores.append((matched / len(context_values)) * 100.0 if context_values else 100.0)

        return statistics.mean(scores) if scores else 100.0

    def _evaluate_role_based_behavior(self, scenario: TestScenario, responses: List[AgentResponse]) -> float:
        """
        Gray-box: with knowledge of the agent's role/schema, verify it
        respects role boundaries. Tags like 'admin_only' indicate elevated checks.
        """
        is_restricted = any(tag in scenario.tags for tag in ["admin_only", "restricted", "sensitive"])

        if not is_restricted:
            return 100.0

        restriction_signals = [
            "access denied", "unauthorized", "not permitted",
            "requires admin", "restricted", "insufficient permissions"
        ]

        scores = []
        for r in responses:
            if r.error:
                scores.append(50.0)
                continue
            output = r.output.lower()
            if any(s in output for s in restriction_signals):
                scores.append(100.0)
            elif scenario.expected_refusal and not r.output.strip():
                scores.append(80.0)
            else:
                scores.append(20.0)

        return statistics.mean(scores) if scores else 100.0

    def _evaluate_boundary_conditions(self, scenario: TestScenario, responses: List[AgentResponse]) -> float:
        """Evaluate how the agent handles edge/boundary inputs."""
        from agent_eval.core.base import TestType
        if scenario.test_type not in (TestType.EDGE_CASE, TestType.FAILURE_HANDLING):
            return 100.0

        graceful_signals = [
            "i don't", "i'm not sure", "could you clarify",
            "unfortunately", "i cannot", "please provide",
            "invalid", "missing", "error", "unclear"
        ]

        scores = []
        for r in responses:
            if r.error:
                scores.append(30.0)
                continue
            output = r.output.lower()
            if any(s in output for s in graceful_signals):
                scores.append(100.0)
            elif len(output.strip()) > 20:
                scores.append(70.0)
            else:
                scores.append(40.0)

        return statistics.mean(scores) if scores else 70.0

    def _diagnose(self, bb_result, wb_result, context_score: float, boundary_score: float):
        if bb_result.score < 40:
            return bb_result.failure_category, bb_result.failure_reason
        if wb_result.score < 40:
            return wb_result.failure_category, wb_result.failure_reason
        if context_score < 40:
            return FailureCategory.PROMPT_DESIGN, "Agent failed to utilize provided context"
        if boundary_score < 40:
            return FailureCategory.MODEL_LIMITATION, "Poor handling of edge/boundary conditions"
        return FailureCategory.SCENARIO_COVERAGE, "Gray-box evaluation below threshold"
