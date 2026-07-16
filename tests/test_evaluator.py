from agentguard_lab.config import get_defense_profile
from agentguard_lab.evaluator import evaluate_profile
from agentguard_lab.scenarios import load_scenarios


def test_expected_profile_metrics():
    scenarios = load_scenarios()

    baseline, _ = evaluate_profile(scenarios, get_defense_profile("baseline"))
    detection, _ = evaluate_profile(scenarios, get_defense_profile("detection"))
    balanced, _ = evaluate_profile(scenarios, get_defense_profile("balanced"))
    strict, _ = evaluate_profile(scenarios, get_defense_profile("strict"))

    assert baseline.attack_success_rate == 100.0
    assert baseline.injection_detection_rate == 0.0
    assert detection.attack_success_rate == 100.0
    assert detection.injection_detection_rate == 100.0
    assert balanced.attack_success_rate == 0.0
    assert balanced.task_success_rate == 100.0
    assert strict.attack_success_rate == 0.0
    assert strict.task_success_rate == 90.0
    assert strict.false_positive_rate == 20.0
    assert balanced.overall_score > strict.overall_score > detection.overall_score

