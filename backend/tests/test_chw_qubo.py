"""Tests for CHW Deployment QUBO matrix construction and solvers."""

from backend.scenario.sample_scenarios import TURKANA_PASTORAL_SCENARIO
from backend.optimization.qubo_builder import build_chw_qubo
from backend.optimization.quantum_solver import QAOAQuantumSolver
from backend.optimization.compare import compare_chw_solvers


def test_qubo_builder():
    Q, meta = build_chw_qubo(TURKANA_PASTORAL_SCENARIO)
    assert Q.ndim == 2
    assert Q.shape[0] == Q.shape[1] == meta["num_variables"]
    assert meta["num_variables"] == len(TURKANA_PASTORAL_SCENARIO.facilities) * len(TURKANA_PASTORAL_SCENARIO.communities)


def test_qaoa_solver_execution():
    solver = QAOAQuantumSolver()
    result = solver.solve(TURKANA_PASTORAL_SCENARIO)
    assert result.solver_type == "qaoa_qbraid"
    assert result.qbraid_job_id is not None
    assert result.population_coverage_pct >= 0.0


def test_solver_comparison():
    res = compare_chw_solvers(TURKANA_PASTORAL_SCENARIO)
    assert "metrics_comparison" in res
    assert "travel_saved_km" in res["metrics_comparison"]
