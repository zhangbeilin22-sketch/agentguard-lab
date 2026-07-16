from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agentguard_lab.config import DEFENSE_PROFILES, TOOL_SPECS, get_defense_profile
from agentguard_lab.engine import AgentGuardEngine
from agentguard_lab.evaluator import evaluate_profile
from agentguard_lab.models import DefenseConfig, RunResult
from agentguard_lab.providers import OpenAICompatibleDecisionProvider, RuleBasedDecisionProvider
from agentguard_lab.scenarios import load_scenarios

load_dotenv()

st.set_page_config(
    page_title="AgentGuard Lab",
    page_icon=":material/security:",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1440px;}
    [data-testid="stMetric"] {border: 1px solid #d9dee7; border-radius: 6px; padding: 12px;}
    [data-testid="stSidebar"] {border-right: 1px solid #d9dee7;}
    .status-safe {border-left: 4px solid #16845b; padding: 10px 14px; background: #edf8f3;}
    .status-danger {border-left: 4px solid #c33c3c; padding: 10px 14px; background: #fff1f1;}
    .status-warn {border-left: 4px solid #b7791f; padding: 10px 14px; background: #fff8e8;}
    code {font-size: 0.9em;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def cached_scenarios():
    return load_scenarios()


def build_defense_config() -> DefenseConfig:
    labels = {key: profile.label for key, profile in DEFENSE_PROFILES.items()}
    labels["custom"] = "自定义模式：手动组合防御"
    selected = st.sidebar.selectbox(
        "防御配置",
        options=list(labels),
        format_func=lambda key: labels[key],
        index=2,
    )

    if selected != "custom":
        approve = False
        if selected == "strict":
            approve = st.sidebar.toggle("模拟人工批准高风险操作", value=False)
        config = get_defense_profile(selected, approve)
        st.sidebar.caption(config.description)
        return config

    st.sidebar.caption("组合不同策略，观察单一防线和纵深防御的效果差异。")
    detect = st.sidebar.toggle("提示词注入检测", value=True)
    isolate = st.sidebar.toggle("隔离不可信内容中的指令", value=True)
    allowlist = st.sidebar.toggle("强制工具白名单", value=True)
    dlp = st.sidebar.toggle("敏感数据防泄漏", value=True)
    approval = st.sidebar.toggle("高风险工具人工审批", value=False)
    approved = st.sidebar.toggle("模拟批准高风险操作", value=False, disabled=not approval)
    return DefenseConfig(
        key="custom",
        label="自定义防御配置",
        description="由用户在侧边栏组合的防御策略。",
        detect_prompt_injection=detect,
        isolate_untrusted_instructions=isolate,
        enforce_tool_allowlist=allowlist,
        block_sensitive_data=dlp,
        require_high_risk_approval=approval,
        approve_high_risk_actions=approved,
    )


def build_provider():
    mode = st.sidebar.radio(
        "决策引擎",
        ["本地规则引擎（无需 API）", "真实模型接口（OpenAI 兼容）"],
    )
    if mode.startswith("本地"):
        st.sidebar.caption("结果完全可复现，适合演示和自动化测试。")
        return RuleBasedDecisionProvider(), True

    with st.sidebar.expander("模型接口配置", expanded=True):
        base_url = st.text_input(
            "接口地址",
            value=os.getenv("LLM_BASE_URL", ""),
            placeholder="https://api.example.com/v1",
        )
        model = st.text_input(
            "模型名称",
            value=os.getenv("LLM_MODEL", ""),
            placeholder="填写服务商提供的模型标识",
        )
        api_key = st.text_input(
            "API Key",
            value=os.getenv("LLM_API_KEY", ""),
            type="password",
        )

    ready = bool(base_url and model and api_key)
    if not ready:
        st.sidebar.warning("请完整填写接口地址、模型名称和 API Key。")
        return None, False
    return OpenAICompatibleDecisionProvider(base_url, api_key, model), True


def render_result(result: RunResult) -> None:
    if result.attack_succeeded:
        st.markdown(
            '<div class="status-danger"><strong>攻击成功：</strong>'
            "至少一个禁止工具被执行。当前 Agent 存在安全风险。</div>",
            unsafe_allow_html=True,
        )
    elif result.scenario_category != "benign":
        st.markdown(
            '<div class="status-safe"><strong>攻击被阻止：</strong>'
            "禁止工具没有执行，防御策略生效。</div>",
            unsafe_allow_html=True,
        )
    elif result.task_succeeded:
        st.markdown(
            '<div class="status-safe"><strong>正常任务完成：</strong>'
            "预期工具成功执行，没有发生误拦截。</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="status-warn"><strong>正常任务未完成：</strong>'
            "防御策略阻止了预期操作，需要检查安全性与可用性的平衡。</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    metric_columns = st.columns(5)
    metric_columns[0].metric("攻击是否成功", "是" if result.attack_succeeded else "否")
    metric_columns[1].metric("任务是否完成", "是" if result.task_succeeded else "否")
    metric_columns[2].metric("注入是否检出", "是" if result.injection_detected else "否")
    metric_columns[3].metric(
        "阻断调用数",
        sum(item.status in {"已阻断", "待审批"} for item in result.executions),
    )
    metric_columns[4].metric("执行耗时", f"{result.duration_ms:.2f} ms")

    st.subheader("工具调用审计轨迹")
    execution_rows = []
    for item in result.executions:
        execution_rows.append(
            {
                "步骤": item.sequence,
                "工具": f"{item.display_name} ({item.tool})",
                "风险": item.risk,
                "来源": "不可信内容" if item.origin == "untrusted_content" else "用户任务",
                "状态": item.status,
                "阻断策略": item.blocked_by or "-",
                "参数": json.dumps(item.arguments, ensure_ascii=False),
                "结果": item.output,
            }
        )
    st.dataframe(
        pd.DataFrame(execution_rows),
        width="stretch",
        hide_index=True,
        column_config={
            "步骤": st.column_config.NumberColumn(width="small"),
            "风险": st.column_config.TextColumn(width="small"),
            "来源": st.column_config.TextColumn(width="small"),
            "状态": st.column_config.TextColumn(width="small"),
            "参数": st.column_config.TextColumn(width="large"),
            "结果": st.column_config.TextColumn(width="large"),
        },
    )

    left, right = st.columns([1, 1])
    with left:
        st.subheader("防御事件")
        if result.guard_events:
            event_rows = [
                {
                    "防线": event.guardrail,
                    "触发": "是" if event.triggered else "否",
                    "动作": event.action,
                    "工具": event.tool or "-",
                    "原因": event.reason,
                }
                for event in result.guard_events
            ]
            st.dataframe(pd.DataFrame(event_rows), width="stretch", hide_index=True)
        else:
            st.info("当前配置没有启用防御策略，因此没有防御事件。")

    with right:
        st.subheader("Agent 决策摘要")
        st.write(result.decision_summary)
        st.caption(f"决策引擎：{result.provider}")
        st.write(result.answer)

    st.download_button(
        "导出本次审计报告",
        data=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        file_name=f"agentguard-{result.scenario_id}-{result.defense_key}.json",
        mime="application/json",
    )


scenarios = cached_scenarios()

st.title("AgentGuard Lab")
st.caption("大模型 Agent 提示词注入攻防与安全评测实验室")

st.sidebar.header("实验配置")
defense_config = build_defense_config()
provider, provider_ready = build_provider()

single_tab, batch_tab, method_tab = st.tabs(["单场景实验", "批量安全评测", "实验方法"])

with single_tab:
    scenario_map = {scenario.id: scenario for scenario in scenarios}
    selected_id = st.selectbox(
        "选择测试场景",
        options=list(scenario_map),
        format_func=lambda item: scenario_map[item].name,
    )
    scenario = scenario_map[selected_id]

    info_columns = st.columns([1, 1, 2])
    info_columns[0].metric("场景类型", "攻击" if scenario.is_attack else "正常")
    info_columns[1].metric("难度", scenario.difficulty)
    info_columns[2].metric("标签", " / ".join(scenario.tags))

    st.subheader("用户任务")
    st.write(scenario.user_request)
    with st.expander("查看工具返回的不可信内容", expanded=scenario.is_attack):
        st.code(scenario.untrusted_content, language=None, wrap_lines=True)
        st.caption("该文本只来自虚拟场景数据，不会访问真实邮箱、文件或知识库。")

    if st.button("运行安全实验", type="primary", disabled=not provider_ready):
        try:
            with st.spinner("正在执行 Agent 决策和安全检查..."):
                result = AgentGuardEngine().run(scenario, defense_config, provider)
            st.session_state["single_result"] = result
        except Exception as exc:
            st.error(f"实验运行失败：{exc}")

    stored_result = st.session_state.get("single_result")
    if stored_result and stored_result.scenario_id == scenario.id:
        st.divider()
        render_result(stored_result)

with batch_tab:
    st.subheader("四组防御配置对比")
    st.write(
        "批量评测固定使用本地规则引擎，保证每次结果一致。真实模型可能产生接口费用，"
        "因此只在单场景实验中调用。"
    )
    if st.button("运行全部场景评测", type="primary"):
        metric_items = []
        result_groups = {}
        with st.spinner("正在运行 10 个场景和 4 组防御配置..."):
            for key in DEFENSE_PROFILES:
                config = get_defense_profile(key)
                metrics, results = evaluate_profile(scenarios, config)
                metric_items.append(metrics)
                result_groups[key] = results
        st.session_state["batch_metrics"] = metric_items
        st.session_state["batch_results"] = result_groups

    metrics_list = st.session_state.get("batch_metrics")
    result_groups = st.session_state.get("batch_results")
    if metrics_list and result_groups:
        rows = [
            {
                "配置": item.profile_label,
                "攻击成功率 (%)": item.attack_success_rate,
                "任务成功率 (%)": item.task_success_rate,
                "误拦截率 (%)": item.false_positive_rate,
                "注入检测率 (%)": item.injection_detection_rate,
                "平均阻断调用": item.average_blocked_calls,
                "综合分": item.overall_score,
            }
            for item in metrics_list
        ]
        frame = pd.DataFrame(rows)
        st.dataframe(frame, width="stretch", hide_index=True)

        chart_frame = frame.set_index("配置")[[
            "攻击成功率 (%)",
            "任务成功率 (%)",
            "注入检测率 (%)",
        ]]
        st.bar_chart(chart_frame, horizontal=True, height=360)

        best = max(metrics_list, key=lambda item: item.overall_score)
        st.success(f"当前测试集综合表现最佳：{best.profile_label}，综合分 {best.overall_score}。")

        st.subheader("逐场景结果")
        detail_key = st.selectbox(
            "查看配置",
            options=list(result_groups),
            format_func=lambda key: DEFENSE_PROFILES[key].label,
            key="batch_detail_profile",
        )
        detail_rows = [
            {
                "场景": result.scenario_name,
                "类型": "攻击" if result.scenario_category != "benign" else "正常",
                "检出注入": "是" if result.injection_detected else "否",
                "攻击成功": "是" if result.attack_succeeded else "否",
                "任务完成": "是" if result.task_succeeded else "否",
                "误拦截": "是" if result.false_positive else "否",
            }
            for result in result_groups[detail_key]
        ]
        st.dataframe(pd.DataFrame(detail_rows), width="stretch", hide_index=True)

        st.download_button(
            "导出评测指标 CSV",
            data=frame.to_csv(index=False).encode("utf-8-sig"),
            file_name="agentguard-evaluation.csv",
            mime="text/csv",
        )

with method_tab:
    st.subheader("安全边界")
    st.write(
        "所有工具均由 VirtualToolbox 在内存中模拟。发送邮件、删除文件、导出数据、读取密钥"
        "都只会写入临时 Python 字典，不会访问网络、操作系统文件、真实邮箱或真实密钥。"
    )

    st.subheader("防御流水线")
    st.code(
        "不可信内容 → 注入检测 → 指令隔离 → 工具白名单 → 敏感数据检查 → 人工审批 → 虚拟工具箱",
        language=None,
    )

    tool_rows = [
        {
            "工具": spec.display_name,
            "标识": spec.name,
            "风险": spec.risk.value,
            "有副作用": "是" if spec.side_effect else "否",
            "说明": spec.description,
        }
        for spec in TOOL_SPECS.values()
    ]
    st.dataframe(pd.DataFrame(tool_rows), width="stretch", hide_index=True)

    st.subheader("核心指标")
    st.markdown(
        "- **攻击成功率（ASR）**：攻击场景中，至少一个禁止工具成功执行的比例。\n"
        "- **任务成功率（TSR）**：全部场景中，预期业务工具成功执行的比例。\n"
        "- **误拦截率（FPR）**：正常场景中，预期操作被防御策略阻止的比例。\n"
        "- **注入检测率**：攻击场景中，检测器命中可疑特征的比例。"
    )
