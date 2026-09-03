"""Tests for classical ranking + quantum opportunity evaluation payload."""

from __future__ import annotations

from backend.optimization.classical_evaluation import (
    QUANTUM_OPPORTUNITY_CATALOGUE,
    build_classical_quantum_evaluation,
    rank_classical_solvers,
)


def test_rank_classical_solvers_from_published_results():
    payload = rank_classical_solvers()
    assert payload["n_runs"] > 0
    assert payload["solvers"]
    ids = [s["solver_id"] for s in payload["solvers"]]
    assert "c4_local_search" in ids
    assert "c3_greedy" in ids
    # ranks are 1..n unique
    ranks = [s["rank"] for s in payload["solvers"]]
    assert ranks == list(range(1, len(ranks) + 1))
    # near-best rates in [0, 1]
    for s in payload["solvers"]:
        assert 0.0 <= s["near_best_rate"] <= 1.0
        assert 0.0 <= s["usable_rate"] <= 1.0


def test_evaluation_maps_all_catalogue_ids():
    report = build_classical_quantum_evaluation()
    assert report["status"] == "ready"
    assert report["classical_ranking"]["top_solver"]
    assert report["classical_ranking"]["top_operational_solver"] != "c1_brute_force"
    assert report["headline"]["top_operational"] == report["classical_ranking"]["top_operational_solver"]
    opp_ids = {o["id"] for o in report["failure_to_quantum"]["opportunities"]}
    assert opp_ids == {c["id"] for c in QUANTUM_OPPORTUNITY_CATALOGUE}
    # classical_ok / staffing entries must stay honest
    by_id = {o["id"]: o for o in report["failure_to_quantum"]["opportunities"]}
    assert by_id["staffing_or_equity"]["advantage_type"] == "none_data_limit"
    assert "ensemble" in by_id["classical_ok"]["quantum_can_add"].lower() or "Additive" in by_id[
        "classical_ok"
    ]["quantum_can_add"]
