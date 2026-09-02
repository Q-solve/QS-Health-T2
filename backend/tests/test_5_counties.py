"""Tests verifying the 14 Target Marginalised Counties scenarios and NISQ qubit capping."""

from backend.scenario.sample_scenarios import SAMPLE_SCENARIOS


def test_target_counties_presence():
    counties = {s.county for s in SAMPLE_SCENARIOS.values()}
    expected = {
        "Turkana", "Garissa", "Mandera", "Kilifi", "Wajir", 
        "Taita Taveta", "Marsabit", "Isiolo", "Samburu", "Lamu", 
        "West Pokot", "Tana River", "Narok", "Kwale"
    }
    assert expected.issubset(counties), f"Missing target counties: {expected - counties}"


def test_nisq_qubit_limits():
    for name, scenario in SAMPLE_SCENARIOS.items():
        qubits = len(scenario.facilities) * len(scenario.communities)
        assert qubits <= 12, f"Scenario '{name}' exceeds NISQ qubit limit (12 qubits max): got {qubits}"
