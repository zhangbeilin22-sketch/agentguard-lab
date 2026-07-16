from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import TOOL_SPECS
from .models import Scenario, ToolCall

DEFAULT_SCENARIO_PATH = Path(__file__).resolve().parent.parent / "data" / "scenarios.json"


def load_scenarios(path: Path | str = DEFAULT_SCENARIO_PATH) -> list[Scenario]:
    scenario_path = Path(path)
    raw_scenarios = json.loads(scenario_path.read_text(encoding="utf-8"))
    scenarios = [_scenario_from_dict(item) for item in raw_scenarios]
    _validate_scenarios(scenarios)
    return scenarios


def get_scenario(scenario_id: str, scenarios: list[Scenario] | None = None) -> Scenario:
    candidates = scenarios or load_scenarios()
    for scenario in candidates:
        if scenario.id == scenario_id:
            return scenario
    raise KeyError(f"未找到场景: {scenario_id}")


def _scenario_from_dict(data: dict[str, Any]) -> Scenario:
    return Scenario(
        id=data["id"],
        name=data["name"],
        category=data["category"],
        description=data["description"],
        user_request=data["user_request"],
        source_tool=data["source_tool"],
        source_args=data.get("source_args", {}),
        untrusted_content=data["untrusted_content"],
        expected_actions=tuple(
            _tool_call(item, "user_request") for item in data["expected_actions"]
        ),
        injected_actions=tuple(
            _tool_call(item, "untrusted_content") for item in data.get("injected_actions", [])
        ),
        allowed_tools=tuple(data["allowed_tools"]),
        forbidden_tools=tuple(data.get("forbidden_tools", [])),
        sensitive_values=tuple(data.get("sensitive_values", [])),
        difficulty=data.get("difficulty", "中等"),
        tags=tuple(data.get("tags", [])),
    )


def _tool_call(data: dict[str, Any], default_origin: str) -> ToolCall:
    return ToolCall(
        tool=data["tool"],
        arguments=data.get("arguments", {}),
        origin=data.get("origin", default_origin),
        rationale=data.get("rationale", ""),
    )


def _validate_scenarios(scenarios: list[Scenario]) -> None:
    ids = [scenario.id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("场景 ID 必须唯一")

    known_tools = set(TOOL_SPECS)
    for scenario in scenarios:
        referenced_tools = {
            scenario.source_tool,
            *scenario.allowed_tools,
            *scenario.forbidden_tools,
            *(call.tool for call in scenario.expected_actions),
            *(call.tool for call in scenario.injected_actions),
        }
        unknown = referenced_tools - known_tools
        if unknown:
            raise ValueError(f"场景 {scenario.id} 引用了未知工具: {sorted(unknown)}")
        expected_tools = {call.tool for call in scenario.expected_actions}
        if not expected_tools.issubset(set(scenario.allowed_tools)):
            raise ValueError(f"场景 {scenario.id} 的预期工具必须包含在白名单中")
