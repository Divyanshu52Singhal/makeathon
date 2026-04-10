"""
White-Box Evaluator: Tests with full internal knowledge.
Inspects reasoning traces, tool calls, and structural logic.
"""

import re
import statistics
from typing import List

from agent_eval.core.base import (
    AgentResponse,
    EvalMode,
    FailureCategory,
    TestResult,
    TestScenario,
)
from agent_eval.evaluators.black_box import BlackBoxEvaluator


class WhiteBoxEvaluator:
    """
    Evaluates the agent using full internal access:
    reasoning traces, tool usage, token budgets, and structural coverage.
    Extends black-box checks with deep structural analysis.
    """

    def __init__(self, llm_judge=None):
        self._black_box = BlackBoxEvaluator(llm_judge=llm_judge)

    def evaluate(self, scenario: TestScenario, responses: List[AgentResponse], mode: EvalMode) -> TestResult:
        result = self._black_box.evaluate(scenario, responses, mode)
        result.eval_mode = mode

        bb_score = result.score
        structural_score = self._evaluate_structural(scenario, responses)
        trace_score = self._evaluate_traces(scenario, responses)
        tool_score = self._evaluate_tool_usage(scenario, responses)
        token_score = self._evaluate_token_efficiency(responses)

        wb_score = (
            bb_score * 0.35
            + structural_score * 0.25
            + trace_score * 0.20
            + tool_score * 0.15
            + token_score * 0.05
        )

        result.score = round(wb_score, 2)
        result.metrics.update({
            "structural_coverage": round(structural_score, 2),
            "reasoning_trace_quality": round(trace_score, 2),
            "tool_usage_correctness": round(tool_score, 2),
            "token_efficiency": round(token_score, 2),
        })

        result.passed = result.score >= 60.0

        if not result.passed and structural_score < 40:
            result.failure_category = FailureCategory.PROMPT_DESIGN
            result.failure_reason = "Structural analysis reveals gaps in reasoning or logic paths"

        return result

    def _evaluate_structural(self, scenario: TestScenario, responses: List[AgentResponse]) -> float:
        """Checks for logical structure in responses: step coverage, conclusion present."""
        scores = []
        for r in responses:
            if r.error:
                scores.append(0.0)
                continue
            output = r.output

            has_structure = bool(
                re.search(r'\b(first|second|then|finally|because|therefore|however|step \d)\b', output, re.I)
            )
            has_conclusion = bool(
                re.search(r'\b(in summary|conclusion|result|answer|therefore|thus)\b', output, re.I)
            )
            length_adequate = len(output.split()) > 10

            score = 0.0
            if has_structure:
                score += 40.0
            if has_conclusion:
                score += 30.0
            if length_adequate:
                score += 30.0

            if scenario.internal_hints:
                hint_terms = [t.strip() for t in scenario.internal_hints.split(',')]
                matched = sum(1 for t in hint_terms if t.lower() in output.lower())
                bonus = 20.0 * (matched / max(len(hint_terms), 1))
                score = min(100.0, score + bonus)

            scores.append(score)

        return statistics.mean(scores) if scores else 0.0

    def _evaluate_traces(self, scenario: TestScenario, responses: List[AgentResponse]) -> float:
        """Score quality of reasoning traces if available."""
        traces = [r.reasoning_trace for r in responses if r.reasoning_trace]
        if not traces:
            return 70.0

        scores = []
        for trace in traces:
            word_count = len(trace.split())
            if word_count < 5:
                scores.append(30.0)
            elif word_count < 30:
                scores.append(60.0)
            else:
                scores.append(90.0)

        return statistics.mean(scores)

    def _evaluate_tool_usage(self, scenario: TestScenario, responses: List[AgentResponse]) -> float:
        """Verify tool calls match the allowed set (white-box: we know what tools should be used)."""
        if scenario.allowed_tools is None:
            return 100.0

        scores = []
        for r in responses:
            if not r.tool_calls:
                scores.append(80.0 if not scenario.allowed_tools else 50.0)
                continue

            used_tools = {tc.get("name", "") for tc in r.tool_calls}
            allowed = set(scenario.allowed_tools)

            unauthorized = used_tools - allowed
            if unauthorized:
                penalty = min(100.0, len(unauthorized) * 25.0)
                scores.append(max(0.0, 100.0 - penalty))
            else:
                scores.append(100.0)

        return statistics.mean(scores) if scores else 100.0

    def _evaluate_token_efficiency(self, responses: List[AgentResponse]) -> float:
        """Score token efficiency based on output-to-input ratio."""
        scores = []
        for r in responses:
            usage = r.token_usage
            if not usage:
                scores.append(70.0)
                continue
            total = usage.get("total_tokens", 0)
            if total == 0:
                scores.append(70.0)
            elif total < 500:
                scores.append(100.0)
            elif total < 2000:
                scores.append(80.0)
            elif total < 5000:
                scores.append(60.0)
            else:
                scores.append(30.0)

        return statistics.mean(scores) if scores else 70.0
