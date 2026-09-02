"""
Shared QUBO builder — quadratic-representable part of H(x).

After a quantum (or classical QUBO) decode, `evaluate_H` is the reporting
metric so classical C1–C7 and QAOA are compared on the same energy.

QUBO terms (x binary, k = i*C + j):
  linear travel:      λ1 d_ij y_j
  walk-cap:           λ5 1[d_ij > cap]
  assignment:         λ2 (Σ_i x_ij − 1)^2
  capacity:           λ3 (Σ_j pop_j x_ij − K_i)^2     [two-sided; H uses overflow only]
Equity Gini is NOT quadratic; it is applied only in evaluate_H after decode.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from backend.optimization.objective import demand_vector, population_vector, scenario_distance_matrix
from backend.scenario.models import CHWDeploymentScenario


class CHWQUBOBuilder:
    def __init__(self, scenario: CHWDeploymentScenario):
        self.scenario = scenario
        self.facilities = scenario.facilities
        self.communities = scenario.communities
        self.num_f = len(self.facilities)
        self.num_c = len(self.communities)
        self.num_vars = self.num_f * self.num_c
        self.w = scenario.lambdas
        self.dist = scenario_distance_matrix(scenario)
        self.y = demand_vector(scenario)
        self.pop = population_vector(scenario)
        self.who = float(scenario.who_ratio)

    def var_index(self, f_idx: int, c_idx: int) -> int:
        return f_idx * self.num_c + c_idx

    def build_qubo_matrix(self) -> Tuple[np.ndarray, Dict[str, Any]]:
        N = self.num_vars
        Q = np.zeros((N, N), dtype=float)
        cap = self.scenario.max_walking_dist_km

        # 1. Travel × demand + walk-cap (linear / diagonal)
        for i, f in enumerate(self.facilities):
            for j, c in enumerate(self.communities):
                k = self.var_index(i, j)
                Q[k, k] += self.w.travel * self.dist[i, j] * self.y[j]
                if self.dist[i, j] > cap:
                    Q[k, k] += self.w.walk_cap

        # 2. Assignment uniqueness: (sum_i x_ij - 1)^2
        #    = sum_i x_ij + 2 sum_{i<i'} x_ij x_i'j - 2 sum_i x_ij + 1
        #    diagonal contrib: (1-2) λ2 = -λ2 ; off-diag: λ2
        for j in range(self.num_c):
            for i1 in range(self.num_f):
                k1 = self.var_index(i1, j)
                Q[k1, k1] += self.w.assign * (1.0 - 2.0)
                for i2 in range(i1 + 1, self.num_f):
                    k2 = self.var_index(i2, j)
                    Q[k1, k2] += self.w.assign
                    Q[k2, k1] += self.w.assign

        # 3. Capacity (load - K)^2 with load = sum_j pop_j x_ij
        for i, f in enumerate(self.facilities):
            k_cap = float(f.available_chws) * self.who
            for j1 in range(self.num_c):
                k1 = self.var_index(i, j1)
                p1 = self.pop[j1]
                Q[k1, k1] += self.w.capacity * (p1 ** 2 - 2.0 * k_cap * p1)
                for j2 in range(j1 + 1, self.num_c):
                    k2 = self.var_index(i, j2)
                    p2 = self.pop[j2]
                    Q[k1, k2] += self.w.capacity * p1 * p2
                    Q[k2, k1] += self.w.capacity * p1 * p2

        metadata = {
            "num_variables": N,
            "num_facilities": self.num_f,
            "num_communities": self.num_c,
            "who_ratio": self.who,
            "feature_stage": self.scenario.feature_stage,
            "constraint_setting": self.scenario.constraint_setting,
            "tier": self.scenario.tier,
            "objective": "shared_H_quadratic_part",
            "equity_in_qubo": False,
            "equity_in_evaluate_H": True,
        }
        return Q, metadata


def build_chw_qubo(scenario: CHWDeploymentScenario) -> Tuple[np.ndarray, Dict[str, Any]]:
    return CHWQUBOBuilder(scenario).build_qubo_matrix()
