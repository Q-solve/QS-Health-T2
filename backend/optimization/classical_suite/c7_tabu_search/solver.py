"""
C7 Tabu Search — local CPU.

Neighborhood: relocate CU to another facility. Tabu list stores (community, facility).
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Dict, Tuple

import numpy as np

from backend.optimization.classical_suite.base import ClassicalSolverBase
from backend.optimization.classical_suite.c3_greedy.solver import GreedyNearestNeighborSolver
from backend.optimization.objective import evaluate_H, scenario_distance_matrix
from backend.scenario.models import CHWDeploymentScenario


class TabuSearchSolver(ClassicalSolverBase):
    solver_id = "c7_tabu_search"

    def _optimize(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float,
        seed: int,
    ) -> Tuple[np.ndarray, str, Dict[str, Any]]:
        del seed
        dist = scenario_distance_matrix(scenario)
        x, _, _ = GreedyNearestNeighborSolver()._optimize(scenario, time_budget_sec, 0)
        best = x.copy()
        best_h = evaluate_H(best, dist, scenario)
        current = x.copy()
        current_h = best_h
        num_f, num_c = x.shape
        tenure = max(5, num_c)
        tabu: deque = deque(maxlen=tenure * 2)
        iterations = 0
        t0 = time.perf_counter()

        while time.perf_counter() - t0 < time_budget_sec:
            iterations += 1
            best_move = None
            best_move_h = float("inf")
            best_move_key = None
            for j in range(num_c):
                cur_i = int(np.argmax(current[:, j]))
                for i in range(num_f):
                    if i == cur_i:
                        continue
                    key = (j, i)
                    trial = current.copy()
                    trial[:, j] = 0.0
                    trial[i, j] = 1.0
                    h = evaluate_H(trial, dist, scenario)
                    is_tabu = key in tabu
                    # Aspiration: allow tabu if improves global best
                    if is_tabu and h >= best_h:
                        continue
                    if h < best_move_h:
                        best_move_h = h
                        best_move = trial
                        best_move_key = key
            if best_move is None:
                break
            current = best_move
            current_h = best_move_h
            tabu.append(best_move_key)
            if current_h + 1e-9 < best_h:
                best = current.copy()
                best_h = current_h

        # Greedy start is always a feasible incumbent; hitting the clock is not F-TIMEOUT.
        hit_budget = time.perf_counter() - t0 >= time_budget_sec
        return best, "feasible", {
            "iterations": iterations,
            "tabu_tenure": tenure,
            "best_objective": best_h,
            "hit_time_budget": hit_budget,
        }
