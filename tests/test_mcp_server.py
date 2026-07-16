import asyncio

from agentguard_lab.mcp_server import (
    build_scenario_catalog,
    compare_profiles_data,
    mcp,
    run_scenario_data,
)


def test_mcp_catalog_can_filter_scenarios():
    assert len(build_scenario_catalog()) == 12
    assert len(build_scenario_catalog("attack")) == 6
    assert len(build_scenario_catalog("benign")) == 6


def test_mcp_runs_balanced_security_scenario():
    result = run_scenario_data("attack_repo_supply_chain", "balanced")

    assert result["attack_succeeded"] is False
    assert result["task_succeeded"] is True
    assert any(item["tool"] == "publish_package" for item in result["executions"])


def test_mcp_compares_profiles():
    report = compare_profiles_data()

    assert report["scenario_count"] == 12
    assert report["best_profile"] == "balanced"
    assert len(report["profiles"]) == 4
    assert mcp.name == "AgentGuard Lab"


def test_mcp_protocol_registers_and_calls_tools():
    async def exercise_protocol():
        tools = await mcp.list_tools()
        _, structured_result = await mcp.call_tool(
            "run_security_scenario",
            {"scenario_id": "attack_repo_supply_chain", "profile": "balanced"},
        )
        return tools, structured_result

    tools, result = asyncio.run(exercise_protocol())

    assert {tool.name for tool in tools} == {
        "list_security_scenarios",
        "run_security_scenario",
        "compare_defense_profiles",
    }
    assert result["attack_succeeded"] is False
    assert result["task_succeeded"] is True
