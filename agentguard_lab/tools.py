from __future__ import annotations

from time import perf_counter
from typing import Any

from .models import Scenario


class VirtualToolbox:
    """只修改内存状态的工具沙箱，不访问真实文件、邮箱、网络或日历。"""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.state: dict[str, list[dict[str, Any]]] = {
            "summaries": [],
            "calendar_events": [],
            "sent_emails": [],
            "exports": [],
            "deleted_files": [],
            "secret_reads": [],
        }

    def execute(self, tool: str, arguments: dict[str, Any]) -> tuple[str, float]:
        started = perf_counter()
        handler = getattr(self, f"_tool_{tool}", None)
        if handler is None:
            raise ValueError(f"虚拟工具箱不支持工具: {tool}")
        output = handler(arguments)
        duration_ms = (perf_counter() - started) * 1000
        return output, duration_ms

    def _tool_read_email(self, arguments: dict[str, Any]) -> str:
        email_id = arguments.get("email_id", "unknown")
        return f"虚拟邮件 {email_id} 内容：{self.scenario.untrusted_content}"

    def _tool_read_file(self, arguments: dict[str, Any]) -> str:
        path = arguments.get("path", "unknown")
        return f"虚拟文件 {path} 内容：{self.scenario.untrusted_content}"

    def _tool_search_knowledge_base(self, arguments: dict[str, Any]) -> str:
        query = arguments.get("query", "")
        return f"知识库检索“{query}”返回：{self.scenario.untrusted_content}"

    def _tool_create_summary(self, arguments: dict[str, Any]) -> str:
        self.state["summaries"].append(dict(arguments))
        return f"已在虚拟工作区创建摘要《{arguments.get('title', '未命名')}》"

    def _tool_create_calendar_event(self, arguments: dict[str, Any]) -> str:
        self.state["calendar_events"].append(dict(arguments))
        return f"已在虚拟日历创建事件“{arguments.get('title', '未命名')}”"

    def _tool_send_email(self, arguments: dict[str, Any]) -> str:
        self.state["sent_emails"].append(dict(arguments))
        return f"已在虚拟邮箱模拟发送邮件至 {arguments.get('to', 'unknown')}"

    def _tool_export_data(self, arguments: dict[str, Any]) -> str:
        self.state["exports"].append(dict(arguments))
        return f"已在内存中模拟导出数据至 {arguments.get('destination', 'unknown')}"

    def _tool_delete_file(self, arguments: dict[str, Any]) -> str:
        self.state["deleted_files"].append(dict(arguments))
        return f"已在虚拟工作区模拟删除 {arguments.get('path', 'unknown')}"

    def _tool_read_secret(self, arguments: dict[str, Any]) -> str:
        name = arguments.get("name", "UNKNOWN_SECRET")
        self.state["secret_reads"].append({"name": name})
        value = (
            self.scenario.sensitive_values[0]
            if self.scenario.sensitive_values
            else "EMPTY_CANARY"
        )
        return f"虚拟敏感配置 {name}={value}"
