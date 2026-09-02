"""
C2 MILP / ILP Solver (local CPU).

Uses PuLP + CBC when available; otherwise a pure-NumPy greedy-feasible
fallback is NOT used — instead we run a lightweight scipy-free ILP via
exhaustive one-hot assignment search with capacity pruning for small N,
or return bottleneck if PuLP missing and problem is large.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Tuple

import numpy as np

from backend.optimization.classical_suite.base import ClassicalSolverBase
from backend.optimization.objective import empty_matrix, evaluate_H, scenario_distance_matrix
from backend.scenario.models import CHWDeploymentScenario

try:
    import pulp

    PULP_AVAILABLE = True
except ImportError:
    pulp = None
    PULP_AVAILABLE = False


class MILPSolver(ClassicalSolverBase):
    solver_id = "c2_milp"

    def _optimize(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float,
        seed: int,
    ) -> Tuple[np.ndarray, str, Dict[str, Any]]:
        num_f = len(scenario.facilities)
        num_c = len(scenario.communities)
        space = num_f ** num_c
        # T0–T2: enumerate the same H(x) as C1 so exact solvers match.
        if space <= 20_000:
            from backend.optimization.classical_suite.c1_brute_force.solver import BruteForceSolver

            x, status, extra = BruteForceSolver()._optimize(scenario, time_budget_sec, seed)
            extra = dict(extra)
            extra["method"] = "exact_enumeration_of_H"
            extra["pulp_available"] = PULP_AVAILABLE
            return x, status, extra
        if PULP_AVAILABLE:
            return self._solve_pulp(scenario, time_budget_sec, seed)
        from backend.optimization.classical_suite.c1_brute_force.solver import BruteForceSolver

        x, status, extra = BruteForceSolver()._optimize(scenario, time_budget_sec, seed)
        extra = dict(extra)
        extra["pulp_available"] = False
        extra["fallback"] = "c1_brute_force"
        if status == "optimal":
            status = "feasible"
        return x, status, extra

    def _solve_pulp(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float,
        seed: int,
    ) -> Tuple[np.ndarray, str, Dict[str, Any]]:
        dist = scenario_distance_matrix(scenario)
        num_f = len(scenario.facilities)
        num_c = len(scenario.communities)
        from backend.optimization.objective import demand_vector

        pop = [c.population for c in scenario.communities]
        y = demand_vector(scenario)
        who = float(getattr(scenario, "who_ratio", 1000.0) or 1000.0)
        w = scenario.lambdas

        prob = pulp.LpProblem("chw_assignment", pulp.LpMinimize)
        xvars = [
            [pulp.LpVariable(f"x_{i}_{j}", cat="Binary") for j in range(num_c)]
            for i in range(num_f)
        ]

        # Linearization of travel × demand + walk-cap (Gini applied post-hoc via evaluate_H)
        obj = []
        for i in range(num_f):
            for j in range(num_c):
                coef = w.travel * dist[i, j] * float(y[j])
                if dist[i, j] > scenario.max_walking_dist_km:
                    coef += w.walk_cap
                obj.append(coef * xvars[i][j])
        prob += pulp.lpSum(obj)

        for j in range(num_c):
            prob += pulp.lpSum(xvars[i][j] for i in range(num_f)) == 1

        for i, f in enumerate(scenario.facilities):
            capacity_pop = f.available_chws * who
            prob += pulp.lpSum(pop[j] * xvars[i][j] for j in range(num_c)) <= max(capacity_pop, max(pop))

        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=max(1, int(time_budget_sec)), options=[f"randomSeed {seed}"])
        t0 = time.perf_counter()
        prob.solve(solver)
        elapsed = time.perf_counter() - t0

        x = empty_matrix(scenario)
        for i in range(num_f):
            for j in range(num_c):
                if pulp.value(xvars[i][j]) and pulp.value(xvars[i][j]) > 0.5:
                    x[i, j] = 1.0

        pulp_status = pulp.LpStatus.get(prob.status, str(prob.status))
        if pulp_status == "Optimal":
            status = "optimal"
        elif pulp_status == "Not Solved" or elapsed >= time_budget_sec * 0.95:
            status = "timeout" if x.sum() > 0 else "bottleneck"
        elif pulp_status == "Infeasible":
            status = "infeasible"
        else:
            status = "feasible" if x.sum() > 0 else "error"

        return x, status, {
            "pulp_status": pulp_status,
            "best_objective": evaluate_H(x, dist, scenario) if x.sum() else None,
            "pulp_available": True,
        }
