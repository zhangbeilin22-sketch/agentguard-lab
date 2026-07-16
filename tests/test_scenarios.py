from agentguard_lab.scenarios import load_scenarios


def test_builtin_scenarios_are_balanced_and_valid():
    scenarios = load_scenarios()

    assert len(scenarios) == 10
    assert sum(item.is_attack for item in scenarios) == 5
    assert sum(not item.is_attack for item in scenarios) == 5
    assert len({item.id for item in scenarios}) == len(scenarios)


def test_attack_destinations_are_non_routable_or_in_memory():
    scenarios = load_scenarios()
    serialized = str([call.arguments for item in scenarios for call in item.injected_actions])

    assert "external.invalid" in serialized or "memory://external" in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized

