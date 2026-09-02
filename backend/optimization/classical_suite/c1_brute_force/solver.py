"""
C1 Brute-Force Exact Solver (local CPU).

Enumerates assignments where each community gets exactly one facility.
Only practical for tiny N (recommend num_communities <= 10 and num_facilities <= 4).
"""

from __future__ import annotations

import itertools
import time
from typing import Any, Dict, Tuple

import numpy as np

from backend.optimization.classical_suite.base import ClassicalSolverBase
from backend.optimization.objective import empty_matrix, evaluate_H, scenario_distance_matrix
from backend.scenario.models import CHWDeploymentScenario


class BruteForceSolver(ClassicalSolverBase):
    solver_id = "c1_brute_force"

    def _optimize(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float,
        seed: int,
    ) -> Tuple[np.ndarray, str, Dict[str, Any]]:
        num_f = len(scenario.facilities)
        num_c = len(scenario.communities)
        # Search space: F^C (each CU picks one facility)
        space = num_f ** num_c
        if space > 5_000_000:
            return empty_matrix(scenario), "bottleneck", {
                "reason": "B-SCALE",
                "search_space": space,
                "message": "Brute force search space too large",
            }

        dist = scenario_distance_matrix(scenario)
        best_x = empty_matrix(scenario)
        best_h = float("inf")
        evaluated = 0
        t0 = time.perf_counter()

        for choices in itertools.product(range(num_f), repeat=num_c):
            if time.perf_counter() - t0 > time_budget_sec:
                status = "timeout" if best_h < float("inf") else "bottleneck"
                return best_x, status, {
                    "reason": "B-TIMEOUT",
                    "evaluated": evaluated,
                    "search_space": space,
                    "best_objective": best_h if best_h < float("inf") else None,
                }
            x = np.zeros((num_f, num_c), dtype=float)
            for j, i in enumerate(choices):
                x[i, j] = 1.0
            h = evaluate_H(x, dist, scenario)
            evaluated += 1
            if h < best_h:
                best_h = h
                best_x = x

        return best_x, "optimal", {
            "evaluated": evaluated,
            "search_space": space,
            "best_objective": best_h,
            "seed": seed,
        }
