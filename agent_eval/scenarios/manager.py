"""
Scenario Manager: Loads and manages test scenarios from YAML files.
"""

import uuid
from typing import List, Optional

import yaml

from agent_eval.core.base import TestScenario, TestType


DEFAULT_SCENARIOS = [
    {
        "id": "default_happy_1",
        "name": "Basic Greeting",
        "description": "Standard user greeting - agent should respond helpfully",
        "test_type": "happy_path",
        "input": "Hello, can you help me today?",
        "expected_keywords": ["help", "happy", "assist", "sure", "yes", "hello"],
        "max_latency_seconds": 10.0,
        "runs": 2,
    },
    {
        "id": "default_edge_1",
        "name": "Empty Input",
        "description": "Agent should gracefully handle empty or minimal input",
        "test_type": "edge_case",
        "input": "   ",
        "max_latency_seconds": 5.0,
        "runs": 2,
    },
    {
        "id": "default_fail_1",
        "name": "Nonsense Input",
        "description": "Agent should handle incoherent input gracefully",
        "test_type": "failure_handling",
        "input": "asdfjkl qwerty zxcvbn 123!@#",
        "max_latency_seconds": 10.0,
        "runs": 2,
    },
]

TYPE_MAP = {
    "happy_path": TestType.HAPPY_PATH,
    "edge_case": TestType.EDGE_CASE,
    "failure_handling": TestType.FAILURE_HANDLING,
    "safety_compliance": TestType.SAFETY_COMPLIANCE,
    "regression": TestType.REGRESSION,
    "security": TestType.SECURITY,
}


class ScenarioManager:
    """Load scenarios from a YAML file or use defaults."""

    def __init__(self, scenario_file: Optional[str] = None):
        self._scenarios: List[TestScenario] = []
        if scenario_file:
            self._load_from_file(scenario_file)
        else:
            self._load_defaults()

    def get_all(self) -> List[TestScenario]:
        return self._scenarios

    def get_by_type(self, test_type: TestType) -> List[TestScenario]:
        return [s for s in self._scenarios if s.test_type == test_type]

    def add_scenario(self, scenario: TestScenario):
        self._scenarios.append(scenario)

    def _load_from_file(self, path: str):
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        scenarios = data.get("scenarios", []) if isinstance(data, dict) else data
        self._scenarios = [self._parse(s) for s in scenarios]

    def _load_defaults(self):
        self._scenarios = [self._parse(s) for s in DEFAULT_SCENARIOS]

    def _parse(self, data: dict) -> TestScenario:
        test_type_str = data.get("test_type", "happy_path")
        test_type = TYPE_MAP.get(test_type_str, TestType.HAPPY_PATH)

        return TestScenario(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Unnamed Scenario"),
            description=data.get("description", ""),
            test_type=test_type,
            input=data.get("input", ""),
            expected_output=data.get("expected_output"),
            expected_keywords=data.get("expected_keywords", []),
            forbidden_keywords=data.get("forbidden_keywords", []),
            expected_refusal=data.get("expected_refusal", False),
            allowed_tools=data.get("allowed_tools"),
            max_latency_seconds=float(data.get("max_latency_seconds", 10.0)),
            runs=int(data.get("runs", 3)),
            context=data.get("context", {}),
            tags=data.get("tags", []),
            internal_hints=data.get("internal_hints"),
        )
