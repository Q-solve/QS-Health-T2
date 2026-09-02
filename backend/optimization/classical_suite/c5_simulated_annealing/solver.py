"""
C5 Simulated Annealing — local CPU.

Uses `simanneal` when installed; otherwise a lightweight custom SA loop.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, Tuple

import numpy as np

from backend.optimization.classical_suite.base import ClassicalSolverBase
from backend.optimization.classical_suite.c3_greedy.solver import GreedyNearestNeighborSolver
from backend.optimization.objective import evaluate_H, scenario_distance_matrix
from backend.scenario.models import CHWDeploymentScenario

try:
    import simanneal

    SIMANNEAL_AVAILABLE = True
except ImportError:
    simanneal = None
    SIMANNEAL_AVAILABLE = False


class SimulatedAnnealingSolver(ClassicalSolverBase):
    solver_id = "c5_simulated_annealing"

    def _optimize(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float,
        seed: int,
    ) -> Tuple[np.ndarray, str, Dict[str, Any]]:
        rng = random.Random(seed)
        dist = scenario_distance_matrix(scenario)
        x, _, _ = GreedyNearestNeighborSolver()._optimize(scenario, time_budget_sec, seed)
        num_f, num_c = x.shape

        def neighbor(state: np.ndarray) -> np.ndarray:
            trial = state.copy()
            j = rng.randrange(num_c)
            i_new = rng.randrange(num_f)
            trial[:, j] = 0.0
            trial[i_new, j] = 1.0
            return trial

        if SIMANNEAL_AVAILABLE:

            class _CHWAnnealer(simanneal.Annealer):
                def move(self):
                    self.state = neighbor(self.state)

                def energy(self):
                    return evaluate_H(self.state, dist, scenario)

            ann = _CHWAnnealer(x)
            # Map time budget to steps heuristically
            steps = max(100, int(time_budget_sec * 200))
            ann.steps = steps
            ann.Tmax = 100.0
            ann.Tmin = 0.05
            ann.updates = 0
            best_state, best_e = ann.anneal()
            return np.asarray(best_state, dtype=float), "feasible", {
                "backend": "simanneal",
                "steps": steps,
                "best_objective": float(best_e),
            }

        # Custom SA fallback
        current = x.copy()
        current_h = evaluate_H(current, dist, scenario)
        best = current.copy()
        best_h = current_h
        t0 = time.perf_counter()
        T = 50.0
        steps = 0
        while time.perf_counter() - t0 < time_budget_sec:
            trial = neighbor(current)
            h = evaluate_H(trial, dist, scenario)
            delta = h - current_h
            if delta < 0 or rng.random() < math.exp(-delta / max(T, 1e-9)):
                current, current_h = trial, h
                if h < best_h:
                    best, best_h = trial.copy(), h
            T *= 0.995
            steps += 1
        return best, "feasible", {"backend": "custom_sa", "steps": steps, "best_objective": best_h}
