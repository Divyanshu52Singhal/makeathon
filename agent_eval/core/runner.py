"""Test execution engine - runs scenarios against the agent multiple times."""

import time
from typing import List, Optional

from agent_eval.core.base import (
    AgentInterface,
    EvalMode,
    EvaluationReport,
    TestResult,
    TestScenario,
)
from agent_eval.evaluators.black_box import BlackBoxEvaluator
from agent_eval.evaluators.gray_box import GrayBoxEvaluator
from agent_eval.evaluators.white_box import WhiteBoxEvaluator
from agent_eval.metrics.scorer import AggregatedScorer
from agent_eval.reports.generator import ReportGenerator
from agent_eval.scenarios.manager import ScenarioManager
from agent_eval.security.scanner import SecurityScanner


class EvaluationRunner:
    """
    Orchestrates the full evaluation pipeline:
    load scenarios -> run tests -> score -> report
    """

    DEPLOY_THRESHOLD = 70.0

    def __init__(self, agent: AgentInterface, scenario_file: Optional[str] = None, verbose: bool = True):
        self.agent = agent
        self.verbose = verbose
        self.scenario_manager = ScenarioManager(scenario_file)
        self.black_box = BlackBoxEvaluator()
        self.white_box = WhiteBoxEvaluator()
        self.gray_box = GrayBoxEvaluator()
        self.security_scanner = SecurityScanner()
        self.scorer = AggregatedScorer()
        self.report_gen = ReportGenerator()

    def run(self, modes: Optional[List[EvalMode]] = None) -> EvaluationReport:
        if modes is None:
            modes = [EvalMode.BLACK_BOX, EvalMode.WHITE_BOX, EvalMode.GRAY_BOX]

        scenarios = self.scenario_manager.get_all()
        all_results: List[TestResult] = []

        self._log(f"\n{'='*60}")
        self._log(f"  Agent Evaluation Framework")
        self._log(f"  Agent: {self.agent.name} v{self.agent.version}")
        self._log(f"  Scenarios: {len(scenarios)} | Modes: {[m.value for m in modes]}")
        self._log(f"{'='*60}\n")

        for mode in modes:
            evaluator = self._get_evaluator(mode)
            self._log(f"[{mode.value.upper()}] Running {len(scenarios)} scenarios...\n")

            for scenario in scenarios:
                run_results = self._execute_scenario(scenario, evaluator, mode)
                all_results.extend(run_results)

        security_results = self.security_scanner.run_security_suite(self.agent)
        all_results.extend(security_results)

        report = self.scorer.build_report(self.agent, all_results, self.DEPLOY_THRESHOLD)
        return report

    def _execute_scenario(self, scenario: TestScenario, evaluator, mode: EvalMode) -> List[TestResult]:
        results = []
        self._log(f"  [{scenario.test_type.value}] {scenario.name}", end=" ")

        responses = []
        for _ in range(scenario.runs):
            response = self.agent.call(scenario.input, scenario.context)
            responses.append(response)
            time.sleep(0.1)

        result = evaluator.evaluate(scenario, responses, mode)
        results.append(result)

        status = "PASS" if result.passed else "FAIL"
        self._log(f"-> {status} (score: {result.score:.1f})")

        if not result.passed and result.failure_reason:
            self._log(f"    Reason: {result.failure_reason}")

        return results

    def _get_evaluator(self, mode: EvalMode):
        return {
            EvalMode.BLACK_BOX: self.black_box,
            EvalMode.WHITE_BOX: self.white_box,
            EvalMode.GRAY_BOX: self.gray_box,
        }[mode]

    def _log(self, msg: str, end: str = "\n"):
        if self.verbose:
            print(msg, end=end, flush=True)
