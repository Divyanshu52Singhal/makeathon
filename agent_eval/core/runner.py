"""Test execution engine - runs scenarios against the agent multiple times."""

import time
from typing import List, Optional

from agent_eval.cache.result_cache import SupabaseResultCache, SupabaseReportStore
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
from agent_eval.judges.llm_judge import LLMJudge
from agent_eval.metrics.scorer import AggregatedScorer
from agent_eval.reports.generator import ReportGenerator
from agent_eval.scenarios.manager import ScenarioManager
from agent_eval.security.scanner import SecurityScanner


class EvaluationRunner:
    """
    Orchestrates the full evaluation pipeline:
    load scenarios -> run tests -> score -> report

    Caching: agent responses are stored per (agent_name, agent_version, scenario_id)
    in Supabase. On re-evaluation of the same agent the cached responses are reused
    so the agent is not re-invoked.  Pass clear_cache=True to force a fresh run.

    LLM Judge: when Azure OpenAI credentials are configured, the judge sends each
    scenario to the model using the Agent Evaluation Framework system prompt and
    replaces the keyword-based score with a semantically richer one.
    """

    DEPLOY_THRESHOLD = 70.0

    def __init__(
        self,
        agent: AgentInterface,
        scenario_file: Optional[str] = None,
        verbose: bool = True,
        llm_judge: Optional[LLMJudge] = None,
        cache: Optional[SupabaseResultCache] = None,
        report_store: Optional[SupabaseReportStore] = None,
        clear_cache: bool = False,
    ):
        self.agent = agent
        self.verbose = verbose
        self.scenario_manager = ScenarioManager(scenario_file)
        self._judge = llm_judge
        self._cache = cache or SupabaseResultCache()
        self._report_store = report_store or SupabaseReportStore()
        self._clear_cache = clear_cache

        self.black_box = BlackBoxEvaluator(llm_judge=self._judge)
        self.white_box = WhiteBoxEvaluator(llm_judge=self._judge)
        self.gray_box = GrayBoxEvaluator(llm_judge=self._judge)
        self.security_scanner = SecurityScanner()
        self.scorer = AggregatedScorer()
        self.report_gen = ReportGenerator()

        if self._clear_cache and self._cache.available:
            self._cache.invalidate(agent.name, agent.version)
            self._log("  [cache] Cleared cached results for this agent.")

    def run(self, modes: Optional[List[EvalMode]] = None) -> EvaluationReport:
        if modes is None:
            modes = [EvalMode.BLACK_BOX, EvalMode.WHITE_BOX, EvalMode.GRAY_BOX]

        scenarios = self.scenario_manager.get_all()
        all_results: List[TestResult] = []

        self._log(f"\n{'='*60}")
        self._log(f"  Agent Evaluation Framework")
        self._log(f"  Agent: {self.agent.name} v{self.agent.version}")
        self._log(f"  Scenarios: {len(scenarios)} | Modes: {[m.value for m in modes]}")
        judge_status = "enabled" if (self._judge and self._judge.available) else "disabled"
        cache_status = "enabled" if self._cache.available else "disabled"
        self._log(f"  LLM Judge: {judge_status} | Cache: {cache_status}")
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

        if self._report_store.available:
            report_dict = self._report_to_dict(report)
            self._report_store.save_report(self.agent.name, self.agent.version, report_dict)
            self._log("  [cache] Full report saved to Supabase.")

        return report

    def _execute_scenario(self, scenario: TestScenario, evaluator, mode: EvalMode) -> List[TestResult]:
        results = []
        self._log(f"  [{scenario.test_type.value}] {scenario.name}", end=" ")

        cached = self._cache.get(self.agent.name, self.agent.version, scenario.id)
        if cached is not None:
            responses = cached
            self._log(f"(cached)", end=" ")
        else:
            responses = []
            for _ in range(scenario.runs):
                response = self.agent.call(scenario.input, scenario.context)
                responses.append(response)
                time.sleep(0.1)
            self._cache.set(self.agent.name, self.agent.version, scenario.id, responses)

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

    def _report_to_dict(self, report: EvaluationReport) -> dict:
        return {
            "agent": {"name": report.agent_name, "version": report.agent_version},
            "timestamp": report.timestamp,
            "total_scenarios": report.total_scenarios,
            "scores": {
                "black_box": report.black_box_score,
                "white_box": report.white_box_score,
                "gray_box": report.gray_box_score,
                "aggregated": report.aggregated_score,
            },
            "deployable": report.deployable,
            "summary": report.summary,
            "benchmark": report.benchmark,
            "failure_analysis": report.failure_analysis,
        }

    def _log(self, msg: str, end: str = "\n"):
        if self.verbose:
            print(msg, end=end, flush=True)
