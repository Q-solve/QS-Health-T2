"""Optimization package for CHW deployment in rural Kenya."""

from backend.optimization.qubo_builder import build_chw_qubo
from backend.optimization.quantum_solver import QAOAQuantumSolver
from backend.optimization.classical_solver import GreedyClassicalSolver
from backend.optimization.compare import compare_chw_solvers
from backend.optimization.classical_suite import (
    get_classical_solver,
    list_classical_solver_ids,
    run_all_classical,
)

__all__ = [
    "build_chw_qubo",
    "QAOAQuantumSolver",
    "GreedyClassicalSolver",
    "compare_chw_solvers",
    "get_classical_solver",
    "list_classical_solver_ids",
    "run_all_classical",
]
