from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"
    CRITICAL = "严重"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    display_name: str
    description: str
    risk: RiskLevel
    side_effect: bool = False


@dataclass(frozen=True)
class ToolCall:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    origin: str = "user_request"
    rationale: str = ""


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    category: str
    description: str
    user_request: str
    source_tool: str
    source_args: dict[str, Any]
    untrusted_content: str
    expected_actions: tuple[ToolCall, ...]
    injected_actions: tuple[ToolCall, ...]
    allowed_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    sensitive_values: tuple[str, ...]
    difficulty: str
    tags: tuple[str, ...]

    @property
    def is_attack(self) -> bool:
        return self.category != "benign"


@dataclass(frozen=True)
class DefenseConfig:
    key: str
    label: str
    description: str
    detect_prompt_injection: bool = False
    isolate_untrusted_instructions: bool = False
    enforce_tool_allowlist: bool = False
    block_sensitive_data: bool = False
    require_high_risk_approval: bool = False
    approve_high_risk_actions: bool = False


@dataclass(frozen=True)
class AgentDecision:
    summary: str
    actions: tuple[ToolCall, ...]
    answer: str
    provider: str


@dataclass(frozen=True)
class GuardEvent:
    guardrail: str
    triggered: bool
    reason: str
    tool: str = ""
    action: str = "记录"


@dataclass(frozen=True)
class ToolExecution:
    sequence: int
    tool: str
    display_name: str
    risk: str
    origin: str
    arguments: dict[str, Any]
    status: str
    output: str
    blocked_by: str = ""
    duration_ms: float = 0.0


@dataclass(frozen=True)
class RunResult:
    scenario_id: str
    scenario_name: str
    scenario_category: str
    defense_key: str
    defense_label: str
    provider: str
    injection_detected: bool
    attack_succeeded: bool
    task_succeeded: bool
    false_positive: bool
    answer: str
    decision_summary: str
    executions: tuple[ToolExecution, ...]
    guard_events: tuple[GuardEvent, ...]
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass(frozen=True)
class EvaluationMetrics:
    profile_key: str
    profile_label: str
    total_scenarios: int
    attack_scenarios: int
    benign_scenarios: int
    attack_success_rate: float
    task_success_rate: float
    false_positive_rate: float
    injection_detection_rate: float
    average_blocked_calls: float
    average_duration_ms: float
    overall_score: float

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value

