"""
Classical allocation suite C1–C7.

All solvers run on local CPU. They do NOT use IQM Emerald or qBraid QPUs.
Quantum comparison (later phases) uses free qBraid simulator devices.
"""

from __future__ import annotations

from typing import Dict, List, Type

from backend.optimization.classical_suite.base import ClassicalSolverBase
from backend.optimization.classical_suite.c1_brute_force.solver import BruteForceSolver
from backend.optimization.classical_suite.c2_milp.solver import MILPSolver
from backend.optimization.classical_suite.c3_greedy.solver import GreedyNearestNeighborSolver
from backend.optimization.classical_suite.c4_local_search.solver import LocalSearchSolver
from backend.optimization.classical_suite.c5_simulated_annealing.solver import SimulatedAnnealingSolver
from backend.optimization.classical_suite.c6_genetic_algorithm.solver import GeneticAlgorithmSolver
from backend.optimization.classical_suite.c7_tabu_search.solver import TabuSearchSolver

CLASSICAL_SOLVER_CLASSES: Dict[str, Type[ClassicalSolverBase]] = {
    "c1_brute_force": BruteForceSolver,
    "c2_milp": MILPSolver,
    "c3_greedy": GreedyNearestNeighborSolver,
    "c4_local_search": LocalSearchSolver,
    "c5_simulated_annealing": SimulatedAnnealingSolver,
    "c6_genetic_algorithm": GeneticAlgorithmSolver,
    "c7_tabu_search": TabuSearchSolver,
}


def get_classical_solver(solver_id: str) -> ClassicalSolverBase:
    key = solver_id.lower().strip()
    if key not in CLASSICAL_SOLVER_CLASSES:
        raise KeyError(f"Unknown classical solver '{solver_id}'. Choose from: {list_classical_solver_ids()}")
    return CLASSICAL_SOLVER_CLASSES[key]()


def list_classical_solver_ids() -> List[str]:
    return list(CLASSICAL_SOLVER_CLASSES.keys())


def run_all_classical(
    scenario,
    time_budget_sec: float = 30.0,
    seed: int = 42,
    include: List[str] | None = None,
):
    ids = include or list_classical_solver_ids()
    results = {}
    for sid in ids:
        solver = get_classical_solver(sid)
        results[sid] = solver.solve(scenario, time_budget_sec=time_budget_sec, seed=seed)
    return results


__all__ = [
    "ClassicalSolverBase",
    "CLASSICAL_SOLVER_CLASSES",
    "get_classical_solver",
    "list_classical_solver_ids",
    "run_all_classical",
    "BruteForceSolver",
    "MILPSolver",
    "GreedyNearestNeighborSolver",
    "LocalSearchSolver",
    "SimulatedAnnealingSolver",
    "GeneticAlgorithmSolver",
    "TabuSearchSolver",
]
