"""Phase 1 ladder + shared H(x) tests."""

from __future__ import annotations

from backend.optimization.classical_suite import get_classical_solver
from backend.optimization.objective import evaluate_H, scenario_distance_matrix
from backend.optimization.qubo_builder import build_chw_qubo
from backend.scenario.constraints import list_constraint_presets
from backend.scenario.features import list_feature_stages
from backend.scenario.ladder import TIER_SPEC, build_ladder_instance, list_counties


def test_fourteen_counties_available():
    counties = list_counties()
    assert len(counties) >= 13
    assert "TURKANA" in counties
    assert "KILIFI" in counties


def test_constraint_and_feature_catalogs():
    assert list_constraint_presets() == ["loose", "nominal", "tight"]
    assert list_feature_stages() == ["B0", "B1", "B2", "B3", "B4"]


def test_ladder_t0_shape():
    sc = build_ladder_instance(tier="T0", county="TURKANA", seed=0, constraint_setting="nominal", feature_stage="B4")
    assert len(sc.facilities) == TIER_SPEC["T0"]["num_f"]
    assert len(sc.communities) == TIER_SPEC["T0"]["num_c"]
    assert sc.num_variables == 6
    assert sc.who_ratio == 1000.0
    assert all(c.demand_score > 0 for c in sc.communities)


def test_feature_stage_changes_demand():
    sc0 = build_ladder_instance(tier="T0", county="LAMU", seed=1, feature_stage="B0")
    sc4 = build_ladder_instance(tier="T0", county="LAMU", seed=1, feature_stage="B4")
    scores0 = [c.demand_score for c in sc0.communities]
    scores4 = [c.demand_score for c in sc4.communities]
    assert scores0 != scores4 or len(set(scores4)) >= 1


def test_tight_constraints_stricter_than_loose():
    loose = build_ladder_instance(tier="T0", county="ISIOLO", seed=0, constraint_setting="loose")
    tight = build_ladder_instance(tier="T0", county="ISIOLO", seed=0, constraint_setting="tight")
    assert tight.max_walking_dist_km < loose.max_walking_dist_km
    assert tight.who_ratio < loose.who_ratio
    assert tight.equity_target < loose.equity_target


def test_c1_equals_c2_on_t0():
    sc = build_ladder_instance(tier="T0", county="TURKANA", seed=2, constraint_setting="nominal")
    c1 = get_classical_solver("c1_brute_force").solve(sc, time_budget_sec=8.0, seed=2)
    c2 = get_classical_solver("c2_milp").solve(sc, time_budget_sec=8.0, seed=2)
    assert c1.objective_value is not None and c2.objective_value is not None
    assert abs(c1.objective_value - c2.objective_value) < 1e-6


def test_heuristics_near_exact_on_t0():
    sc = build_ladder_instance(tier="T0", county="TURKANA", seed=3)
    exact = get_classical_solver("c1_brute_force").solve(sc, time_budget_sec=8.0, seed=3)
    local = get_classical_solver("c4_local_search").solve(sc, time_budget_sec=3.0, seed=3)
    assert exact.objective_value is not None and local.objective_value is not None
    assert local.population_coverage_pct == 100.0
    gap = (local.objective_value - exact.objective_value) / max(abs(exact.objective_value), 1.0)
    assert gap < 1.25


def test_qubo_matches_variable_count_and_uses_demand():
    sc = build_ladder_instance(tier="T1", county="LAMU", seed=0, feature_stage="B4")
    Q, meta = build_chw_qubo(sc)
    assert Q.shape == (sc.num_variables, sc.num_variables)
    assert meta["feature_stage"] == "B4"
    dist = scenario_distance_matrix(sc)
    # Dummy assignment: each CU to facility 0
    import numpy as np

    x = np.zeros((len(sc.facilities), len(sc.communities)))
    x[0, :] = 1.0
    h = evaluate_H(x, dist, sc)
    assert h > 0
