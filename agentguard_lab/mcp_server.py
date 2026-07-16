from __future__ import annotations

import json
import os
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from .config import DEFENSE_PROFILES, get_defense_profile
from .engine import AgentGuardEngine
from .evaluator import evaluate_profile
from .scenarios import get_scenario, load_scenarios

mcp = FastMCP(
    "AgentGuard Lab",
    instructions=(
        "用于运行 Agent 提示词注入安全实验。所有高风险工具均在内存中模拟，"
        "不会访问真实邮箱、文件、软件仓库或密钥。"
    ),
    stateless_http=True,
    json_response=True,
)


def build_scenario_catalog(kind: str = "all") -> list[dict[str, Any]]:
    if kind not in {"all", "attack", "benign"}:
        raise ValueError("kind 必须是 all、attack 或 benign")

    scenarios = load_scenarios()
    if kind == "attack":
        scenarios = [item for item in scenarios if item.is_attack]
    elif kind == "benign":
        scenarios = [item for item in scenarios if not item.is_attack]

    return [
        {
            "id": item.id,
            "name": item.name,
            "type": "attack" if item.is_attack else "benign",
            "category": item.category,
            "difficulty": item.difficulty,
            "description": item.description,
            "tags": list(item.tags),
        }
        for item in scenarios
    ]


def run_scenario_data(
    scenario_id: str,
    profile: str = "balanced",
    approve_high_risk: bool = False,
) -> dict[str, Any]:
    if profile not in DEFENSE_PROFILES:
        raise ValueError(f"profile 必须是以下值之一：{', '.join(DEFENSE_PROFILES)}")

    scenario = get_scenario(scenario_id)
    defense = get_defense_profile(profile, approve_high_risk)
    result = AgentGuardEngine().run(scenario, defense)
    return result.to_dict()


def compare_profiles_data() -> dict[str, Any]:
    scenarios = load_scenarios()
    metrics = []
    for key in DEFENSE_PROFILES:
        item, _ = evaluate_profile(scenarios, get_defense_profile(key))
        metrics.append(item.to_dict())
    best = max(metrics, key=lambda item: item["overall_score"])
    return {
        "scenario_count": len(scenarios),
        "profiles": metrics,
        "best_profile": best["profile_key"],
        "note": "结果来自内置确定性场景，不代表生产环境中的绝对安全水平。",
    }


@mcp.tool()
def list_security_scenarios(
    kind: Literal["all", "attack", "benign"] = "all",
) -> list[dict[str, Any]]:
    """列出 AgentGuard Lab 的安全测试场景，可按攻击或正常场景筛选。"""
    return build_scenario_catalog(kind)


@mcp.tool()
def run_security_scenario(
    scenario_id: str,
    profile: Literal["baseline", "detection", "balanced", "strict"] = "balanced",
    approve_high_risk: bool = False,
) -> dict[str, Any]:
    """运行一个隔离的 Agent 安全场景，返回工具轨迹、防御事件和评测结论。"""
    return run_scenario_data(scenario_id, profile, approve_high_risk)


@mcp.tool()
def compare_defense_profiles() -> dict[str, Any]:
    """在全部内置场景上比较四组防御配置，返回 ASR、TSR、FPR 和综合分。"""
    return compare_profiles_data()


@mcp.resource("agentguard://scenario/{scenario_id}")
def read_scenario_resource(scenario_id: str) -> str:
    """读取指定场景的用户任务、不可信内容、工具白名单和禁止工具。"""
    scenario = get_scenario(scenario_id)
    return json.dumps(
        {
            "id": scenario.id,
            "name": scenario.name,
            "user_request": scenario.user_request,
            "untrusted_content": scenario.untrusted_content,
            "allowed_tools": list(scenario.allowed_tools),
            "forbidden_tools": list(scenario.forbidden_tools),
            "sensitive_values": list(scenario.sensitive_values),
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.prompt(title="Agent 应用安全评审")
def agent_security_review(system_description: str) -> str:
    """生成一份用于评审工具调用 Agent 的结构化安全检查提示。"""
    return (
        "请对下面的 Agent 应用进行安全评审。依次分析：不可信输入来源、可调用工具、"
        "每个工具的副作用、最小权限、敏感数据流、高风险审批、审计与评测方案。"
        "请区分检测措施和阻断措施，并给出可量化的 ASR、TSR、FPR 测试设计。\n\n"
        f"系统描述：{system_description}"
    )


def main() -> None:
    transport = os.getenv("AGENTGUARD_MCP_TRANSPORT", "stdio")
    if transport not in {"stdio", "streamable-http"}:
        raise ValueError("AGENTGUARD_MCP_TRANSPORT 必须是 stdio 或 streamable-http")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()

