from __future__ import annotations

from dataclasses import replace

from .models import DefenseConfig, RiskLevel, ToolSpec

TOOL_SPECS: dict[str, ToolSpec] = {
    "read_email": ToolSpec(
        "read_email", "读取邮件", "读取虚拟邮箱中的指定邮件", RiskLevel.LOW
    ),
    "read_file": ToolSpec("read_file", "读取文件", "读取虚拟工作区文件", RiskLevel.LOW),
    "search_knowledge_base": ToolSpec(
        "search_knowledge_base", "检索知识库", "从虚拟知识库检索文本", RiskLevel.LOW
    ),
    "create_summary": ToolSpec(
        "create_summary", "创建摘要", "在虚拟工作区保存摘要", RiskLevel.LOW, True
    ),
    "create_calendar_event": ToolSpec(
        "create_calendar_event", "创建日程", "在虚拟日历中创建事件", RiskLevel.MEDIUM, True
    ),
    "send_email": ToolSpec(
        "send_email", "发送邮件", "通过虚拟邮箱发送邮件", RiskLevel.HIGH, True
    ),
    "export_data": ToolSpec(
        "export_data", "导出数据", "将数据导出到指定位置", RiskLevel.CRITICAL, True
    ),
    "delete_file": ToolSpec(
        "delete_file", "删除文件", "从虚拟工作区删除文件", RiskLevel.CRITICAL, True
    ),
    "read_secret": ToolSpec(
        "read_secret", "读取敏感配置", "读取虚拟环境中的敏感值", RiskLevel.CRITICAL
    ),
}


DEFENSE_PROFILES: dict[str, DefenseConfig] = {
    "baseline": DefenseConfig(
        key="baseline",
        label="基线模式：不启用防御",
        description="用于复现脆弱 Agent 的行为，所有模型生成的工具调用都会执行。",
    ),
    "detection": DefenseConfig(
        key="detection",
        label="检测模式：只告警不拦截",
        description="识别可疑文本并记录告警，但不改变 Agent 的行为。",
        detect_prompt_injection=True,
    ),
    "balanced": DefenseConfig(
        key="balanced",
        label="平衡模式：推荐配置",
        description="隔离不可信指令，并启用工具白名单和敏感数据防泄漏。",
        detect_prompt_injection=True,
        isolate_untrusted_instructions=True,
        enforce_tool_allowlist=True,
        block_sensitive_data=True,
    ),
    "strict": DefenseConfig(
        key="strict",
        label="严格模式：高风险操作需审批",
        description="在平衡模式基础上，所有高风险和严重风险工具必须人工批准。",
        detect_prompt_injection=True,
        isolate_untrusted_instructions=True,
        enforce_tool_allowlist=True,
        block_sensitive_data=True,
        require_high_risk_approval=True,
    ),
}


def get_defense_profile(key: str, approve_high_risk_actions: bool = False) -> DefenseConfig:
    if key not in DEFENSE_PROFILES:
        raise KeyError(f"未知防御配置: {key}")
    return replace(
        DEFENSE_PROFILES[key], approve_high_risk_actions=approve_high_risk_actions
    )

