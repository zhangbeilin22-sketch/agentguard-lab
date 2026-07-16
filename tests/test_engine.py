from agentguard_lab.config import get_defense_profile
from agentguard_lab.engine import AgentGuardEngine
from agentguard_lab.models import DefenseConfig
from agentguard_lab.scenarios import get_scenario, load_scenarios


def test_baseline_reproduces_all_injected_attacks():
    attacks = [item for item in load_scenarios() if item.is_attack]
    engine = AgentGuardEngine()

    results = [engine.run(item, get_defense_profile("baseline")) for item in attacks]

    assert all(result.attack_succeeded for result in results)
    assert all(result.task_succeeded for result in results)


def test_balanced_profile_blocks_attacks_without_breaking_tasks():
    scenarios = load_scenarios()
    engine = AgentGuardEngine()

    results = [engine.run(item, get_defense_profile("balanced")) for item in scenarios]

    assert not any(result.attack_succeeded for result in results)
    assert all(result.task_succeeded for result in results)
    assert not any(result.false_positive for result in results)


def test_strict_profile_requires_approval_for_legitimate_email():
    scenario = get_scenario("benign_send_update")
    engine = AgentGuardEngine()

    pending = engine.run(scenario, get_defense_profile("strict"))
    approved = engine.run(scenario, get_defense_profile("strict", approve_high_risk_actions=True))

    assert not pending.task_succeeded
    assert pending.false_positive
    assert any(item.status == "待审批" for item in pending.executions)
    assert approved.task_succeeded


def test_sensitive_data_guard_works_without_other_guards():
    scenario = get_scenario("attack_email_exfiltration")
    dlp_only = DefenseConfig(
        key="dlp-only",
        label="仅敏感数据检查",
        description="测试配置",
        block_sensitive_data=True,
    )

    result = AgentGuardEngine().run(scenario, dlp_only)

    assert not result.attack_succeeded
    assert any(event.guardrail == "敏感数据防泄漏" for event in result.guard_events)


def test_tool_allowlist_blocks_destructive_call():
    scenario = get_scenario("attack_file_deletion")
    allowlist_only = DefenseConfig(
        key="allowlist-only",
        label="仅工具白名单",
        description="测试配置",
        enforce_tool_allowlist=True,
    )

    result = AgentGuardEngine().run(scenario, allowlist_only)

    assert not result.attack_succeeded
    blocked = [item for item in result.executions if item.tool == "delete_file"]
    assert blocked[0].status == "已阻断"

