"""
CLI interface for the Agent Evaluation Framework.
Usage: python main.py [options]
"""

import argparse
import importlib.util
import sys
from typing import Optional

from agent_eval.core.base import AgentInterface, EvalMode
from agent_eval.core.runner import EvaluationRunner
from agent_eval.reports.generator import ReportGenerator


def parse_args():
    parser = argparse.ArgumentParser(
        prog="agent-eval",
        description="Agent Evaluation Framework - Black, White & Gray Box Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --agent examples/sample_agent.py
  python main.py --agent examples/sample_agent.py --scenarios examples/sample_scenarios.yaml
  python main.py --agent examples/sample_agent.py --modes black_box gray_box --output report.json
  python main.py --endpoint http://localhost:8000/agent --name "MyAgent"
        """,
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--agent", metavar="FILE",
        help="Path to a Python file that defines 'agent_invoke(input, context) -> dict'",
    )
    source_group.add_argument(
        "--endpoint", metavar="URL",
        help="HTTP endpoint of the agent (POST with {input, context})",
    )

    parser.add_argument("--name", default="Agent", help="Agent name (default: Agent)")
    parser.add_argument("--version", default="1.0", help="Agent version (default: 1.0)")
    parser.add_argument(
        "--scenarios", metavar="FILE",
        help="Path to YAML scenario file. Uses built-in defaults if not provided.",
    )
    parser.add_argument(
        "--modes", nargs="+",
        choices=["black_box", "white_box", "gray_box"],
        default=["black_box", "white_box", "gray_box"],
        help="Evaluation modes to run (default: all three)",
    )
    parser.add_argument(
        "--output", metavar="FILE", default="evaluation_report.json",
        help="Output JSON report path (default: evaluation_report.json)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress verbose output; only show final report",
    )
    parser.add_argument(
        "--threshold", type=float, default=70.0,
        help="Deployability score threshold 0-100 (default: 70.0)",
    )

    return parser.parse_args()


def load_agent_from_file(path: str, name: str, version: str) -> AgentInterface:
    spec = importlib.util.spec_from_file_location("agent_module", path)
    if spec is None:
        print(f"Error: cannot load agent from '{path}'", file=sys.stderr)
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"Error executing agent file '{path}': {e}", file=sys.stderr)
        sys.exit(1)

    if not hasattr(module, "agent_invoke"):
        print(f"Error: '{path}' must define a function 'agent_invoke(input: str, context: dict) -> dict'", file=sys.stderr)
        sys.exit(1)

    return AgentInterface(name=name, version=version, invoke=module.agent_invoke)


def run_cli():
    args = parse_args()

    if args.agent:
        agent = load_agent_from_file(args.agent, args.name, args.version)
    else:
        agent = AgentInterface(name=args.name, version=args.version, endpoint_url=args.endpoint)

    modes = [EvalMode(m) for m in args.modes]

    runner = EvaluationRunner(
        agent=agent,
        scenario_file=args.scenarios,
        verbose=not args.quiet,
    )
    runner.DEPLOY_THRESHOLD = args.threshold

    report = runner.run(modes=modes)

    report_gen = ReportGenerator()
    report_gen.print_summary(report)

    saved_path = report_gen.save_json(report, args.output)
    print(f"\n  Report saved: {saved_path}\n")

    sys.exit(0 if report.deployable else 1)
