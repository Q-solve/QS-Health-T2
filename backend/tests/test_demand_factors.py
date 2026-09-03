"""Demand-factor selection must change y_j, H(x), and QUBO for classical + quantum paths."""

from __future__ import annotations

import numpy as np

from backend.optimization.classical_suite.c3_greedy.solver import GreedyNearestNeighborSolver
from backend.optimization.objective import (
    bitstring_to_matrix,
    build_solution_result,
    decompose_H,
    demand_vector,
    empty_matrix,
    evaluate_H,
    scenario_distance_matrix,
)
from backend.optimization.qubo_builder import build_chw_qubo
from backend.scenario.constraints import resolve_constraints
from backend.scenario.features import default_enabled_factors, list_demand_factors
from backend.scenario.ladder import build_ladder_instance


def test_demand_factor_catalog_has_plain_labels():
    catalog = list_demand_factors("B4")
    assert len(catalog) >= 10
    ids = {f["id"] for f in catalog}
    assert "flood_risk_flag" in ids
    assert "vulnerability_score" in ids
    for item in catalog:
        assert item["label"]
        assert item["group"]


def test_constraint_overrides_apply():
    resolved = resolve_constraints(
        "nominal",
        max_walking_dist_km=4.0,
        who_ratio=900.0,
        equity_target=0.2,
    )
    assert resolved["max_walking_dist_km"] == 4.0
    assert resolved["who_ratio"] == 900.0
    assert resolved["equity_target"] == 0.2
    assert resolved["overrides_applied"]["max_walking_dist_km"] is True


def test_enabled_factors_change_demand_and_objective():
    base_factors = default_enabled_factors("B4")
    lean = ["vulnerability_score", "under5_share", "access_need"]

    sc_all = build_ladder_instance(
        tier="T0",
        county="LAMU",
        seed=0,
        constraint_setting="nominal",
        feature_stage="B4",
        who_capacity_mode="feasible",
        enabled_factors=base_factors,
    )
    sc_lean = build_ladder_instance(
        tier="T0",
        county="LAMU",
        seed=0,
        constraint_setting="nominal",
        feature_stage="B4",
        who_capacity_mode="feasible",
        enabled_factors=lean,
    )

    y_all = demand_vector(sc_all)
    y_lean = demand_vector(sc_lean)
    assert y_all.shape == y_lean.shape
    assert not np.allclose(y_all, y_lean), "Selecting different factors must change y_j"

    # Same nearest-facility assignment matrix
    dist = scenario_distance_matrix(sc_all)
    x = empty_matrix(sc_all)
    for j in range(x.shape[1]):
        i = int(np.argmin(dist[:, j]))
        x[i, j] = 1.0

    h_all = evaluate_H(x, dist, sc_all)
    # Rebuild dist for lean (geography identical for same seed/tier/county)
    dist_lean = scenario_distance_matrix(sc_lean)
    h_lean = evaluate_H(x, dist_lean, sc_lean)
    assert h_all != h_lean, "H(x) must change when demand factors change"


def test_enabled_factors_change_qubo():
    sc_a = build_ladder_instance(
        tier="T0",
        county="LAMU",
        seed=1,
        feature_stage="B4",
        who_capacity_mode="feasible",
        enabled_factors=default_enabled_factors("B4"),
    )
    sc_b = build_ladder_instance(
        tier="T0",
        county="LAMU",
        seed=1,
        feature_stage="B4",
        who_capacity_mode="feasible",
        enabled_factors=["flood_risk_flag", "seasonal_mobility_flag", "poverty_overall_pct"],
    )
    ya = demand_vector(sc_a)
    yb = demand_vector(sc_b)
    assert not np.allclose(ya, yb), "Selected factors must change y_j before QUBO"
    Qa, _ = build_chw_qubo(sc_a)
    Qb, _ = build_chw_qubo(sc_b)
    assert Qa.shape == Qb.shape
    # Capacity terms dominate absolute scale; check absolute diagonal drift from travel×y
    assert float(np.max(np.abs(np.diag(Qa) - np.diag(Qb)))) > 1e-6


def test_custom_walk_cap_on_ladder():
    sc = build_ladder_instance(
        tier="T0",
        county="TURKANA",
        seed=0,
        constraint_setting="nominal",
        max_walking_dist_km=3.5,
        who_ratio=850.0,
        equity_target=0.18,
        who_capacity_mode="feasible",
    )
    assert sc.max_walking_dist_km == 3.5
    assert sc.who_ratio == 850.0
    assert sc.equity_target == 0.18
    assert sc.extra.get("enabled_factors")


def test_catalog_includes_unified_maternal_and_risk_columns():
    ids = {f["id"] for f in list_demand_factors("B4")}
    for key in (
        "facility_delivery_pct",
        "skilled_delivery_pct",
        "anc4_pct",
        "hh_itn_ownership_pct",
        "ccri_risk_index",
    ):
        assert key in ids


def test_num_chws_total_override():
    sc = build_ladder_instance(
        tier="T0",
        county="TURKANA",
        seed=0,
        who_capacity_mode="feasible",
        num_chws_total=100,
    )
    assert sc.extra.get("who_capacity_mode") == "user"
    assert sc.num_chws_available == 100
    assert sum(f.available_chws for f in sc.facilities) == sc.num_chws_available
    assert sc.extra.get("user_total_chws") == float(sc.num_chws_available)


def test_num_chws_total_not_inflated_on_county():
    sc = build_ladder_instance(
        tier="T5",
        county="TURKANA",
        seed=0,
        who_capacity_mode="user",
        num_chws_total=20,
    )
    assert sc.num_chws_available == 20
    assert sum(f.available_chws for f in sc.facilities) == 20
    assert sc.extra.get("headcount_raised") is False


def test_solution_result_aligned_with_objective_terms():
    """Results must report H(x*) decomposed over the same core variables as evaluate_H."""
    sc = build_ladder_instance(
        tier="T0",
        county="LAMU",
        seed=0,
        who_capacity_mode="feasible",
        enabled_factors=["flood_risk_flag", "poverty_overall_pct", "vulnerability_score"],
    )
    res = GreedyNearestNeighborSolver().solve(sc, time_budget_sec=5.0, seed=0)
    assert res.objective_value is not None
    assert res.objective_terms
    assert abs(sum(res.objective_terms.values()) - float(res.objective_value)) < 1e-5
    assert res.demand_weighted_travel is not None
    assert "travel" in res.objective_terms
    assert res.objective_inputs.get("enabled_factors") == [
        "flood_risk_flag",
        "poverty_overall_pct",
        "vulnerability_score",
    ]
    assert res.objective_inputs.get("max_walking_dist_km") == sc.max_walking_dist_km
    assert res.assignments
    for a in res.assignments:
        assert a.walking_distance_km >= 0
        assert a.demand_score is not None
        assert a.population is not None

    dist = scenario_distance_matrix(sc)
    x = bitstring_to_matrix(res.bitstring, len(sc.facilities), len(sc.communities))
    decomp = decompose_H(x, dist, sc)
    assert abs(decomp["objective_value"] - float(res.objective_value)) < 1e-5
    assert abs(decomp["raw"]["demand_weighted_travel"] - float(res.demand_weighted_travel)) < 1e-5

    rebuilt = build_solution_result(sc, x, solver_type="test", execution_time_sec=0.0)
    assert rebuilt.objective_terms == decomp["terms"]
