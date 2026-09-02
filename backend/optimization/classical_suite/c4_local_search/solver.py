"""
C4 Local Search (swap / relocate) — local CPU.
Starts from greedy, applies improving moves until local optimum or budget.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Tuple

import numpy as np

from backend.optimization.classical_suite.base import ClassicalSolverBase
from backend.optimization.classical_suite.c3_greedy.solver import GreedyNearestNeighborSolver
from backend.optimization.objective import evaluate_H, scenario_distance_matrix
from backend.scenario.models import CHWDeploymentScenario


class LocalSearchSolver(ClassicalSolverBase):
    solver_id = "c4_local_search"

    def _optimize(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float,
        seed: int,
    ) -> Tuple[np.ndarray, str, Dict[str, Any]]:
        dist = scenario_distance_matrix(scenario)
        x, _, _ = GreedyNearestNeighborSolver()._optimize(scenario, time_budget_sec, seed)
        best_h = evaluate_H(x, dist, scenario)
        num_f, num_c = x.shape
        moves = 0
        t0 = time.perf_counter()

        improved = True
        while improved and (time.perf_counter() - t0) < time_budget_sec:
            improved = False
            # Relocate: move CU j from current facility to another
            for j in range(num_c):
                cur = int(np.argmax(x[:, j]))
                for i in range(num_f):
                    if i == cur:
                        continue
                    trial = x.copy()
                    trial[:, j] = 0.0
                    trial[i, j] = 1.0
                    h = evaluate_H(trial, dist, scenario)
                    moves += 1
                    if h + 1e-9 < best_h:
                        x = trial
                        best_h = h
                        improved = True
                        break
                if improved:
                    break
            if improved:
                continue
            # Swap facilities of two communities
            for j1 in range(num_c):
                for j2 in range(j1 + 1, num_c):
                    i1 = int(np.argmax(x[:, j1]))
                    i2 = int(np.argmax(x[:, j2]))
                    if i1 == i2:
                        continue
                    trial = x.copy()
                    trial[:, j1] = 0.0
                    trial[:, j2] = 0.0
                    trial[i2, j1] = 1.0
                    trial[i1, j2] = 1.0
                    h = evaluate_H(trial, dist, scenario)
                    moves += 1
                    if h + 1e-9 < best_h:
                        x = trial
                        best_h = h
                        improved = True
                        break
                if improved:
                    break

        status = "feasible"
        if time.perf_counter() - t0 >= time_budget_sec:
            status = "timeout"
        return x, status, {"moves_evaluated": moves, "best_objective": best_h}
