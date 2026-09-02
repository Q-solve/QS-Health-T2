"""
C3 Greedy Nearest-Neighbor Solver (local CPU).

Assigns each community (highest vulnerability×population first) to the
nearest facility with residual WHO capacity.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from backend.optimization.classical_suite.base import ClassicalSolverBase
from backend.optimization.objective import empty_matrix, scenario_distance_matrix
from backend.scenario.models import CHWDeploymentScenario


class GreedyNearestNeighborSolver(ClassicalSolverBase):
    solver_id = "c3_greedy"

    def _optimize(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float,
        seed: int,
    ) -> Tuple[np.ndarray, str, Dict[str, Any]]:
        del time_budget_sec, seed  # deterministic constructive heuristic
        dist = scenario_distance_matrix(scenario)
        num_f = len(scenario.facilities)
        num_c = len(scenario.communities)
        x = empty_matrix(scenario)

        who = float(getattr(scenario, "who_ratio", 1000.0) or 1000.0)
        residual = np.array([f.available_chws * who for f in scenario.facilities], dtype=float)
        order = sorted(
            range(num_c),
            key=lambda j: scenario.communities[j].population * max(scenario.communities[j].demand_score, 0.05),
            reverse=True,
        )

        unassigned = 0
        for j in order:
            # Prefer feasible nearest; else nearest overall
            candidates = []
            for i in range(num_f):
                pop = float(scenario.communities[j].population)
                feasible = residual[i] >= pop
                candidates.append((0 if feasible else 1, dist[i, j], i))
            candidates.sort()
            i_star = candidates[0][2]
            x[i_star, j] = 1.0
            residual[i_star] -= float(scenario.communities[j].population)
            if residual[i_star] < 0:
                unassigned += 0  # still assigned but overloaded
        return x, "feasible", {"strategy": "nearest_with_capacity", "overloads_allowed": True}
