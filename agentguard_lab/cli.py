from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import DEFENSE_PROFILES, get_defense_profile
from .evaluator import evaluate_profile
from .scenarios import load_scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentGuard Lab 批量安全评测")
    parser.add_argument(
        "--profile",
        choices=[*DEFENSE_PROFILES, "all"],
        default="all",
        help="选择防御配置，默认评测全部配置",
    )
    parser.add_argument(
        "--approve-high-risk",
        action="store_true",
        help="模拟人工批准高风险工具调用",
    )
    parser.add_argument("--json", type=Path, help="将评测结果写入指定 JSON 文件")
    args = parser.parse_args()

    scenarios = load_scenarios()
    keys = list(DEFENSE_PROFILES) if args.profile == "all" else [args.profile]
    report: list[dict] = []

    print("AgentGuard Lab 批量评测")
    print(f"场景数量：{len(scenarios)}")
    print("-" * 88)
    print(f"{'配置':<24}{'攻击成功率':>12}{'任务成功率':>12}{'误拦截率':>12}{'检测率':>10}{'综合分':>10}")

    for key in keys:
        defense = get_defense_profile(key, args.approve_high_risk)
        metrics, results = evaluate_profile(scenarios, defense)
        report.append(
            {
                "metrics": metrics.to_dict(),
                "results": [result.to_dict() for result in results],
            }
        )
        print(
            f"{key:<24}"
            f"{metrics.attack_success_rate:>11.1f}%"
            f"{metrics.task_success_rate:>11.1f}%"
            f"{metrics.false_positive_rate:>11.1f}%"
            f"{metrics.injection_detection_rate:>9.1f}%"
            f"{metrics.overall_score:>10.1f}"
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n报告已写入：{args.json}")


if __name__ == "__main__":
    main()

