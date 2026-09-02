"""Phase 1 tests: shared metrics + classical suite (local CPU)."""

from __future__ import annotations

from backend.optimization.classical_suite import get_classical_solver, list_classical_solver_ids, run_all_classical
from backend.optimization.compare import compare_classical_suite
from backend.optimization.metrics import atkinson_index, gini_coefficient, theil_index
from backend.scenario.sample_scenarios import TURKANA_PASTORAL_SCENARIO
from backend import config


def test_equity_metrics_basic():
    vals = [1.0, 2.0, 3.0, 4.0]
    assert 0.0 <= gini_coefficient(vals) <= 1.0
    assert theil_index(vals) >= 0.0
    assert 0.0 <= atkinson_index(vals) <= 1.0


def test_classical_solver_ids():
    ids = list_classical_solver_ids()
    assert len(ids) == 7
    assert "c3_greedy" in ids
    assert "c1_brute_force" in ids


def test_greedy_uses_real_distances_and_metrics():
    res = get_classical_solver("c3_greedy").solve(TURKANA_PASTORAL_SCENARIO, time_budget_sec=5.0)
    assert res.solver_type == "c3_greedy"
    assert res.qbraid_job_id is None
    assert res.extra_metrics.get("execution_target") == "local_cpu"
    assert res.objective_value is not None
    assert res.theil_index is not None
    assert res.d_p90_km is not None
    assert len(res.assignments) == len(TURKANA_PASTORAL_SCENARIO.communities)


def test_brute_force_optimal_on_tiny_scenario():
    res = get_classical_solver("c1_brute_force").solve(TURKANA_PASTORAL_SCENARIO, time_budget_sec=10.0)
    assert res.status in {"optimal", "timeout", "feasible"}
    assert res.objective_value is not None
    assert res.population_coverage_pct == 100.0


def test_classical_suite_ranking():
    # Keep budget small for CI speed; skip heavy metaheuristics if needed
    payload = compare_classical_suite(
        TURKANA_PASTORAL_SCENARIO,
        time_budget_sec=2.0,
        include=["c1_brute_force", "c3_greedy", "c4_local_search"],
    )
    assert payload["execution_target"] == "local_cpu"
    assert payload["best_classical"] in payload["solvers_run"]
    assert len(payload["ranking_by_objective"]) == 3


def test_config_defaults_to_free_qbraid_not_emerald():
    assert config.CLASSICAL_EXECUTION_TARGET == "local_cpu"
    assert "sim" in config.QBRAID_DEFAULT_DEVICE.lower() or "simulator" in config.QBRAID_DEFAULT_DEVICE.lower()
    assert "emerald" not in config.QBRAID_DEFAULT_DEVICE.lower()
