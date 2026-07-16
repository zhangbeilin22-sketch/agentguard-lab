from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .models import DefenseConfig, GuardEvent, RiskLevel, Scenario, ToolCall, ToolSpec

INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("忽略既有指令", re.compile(r"忽略.{0,8}(之前|先前|已有|用户).{0,8}(指令|要求|规则)")),
    (
        "英文越权指令",
        re.compile(r"ignore\s+(all\s+)?(previous|prior).{0,20}(instructions|rules)", re.I),
    ),
    (
        "伪造系统身份",
        re.compile(r"(system\s+message|系统管理员指令|重要系统指令|隐藏管理员任务)", re.I),
    ),
    (
        "强制工具调用",
        re.compile(r"(必须执行|立即执行|模型必须执行|call\s+[a-z_]+|调用\s*[a-z_]+)", re.I),
    ),
    ("绕过用户确认", re.compile(r"(不需要|无需).{0,8}(确认|告知|批准|审批)")),
    ("敏感数据外发", re.compile(r"(令牌|密钥|token|secret).{0,30}(发送|发给|导出|上传)", re.I)),
)

CANARY_PATTERN = re.compile(r"AGENTGUARD_[A-Z0-9_]*CANARY[A-Z0-9_]*", re.I)


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    status: str
    event: GuardEvent | None = None


def scan_for_prompt_injection(content: str, enabled: bool) -> tuple[bool, GuardEvent | None]:
    if not enabled:
        return False, None

    matched = [label for label, pattern in INJECTION_PATTERNS if pattern.search(content)]
    detected = bool(matched)
    reason = (
        f"检测到可疑特征：{'、'.join(matched)}"
        if detected
        else "未检测到已知提示词注入特征"
    )
    return detected, GuardEvent(
        guardrail="提示词注入检测器",
        triggered=detected,
        reason=reason,
        action="告警" if detected else "通过",
    )


def assess_tool_call(
    call: ToolCall,
    spec: ToolSpec,
    scenario: Scenario,
    defense: DefenseConfig,
    injection_detected: bool,
) -> GuardDecision:
    if (
        defense.isolate_untrusted_instructions
        and injection_detected
        and call.origin == "untrusted_content"
    ):
        return _blocked(
            "不可信指令隔离器",
            call.tool,
            "该工具调用来自检测到注入特征的不可信内容，已与用户指令隔离。",
        )

    if defense.enforce_tool_allowlist and call.tool not in scenario.allowed_tools:
        return _blocked(
            "最小权限工具白名单",
            call.tool,
            f"工具 {call.tool} 不在当前任务白名单中。",
        )

    if defense.block_sensitive_data and _contains_sensitive_data(call, scenario):
        return _blocked(
            "敏感数据防泄漏",
            call.tool,
            "工具参数中检测到实验用金丝雀敏感值，已阻止外发或处理。",
        )

    needs_approval = spec.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    if (
        defense.require_high_risk_approval
        and needs_approval
        and not defense.approve_high_risk_actions
    ):
        return GuardDecision(
            allowed=False,
            status="待审批",
            event=GuardEvent(
                guardrail="高风险操作人工审批",
                triggered=True,
                reason=f"{spec.display_name} 的风险等级为“{spec.risk.value}”，需要人工批准。",
                tool=call.tool,
                action="等待审批",
            ),
        )

    return GuardDecision(allowed=True, status="已执行")


def _contains_sensitive_data(call: ToolCall, scenario: Scenario) -> bool:
    serialized = json.dumps(call.arguments, ensure_ascii=False, sort_keys=True)
    if CANARY_PATTERN.search(serialized):
        return True
    return any(value and value in serialized for value in scenario.sensitive_values)


def _blocked(guardrail: str, tool: str, reason: str) -> GuardDecision:
    return GuardDecision(
        allowed=False,
        status="已阻断",
        event=GuardEvent(
            guardrail=guardrail,
            triggered=True,
            reason=reason,
            tool=tool,
            action="阻断",
        ),
    )
