"""
Classical solver base interface.

Classical execution target: local CPU only.
Never submits jobs to IQM Emerald or any QPU.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from backend.optimization.objective import build_solution_result, empty_matrix
from backend.scenario.models import CHWDeploymentScenario, CHWSolutionResult


class ClassicalSolverBase(ABC):
    """Common contract for C1–C7 classical allocation solvers."""

    solver_id: str = "classical_base"
    execution_target: str = "local_cpu"

    @abstractmethod
    def _optimize(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float,
        seed: int,
    ):
        """Return (assignment_matrix, status, extra_metrics)."""

    def solve(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float = 60.0,
        seed: int = 42,
    ) -> CHWSolutionResult:
        t0 = time.perf_counter()
        try:
            x, status, extra = self._optimize(scenario, time_budget_sec, seed)
        except Exception as exc:  # noqa: BLE001 — surface as solver error status
            x = empty_matrix(scenario)
            status = "error"
            extra = {"error": str(exc)}
        elapsed = time.perf_counter() - t0
        extra = dict(extra or {})
        extra["execution_target"] = self.execution_target
        extra["time_budget_sec"] = time_budget_sec
        extra["seed"] = seed
        return build_solution_result(
            scenario,
            x,
            solver_type=self.solver_id,
            execution_time_sec=elapsed,
            status=status,
            extra_metrics=extra,
        )
