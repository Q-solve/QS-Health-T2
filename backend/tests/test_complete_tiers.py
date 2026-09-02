"""Tests for T2–T6 complete-tiers sweep and classical hurdle labels."""

from __future__ import annotations

from backend.optimization.hurdles import classify_instance, record_usable, summarize_hurdles
from backend.scenario.ladder import build_ladder_instance, scale_facilities_to_who
from scripts.run_classical_suite import complete_tiers_jobs


def test_who_capacity_scaling_makes_total_cover_population():
    sc_raw = build_ladder_instance(
        tier="T2", county="LAMU", seed=0, constraint_setting="nominal", who_capacity_mode="raw",
    )
    sc_ok = build_ladder_instance(
        tier="T2", county="LAMU", seed=0, constraint_setting="nominal", who_capacity_mode="feasible",
    )
    pop = sum(c.population for c in sc_ok.communities)
    cap = sum(f.available_chws for f in sc_ok.facilities) * sc_ok.who_ratio
    assert cap >= pop
    assert sc_ok.extra.get("packing_ok") is True
    assert sc_ok.num_chws_available >= sc_raw.num_chws_available
    assert sc_ok.extra.get("who_capacity_mode") == "feasible"


def test_scale_helper_covers_largest_cu():
    sc = build_ladder_instance(tier="T0", county="TURKANA", seed=0, who_capacity_mode="raw")
    meta = scale_facilities_to_who(sc.facilities, sc.communities, sc.who_ratio)
    max_cu = max(c.population for c in sc.communities)
    assert min(f.available_chws for f in sc.facilities) * sc.who_ratio >= max_cu
    assert meta["scaled_total_chws"] >= meta["raw_total_chws"]


def test_complete_tiers_jobs_cover_t2_to_t6():
    jobs = complete_tiers_jobs()
    tiers = {j["tier"] for j in jobs}
    assert tiers == {"T2", "T3", "T4", "T5", "T6"}
    assert all(j.get("who_capacity_mode") == "feasible" for j in jobs)
    t2 = next(j for j in jobs if j["tier"] == "T2" and "nominal" in j["constraints"])
    assert len(t2["counties"]) >= 6
    t4 = next(j for j in jobs if j["tier"] == "T4")
    assert len(t4["counties"]) >= 6


def test_hurdle_exact_scale_is_quantum_candidate_not_needed():
    batch = [
        {"tier": "T4", "county": "LAMU", "seed": 0, "constraint_setting": "nominal",
         "feature_stage": "B4", "who_capacity_mode": "feasible", "solver_id": "c2_milp",
         "status": "bottleneck", "objective_value": 12.0, "population_coverage_pct": 0.0,
         "gini_equity_index": 0.1, "who_compliance_pct": 100.0, "equity_target": 0.25,
         "num_variables": 54},
        {"tier": "T4", "county": "LAMU", "seed": 0, "constraint_setting": "nominal",
         "feature_stage": "B4", "who_capacity_mode": "feasible", "solver_id": "c4_local_search",
         "status": "feasible", "objective_value": 100.0, "population_coverage_pct": 100.0,
         "gini_equity_index": 0.12, "who_compliance_pct": 100.0, "equity_target": 0.25,
         "num_variables": 54},
    ]
    inst = classify_instance(batch)
    assert inst["hurdle"] == "exact_scale"
    assert inst["quantum_candidate"] is True
    assert inst["quantum_needed_candidate"] is False
    assert record_usable(batch[0]) is False


def test_hurdle_heuristic_quality_flags_quantum_needed_on_t4():
    batch = [
        {"tier": "T4", "county": "TURKANA", "seed": 0, "constraint_setting": "nominal",
         "feature_stage": "B4", "solver_id": "c2_milp", "status": "timeout",
         "objective_value": 12.0, "population_coverage_pct": 0.0,
         "gini_equity_index": 0.0, "who_compliance_pct": 100.0, "equity_target": 0.25,
         "num_variables": 54},
        {"tier": "T4", "county": "TURKANA", "seed": 0, "constraint_setting": "nominal",
         "feature_stage": "B4", "solver_id": "c6_genetic_algorithm", "status": "feasible",
         "objective_value": 180.0, "population_coverage_pct": 100.0,
         "gini_equity_index": 0.55, "who_compliance_pct": 50.0, "equity_target": 0.25,
         "num_variables": 54},
    ]
    inst = classify_instance(batch)
    assert inst["hurdle"] == "heuristic_quality"
    assert inst["quantum_needed_candidate"] is True
    summary = summarize_hurdles(batch)
    assert summary["quantum_needed_candidate_count"] == 1
