"""
CLI interface for the Agent Evaluation Framework.
Usage: python main.py [options]
"""

import argparse
import importlib.util
import os
import sys
from typing import Optional

from dotenv import load_dotenv

from agent_eval.cache.result_cache import SupabaseResultCache, SupabaseReportStore
from agent_eval.core.base import AgentInterface, EvalMode
from agent_eval.core.runner import EvaluationRunner
from agent_eval.judges.llm_judge import LLMJudge
from agent_eval.reports.generator import ReportGenerator

load_dotenv()


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
  python main.py --agent examples/sample_agent.py --llm-judge
  python main.py --agent examples/sample_agent.py --clear-cache
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

    llm_group = parser.add_argument_group("LLM Judge (Azure OpenAI)")
    llm_group.add_argument(
        "--llm-judge", action="store_true",
        help="Enable LLM-based evaluation using Azure OpenAI (requires AZURE_OPENAI_* env vars)",
    )
    llm_group.add_argument(
        "--azure-endpoint", metavar="URL",
        default=None,
        help="Azure OpenAI endpoint URL (overrides AZURE_OPENAI_ENDPOINT env var)",
    )
    llm_group.add_argument(
        "--azure-api-key", metavar="KEY",
        default=None,
        help="Azure OpenAI API key (overrides AZURE_OPENAI_KEY env var)",
    )
    llm_group.add_argument(
        "--azure-deployment", metavar="NAME",
        default=None,
        help="Azure OpenAI deployment name (overrides AZURE_OPENAI_DEPLOYMENT env var)",
    )

    cache_group = parser.add_argument_group("Caching (Supabase)")
    cache_group.add_argument(
        "--clear-cache", action="store_true",
        help="Invalidate cached responses for this agent before running",
    )
    cache_group.add_argument(
        "--cache-ttl", type=int, default=86400,
        help="Cache TTL in seconds (default: 86400 = 24h)",
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

    llm_judge: Optional[LLMJudge] = None
    if args.llm_judge:
        llm_judge = LLMJudge(
            endpoint=args.azure_endpoint,
            api_key=args.azure_api_key,
            deployment=args.azure_deployment,
        )
        if not llm_judge.available:
            print(
                "Warning: LLM judge requested but Azure OpenAI credentials are missing. "
                "Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, and AZURE_OPENAI_DEPLOYMENT "
                "or pass --azure-endpoint / --azure-api-key / --azure-deployment.",
                file=sys.stderr,
            )

    cache = SupabaseResultCache(ttl_seconds=args.cache_ttl)
    report_store = SupabaseReportStore()

    runner = EvaluationRunner(
        agent=agent,
        scenario_file=args.scenarios,
        verbose=not args.quiet,
        llm_judge=llm_judge,
        cache=cache,
        report_store=report_store,
        clear_cache=args.clear_cache,
    )
    runner.DEPLOY_THRESHOLD = args.threshold

    report = runner.run(modes=modes)

    report_gen = ReportGenerator()
    report_gen.print_summary(report)

    saved_path = report_gen.save_json(report, args.output)
    print(f"\n  Report saved: {saved_path}\n")

    if report_store.available:
        print(f"  Supabase report store: updated for {agent.name} v{agent.version}\n")

    sys.exit(0 if report.deployable else 1)
