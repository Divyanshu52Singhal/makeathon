"""
Report Generator: Produces terminal and JSON reports from evaluation results.
"""

import json
import os
from typing import Optional

from agent_eval.core.base import EvaluationReport, TestType


try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False


def _green(text):
    return f"{Fore.GREEN}{text}{Style.RESET_ALL}" if HAS_COLOR else text

def _red(text):
    return f"{Fore.RED}{text}{Style.RESET_ALL}" if HAS_COLOR else text

def _yellow(text):
    return f"{Fore.YELLOW}{text}{Style.RESET_ALL}" if HAS_COLOR else text

def _cyan(text):
    return f"{Fore.CYAN}{text}{Style.RESET_ALL}" if HAS_COLOR else text

def _bold(text):
    return f"{Style.BRIGHT}{text}{Style.RESET_ALL}" if HAS_COLOR else text


class ReportGenerator:

    def print_summary(self, report: EvaluationReport):
        print()
        print(_bold("=" * 65))
        print(_bold(f"  AGENT EVALUATION REPORT"))
        print(_bold("=" * 65))
        print(f"  Agent        : {report.agent_name} v{report.agent_version}")
        print(f"  Timestamp    : {report.timestamp}")
        print(f"  Scenarios    : {report.total_scenarios}")
        print()

        print(_bold("  [ Score Breakdown ]"))
        print(f"  Black-Box    : {self._score_bar(report.black_box_score)} {report.black_box_score:.1f}/100")
        print(f"  White-Box    : {self._score_bar(report.white_box_score)} {report.white_box_score:.1f}/100")
        print(f"  Gray-Box     : {self._score_bar(report.gray_box_score)} {report.gray_box_score:.1f}/100")
        print(f"  {'─'*50}")
        print(f"  Aggregated   : {self._score_bar(report.aggregated_score)} {report.aggregated_score:.1f}/100")
        print()

        if report.deployable:
            verdict = _green("  ✓  AGENT IS DEPLOYABLE")
        else:
            verdict = _red("  ✗  AGENT IS NOT DEPLOYABLE")
        print(_bold(verdict))
        print()

        s = report.summary
        print(_bold("  [ Test Summary ]"))
        print(f"  Total Tests  : {s.get('total_tests', 0)}")
        print(f"  Passed       : {_green(str(s.get('passed', 0)))}")
        print(f"  Failed       : {_red(str(s.get('failed', 0)))}")
        print(f"  Pass Rate    : {s.get('pass_rate_pct', 0.0):.1f}%")
        print(f"  Avg Latency  : {s.get('avg_latency_s', 0.0):.3f}s")
        print()

        if report.benchmark:
            print(_bold("  [ Results by Test Type ]"))
            for ttype, data in report.benchmark.items():
                bar = self._score_bar(data['avg_score'])
                print(f"  {ttype:<22} Score: {data['avg_score']:5.1f}  Pass Rate: {data['pass_rate']:.0f}%  {bar}")
            print()

        if report.failure_analysis:
            print(_bold("  [ Failure Analysis ]"))
            for fa in report.failure_analysis:
                print(f"  Category : {_yellow(fa['category'])}")
                print(f"  Count    : {fa['count']}")
                print(f"  Avg Score: {fa['avg_score']:.1f}")
                print(f"  Tip      : {fa['recommendation']}")
                print()

        print(_bold("=" * 65))

    def save_json(self, report: EvaluationReport, output_path: str = "evaluation_report.json"):
        data = {
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
            "detailed_results": [
                {
                    "run_id": r.run_id,
                    "scenario_id": r.scenario_id,
                    "scenario_name": r.scenario_name,
                    "test_type": r.test_type.value,
                    "eval_mode": r.eval_mode.value,
                    "passed": r.passed,
                    "score": r.score,
                    "failure_category": r.failure_category.value,
                    "failure_reason": r.failure_reason,
                    "metrics": r.metrics,
                    "response": {
                        "output": r.response.output[:500] if r.response else "",
                        "latency": r.response.latency if r.response else 0,
                        "error": r.response.error if r.response else None,
                    } if r.response else None,
                }
                for r in report.results
            ],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        return output_path

    def _score_bar(self, score: float, width: int = 20) -> str:
        filled = int((score / 100.0) * width)
        bar = "█" * filled + "░" * (width - filled)
        if score >= 75:
            return _green(f"[{bar}]")
        elif score >= 50:
            return _yellow(f"[{bar}]")
        else:
            return _red(f"[{bar}]")
