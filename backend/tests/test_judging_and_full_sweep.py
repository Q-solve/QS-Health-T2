"""Tests for Q-SOLVE judging context + all-county classical sweep."""

from __future__ import annotations

from backend.judging import build_judging_evidence, judging_scorecard_template
from backend.optimization.compare import compare_classical_suite_all_scenarios
from backend.scenario.sample_scenarios import SAMPLE_SCENARIOS


def test_judging_scorecard_has_seven_criteria():
    card = judging_scorecard_template()
    assert len(card["criteria"]) == 7
    assert card["criteria"]["JC2"]["max_score"] == 20
    assert "Small" in card["environment_target"]["qbraid_lab_instance"]


def test_judging_evidence_flags_single_location_gap():
    ev = build_judging_evidence(counties_covered=1, scenarios_run=1, classical_methods_run=3)
    assert "JC1.multi_county_not_single_demo" in ev["evidence_gaps"]


def test_all_scenarios_sweep_subset():
    names = list(SAMPLE_SCENARIOS.keys())[:2]
    payload = compare_classical_suite_all_scenarios(
        time_budget_sec=2.0,
        seed=0,
        include=["c3_greedy", "c1_brute_force"],
        scenario_names=names,
    )
    assert payload["county_count"] >= 1
    assert "q_solve_judging" in payload
    assert payload["q_solve_judging"]["auto_checklist"]["JC6"]["sdg3_health_metrics"] == "PASS"
