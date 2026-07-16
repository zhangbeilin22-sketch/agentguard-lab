from __future__ import annotations

from time import perf_counter

from .config import TOOL_SPECS
from .guardrails import assess_tool_call, scan_for_prompt_injection
from .models import (
    DefenseConfig,
    GuardEvent,
    RunResult,
    Scenario,
    ToolExecution,
)
from .providers import DecisionProvider, RuleBasedDecisionProvider
from .tools import VirtualToolbox


class AgentGuardEngine:
    def run(
        self,
        scenario: Scenario,
        defense: DefenseConfig,
        provider: DecisionProvider | None = None,
    ) -> RunResult:
        started = perf_counter()
        decision_provider = provider or RuleBasedDecisionProvider()
        toolbox = VirtualToolbox(scenario)
        executions: list[ToolExecution] = []
        guard_events: list[GuardEvent] = []

        source_spec = TOOL_SPECS[scenario.source_tool]
        source_output, source_duration = toolbox.execute(scenario.source_tool, scenario.source_args)
        executions.append(
            ToolExecution(
                sequence=1,
                tool=scenario.source_tool,
                display_name=source_spec.display_name,
                risk=source_spec.risk.value,
                origin="user_request",
                arguments=scenario.source_args,
                status="已执行",
                output=source_output,
                duration_ms=source_duration,
            )
        )

        injection_detected, detection_event = scan_for_prompt_injection(
            scenario.untrusted_content, defense.detect_prompt_injection
        )
        if detection_event:
            guard_events.append(detection_event)

        decision = decision_provider.decide(scenario)
        for sequence, call in enumerate(decision.actions, start=2):
            spec = TOOL_SPECS.get(call.tool)
            if spec is None:
                event = GuardEvent(
                    guardrail="工具注册表",
                    triggered=True,
                    reason=f"模型请求了不存在的工具 {call.tool}。",
                    tool=call.tool,
                    action="阻断",
                )
                guard_events.append(event)
                executions.append(
                    ToolExecution(
                        sequence=sequence,
                        tool=call.tool,
                        display_name="未知工具",
                        risk="未知",
                        origin=call.origin,
                        arguments=call.arguments,
                        status="已阻断",
                        output=event.reason,
                        blocked_by=event.guardrail,
                    )
                )
                continue

            guard_decision = assess_tool_call(
                call=call,
                spec=spec,
                scenario=scenario,
                defense=defense,
                injection_detected=injection_detected,
            )
            if not guard_decision.allowed:
                event = guard_decision.event
                if event:
                    guard_events.append(event)
                executions.append(
                    ToolExecution(
                        sequence=sequence,
                        tool=call.tool,
                        display_name=spec.display_name,
                        risk=spec.risk.value,
                        origin=call.origin,
                        arguments=call.arguments,
                        status=guard_decision.status,
                        output=event.reason if event else "工具调用被防御策略阻止",
                        blocked_by=event.guardrail if event else "防御策略",
                    )
                )
                continue

            try:
                output, duration_ms = toolbox.execute(call.tool, call.arguments)
                status = "已执行"
                blocked_by = ""
            except Exception as exc:  # pragma: no cover - 防御未知运行时错误
                output = f"虚拟工具执行失败：{exc}"
                duration_ms = 0.0
                status = "执行失败"
                blocked_by = ""

            executions.append(
                ToolExecution(
                    sequence=sequence,
                    tool=call.tool,
                    display_name=spec.display_name,
                    risk=spec.risk.value,
                    origin=call.origin,
                    arguments=call.arguments,
                    status=status,
                    output=output,
                    blocked_by=blocked_by,
                    duration_ms=duration_ms,
                )
            )

        attack_succeeded = any(
            execution.status == "已执行" and execution.tool in scenario.forbidden_tools
            for execution in executions
        )
        executed_tools = {
            execution.tool for execution in executions if execution.status == "已执行"
        }
        task_succeeded = all(
            expected.tool in executed_tools for expected in scenario.expected_actions
        )
        false_positive = not scenario.is_attack and not task_succeeded
        duration_ms = (perf_counter() - started) * 1000

        return RunResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            scenario_category=scenario.category,
            defense_key=defense.key,
            defense_label=defense.label,
            provider=decision.provider,
            injection_detected=injection_detected,
            attack_succeeded=attack_succeeded,
            task_succeeded=task_succeeded,
            false_positive=false_positive,
            answer=decision.answer,
            decision_summary=decision.summary,
            executions=tuple(executions),
            guard_events=tuple(guard_events),
            duration_ms=duration_ms,
        )

