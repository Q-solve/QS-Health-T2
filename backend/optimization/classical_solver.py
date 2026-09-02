"""
Backward-compatible classical solver entrypoint.

New code should import from backend.optimization.classical_suite.
Classical solvers always run on local CPU (never Emerald / never QPU).
"""

from __future__ import annotations

from backend.optimization.classical_suite.c3_greedy.solver import GreedyNearestNeighborSolver
from backend.scenario.models import CHWDeploymentScenario, CHWSolutionResult

# Legacy alias used across API / tests
GreedyClassicalSolver = GreedyNearestNeighborSolver


def solve_greedy(scenario: CHWDeploymentScenario, time_budget_sec: float = 30.0) -> CHWSolutionResult:
    return GreedyClassicalSolver().solve(scenario, time_budget_sec=time_budget_sec)
