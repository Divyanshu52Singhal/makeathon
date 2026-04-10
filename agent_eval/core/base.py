"""Base classes and data models for the Agent Evaluation Framework."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TestType(Enum):
    HAPPY_PATH = "happy_path"
    EDGE_CASE = "edge_case"
    FAILURE_HANDLING = "failure_handling"
    SAFETY_COMPLIANCE = "safety_compliance"
    REGRESSION = "regression"
    SECURITY = "security"


class EvalMode(Enum):
    BLACK_BOX = "black_box"
    WHITE_BOX = "white_box"
    GRAY_BOX = "gray_box"


class FailureCategory(Enum):
    MODEL_LIMITATION = "model_limitation"
    PROMPT_DESIGN = "prompt_design_issue"
    TOOL_INTEGRATION = "tool_integration_issue"
    SCENARIO_COVERAGE = "scenario_coverage_gap"
    SECURITY_VIOLATION = "security_violation"
    NONE = "none"


@dataclass
class AgentInterface:
    """Wrapper for the agent under test. Supports callable, HTTP endpoint, or custom adapter."""
    name: str
    version: str = "1.0"
    invoke: Optional[Callable] = None
    endpoint_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def call(self, input_text: str, context: Optional[Dict] = None) -> "AgentResponse":
        start = time.time()
        if self.invoke:
            try:
                result = self.invoke(input_text, context or {})
                latency = time.time() - start
                if isinstance(result, dict):
                    return AgentResponse(
                        output=result.get("output", str(result)),
                        reasoning_trace=result.get("reasoning_trace"),
                        tool_calls=result.get("tool_calls", []),
                        token_usage=result.get("token_usage", {}),
                        latency=latency,
                        raw=result,
                    )
                return AgentResponse(output=str(result), latency=latency, raw=result)
            except Exception as e:
                latency = time.time() - start
                return AgentResponse(output="", error=str(e), latency=latency)
        elif self.endpoint_url:
            return self._call_http(input_text, context or {}, start)
        raise ValueError("AgentInterface requires either 'invoke' callable or 'endpoint_url'")

    def _call_http(self, input_text: str, context: Dict, start: float) -> "AgentResponse":
        import requests
        try:
            resp = requests.post(
                self.endpoint_url,
                json={"input": input_text, "context": context},
                timeout=30,
            )
            latency = time.time() - start
            data = resp.json()
            return AgentResponse(
                output=data.get("output", ""),
                reasoning_trace=data.get("reasoning_trace"),
                tool_calls=data.get("tool_calls", []),
                token_usage=data.get("token_usage", {}),
                latency=latency,
                raw=data,
            )
        except Exception as e:
            return AgentResponse(output="", error=str(e), latency=time.time() - start)


@dataclass
class AgentResponse:
    output: str
    reasoning_trace: Optional[str] = None
    tool_calls: List[Dict] = field(default_factory=list)
    token_usage: Dict[str, int] = field(default_factory=dict)
    latency: float = 0.0
    error: Optional[str] = None
    raw: Any = None


@dataclass
class TestScenario:
    id: str
    name: str
    description: str
    test_type: TestType
    input: str
    expected_output: Optional[str] = None
    expected_keywords: List[str] = field(default_factory=list)
    forbidden_keywords: List[str] = field(default_factory=list)
    expected_refusal: bool = False
    allowed_tools: Optional[List[str]] = None
    max_latency_seconds: float = 10.0
    runs: int = 3
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    internal_hints: Optional[str] = None


@dataclass
class TestResult:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    scenario_id: str = ""
    scenario_name: str = ""
    test_type: TestType = TestType.HAPPY_PATH
    eval_mode: EvalMode = EvalMode.BLACK_BOX
    passed: bool = False
    score: float = 0.0
    response: Optional[AgentResponse] = None
    failure_category: FailureCategory = FailureCategory.NONE
    failure_reason: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass
class EvaluationReport:
    agent_name: str
    agent_version: str
    timestamp: str
    total_scenarios: int
    results: List[TestResult] = field(default_factory=list)
    black_box_score: float = 0.0
    white_box_score: float = 0.0
    gray_box_score: float = 0.0
    aggregated_score: float = 0.0
    deployable: bool = False
    summary: Dict[str, Any] = field(default_factory=dict)
    failure_analysis: List[Dict] = field(default_factory=list)
    benchmark: Dict[str, Any] = field(default_factory=dict)
