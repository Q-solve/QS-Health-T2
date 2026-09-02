"""
Qiskit QAOA Quantum Solver with qBraid integration.

Builds the shared CHW QUBO, submits a p=1 QAOA circuit to the free qBraid
simulator (or an explicit QPU), waits for measurement counts, repairs the
best samples to valid one-hot assignments, and scores them with evaluate_H
so classical C1–C7 and QAOA are compared on the same energy.

On Large Lab (8 vCPU / 25 GB), also runs Qiskit Aer locally so mid-size
instances (T2) do not stall when the shared free cloud sim times out.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend import config
from backend.optimization.objective import (
    bitstring_to_matrix,
    build_solution_result,
    evaluate_H,
    matrix_to_bitstring,
    scenario_distance_matrix,
)
from backend.optimization.qaoa_circuit import (
    build_qaoa_circuit,
    pick_best_bitstring_from_counts,
    repair_one_hot_assignment,
)
from backend.optimization.qubo_builder import build_chw_qubo
from backend.qbraid_client.manager import qbraid_manager
from backend.scenario.models import CHWDeploymentScenario, CHWSolutionAssignment, CHWSolutionResult


def _run_aer_counts(circuit: Any, shots: int) -> Dict[str, int]:
    """Execute circuit on local Aer using Lab CPU cores."""
    try:
        from qiskit_aer import AerSimulator
    except ImportError:
        try:
            from qiskit.providers.aer import AerSimulator  # type: ignore
        except ImportError:
            return {}

    threads = max(1, int(getattr(config, "QBRAID_LAB_VCPUS", 8) or 8))
    os.environ.setdefault("OMP_NUM_THREADS", str(threads))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(threads))
    sim = AerSimulator(method="automatic")
    # Prefer max_parallel_threads when supported
    try:
        sim.set_options(max_parallel_threads=threads)
    except Exception:
        pass
    result = sim.run(circuit, shots=shots).result()
    raw = result.get_counts()
    return {str(k): int(v) for k, v in dict(raw).items()}


class QAOAQuantumSolver:
    """QAOA solver dispatched to the free qBraid simulator by default."""

    def __init__(
        self,
        backend_name: str | None = None,
        *,
        shots: int | None = None,
        gamma: float = 0.4,
        beta: float = 0.3,
        reps: int = 1,
        wait_timeout_sec: float | None = None,
        top_k: int = 32,
        use_local_aer: bool | None = None,
    ):
        self.backend_name = backend_name or config.QBRAID_DEFAULT_DEVICE
        self.shots = int(shots or config.QAOA_SHOTS)
        self.gamma = gamma
        self.beta = beta
        self.reps = reps
        self.wait_timeout_sec = float(
            wait_timeout_sec if wait_timeout_sec is not None else getattr(config, "QAOA_WAIT_TIMEOUT_SEC", 600.0)
        )
        self.top_k = top_k
        self.use_local_aer = (
            config.QAOA_USE_LOCAL_AER if use_local_aer is None else bool(use_local_aer)
        )
        self.last_job: Optional[Dict[str, Any]] = None

    def solve(self, scenario: CHWDeploymentScenario) -> CHWSolutionResult:
        start_time = time.time()
        Q, meta = build_chw_qubo(scenario)
        N = int(meta["num_variables"])
        num_f = len(scenario.facilities)
        num_c = len(scenario.communities)
        dist = scenario_distance_matrix(scenario)

        # Free qBraid QIR SV simulator caps at 30 qubits; Aer on Large can go higher
        # but memory grows as 2^N — keep a soft ceiling.
        platform_max_q = 30 if "sim" in self.backend_name.lower() else None
        aer_max_q = int(getattr(config, "MAX_QUBITS", 24) or 24)
        if platform_max_q is not None and N > platform_max_q and not (self.use_local_aer and N <= aer_max_q):
            exec_time = time.time() - start_time
            x = repair_one_hot_assignment("0" * N, num_f, num_c, dist)
            result = build_solution_result(
                scenario,
                x,
                solver_type="qaoa_qbraid",
                execution_time_sec=exec_time,
                status="bottleneck",
                extra_metrics={
                    "backend_name": self.backend_name,
                    "qubo_variables": N,
                    "shots": self.shots,
                    "skip_reason": (
                        f"N={N} exceeds simulator qubit cap {platform_max_q}; "
                        "needs QPU or decomposition"
                    ),
                    "qbraid_submission": "skipped",
                    "qbraid_lab_profile": config.QBRAID_LAB_PROFILE_SLUG,
                },
            )
            result.failure_label = "F-SCALE"
            self.last_job = {"status": "SKIPPED", "reason": result.extra_metrics["skip_reason"]}
            return result

        circuit_cap = platform_max_q
        if self.use_local_aer and (platform_max_q is None or N > platform_max_q):
            circuit_cap = min(N, aer_max_q)
        circuit, n_used = build_qaoa_circuit(
            Q,
            gamma=self.gamma,
            beta=self.beta,
            reps=self.reps,
            max_qubits=circuit_cap,
        )

        counts: Dict[str, int] = {}
        used_platform = False
        used_aer = False
        job_id = None
        job_status = "PENDING"
        job_error = None
        queue_wall = 0.0

        # Prefer platform for N within free-sim limits; use longer wait on Large.
        can_submit_platform = platform_max_q is None or N <= platform_max_q
        if can_submit_platform:
            # On Large, don't block forever on mid-size cloud jobs — race Aer.
            platform_timeout = self.wait_timeout_sec
            if N >= 20 and self.use_local_aer:
                platform_timeout = min(platform_timeout, 180.0)
            queue_t0 = time.time()
            job = qbraid_manager.run_circuit_and_wait(
                circuit,
                backend_name=self.backend_name,
                shots=self.shots,
                timeout_sec=platform_timeout,
            )
            queue_wall = time.time() - queue_t0
            job_id = job.job_id
            job_status = job.status
            job_error = job.error_message
            counts = dict(job.result_counts or {})
            used_platform = bool(counts) and not str(job.job_id).startswith("local_sim_")

        if (not counts) and self.use_local_aer and n_used <= aer_max_q:
            aer_t0 = time.time()
            counts = _run_aer_counts(circuit, self.shots)
            used_aer = bool(counts)
            queue_wall = queue_wall + (time.time() - aer_t0)
            if used_aer and not used_platform:
                job_status = "AER_LOCAL_ON_LAB"
                job_id = job_id or f"aer_lab_{int(time.time())}"

        if counts:
            bits, x, _h = pick_best_bitstring_from_counts(
                counts,
                num_f,
                num_c,
                dist,
                evaluate_H,
                scenario,
                top_k=self.top_k,
            )
            solve_status = "feasible"
        else:
            bits = self._classical_fallback(Q, N, scenario, dist)
            x = bitstring_to_matrix(bits, num_f, num_c)
            solve_status = "feasible" if "FAIL" not in (job_status or "").upper() else "error"

        exec_time = time.time() - start_time
        top5 = sorted(counts.items(), key=lambda kv: -int(kv[1]))[:5] if counts else []
        self.last_job = {
            "job_id": job_id,
            "backend": self.backend_name,
            "status": job_status,
            "shots": self.shots,
            "used_platform_counts": used_platform,
            "used_aer_counts": used_aer,
            "n_unique_bitstrings": len(counts),
            "top5_counts": top5,
            "queue_plus_exec_sec": round(queue_wall, 4),
            "error_message": job_error,
            "circuit_depth": getattr(circuit, "depth", lambda: None)(),
            "n_qubits": n_used,
            "qbraid_lab_profile": config.QBRAID_LAB_PROFILE_SLUG,
            "lab_vcpus": config.QBRAID_LAB_VCPUS,
            "lab_ram_gb": config.QBRAID_LAB_RAM_GB,
        }

        result = build_solution_result(
            scenario,
            x,
            solver_type="qaoa_qbraid",
            execution_time_sec=exec_time,
            status=solve_status,
            extra_metrics={
                "backend_name": self.backend_name,
                "qubo_variables": N,
                "shots": self.shots,
                "qaoa_gamma": self.gamma,
                "qaoa_beta": self.beta,
                "qaoa_reps": self.reps,
                "used_platform_counts": used_platform,
                "used_aer_counts": used_aer,
                "n_unique_bitstrings": len(counts),
                "top5_counts": top5,
                "queue_plus_exec_sec": round(queue_wall, 4),
                "bitstring_repaired": bits,
                "qbraid_lab_profile": config.QBRAID_LAB_PROFILE_SLUG,
            },
        )
        result.qbraid_job_id = job_id
        result.qbraid_synced = used_platform or used_aer
        result.bitstring = matrix_to_bitstring(x)
        return result

    def _classical_fallback(
        self,
        Q: np.ndarray,
        N: int,
        scenario: CHWDeploymentScenario,
        dist: np.ndarray,
    ) -> str:
        """Same-H one-hot search used only when platform counts are unavailable."""
        num_f = len(scenario.facilities)
        num_c = len(scenario.communities)
        space = num_f ** num_c
        best_bits = "0" * N
        best_h = float("inf")

        def one_hot_bits(choices) -> str:
            x = np.zeros((num_f, num_c), dtype=float)
            for j, i in enumerate(choices):
                x[i, j] = 1.0
            return matrix_to_bitstring(x)

        if space <= 4096:
            import itertools

            for choices in itertools.product(range(num_f), repeat=num_c):
                bits = one_hot_bits(choices)
                x = bitstring_to_matrix(bits, num_f, num_c)
                h = evaluate_H(x, dist, scenario)
                if h < best_h:
                    best_h, best_bits = h, bits
            return best_bits

        rng = np.random.default_rng(int(getattr(scenario, "seed", 42) or 42))
        for _ in range(min(max(256, N * 32), 2048)):
            choices = rng.integers(0, num_f, size=num_c)
            bits = one_hot_bits(choices)
            x = bitstring_to_matrix(bits, num_f, num_c)
            h = evaluate_H(x, dist, scenario)
            if h < best_h:
                best_h, best_bits = h, bits
        return best_bits

    def _decode_assignments(
        self, scenario: CHWDeploymentScenario, bitstring: str
    ) -> Tuple[List[CHWSolutionAssignment], float, float]:
        from backend.geo.chw_facilities import calculate_walking_distance_matrix

        assignments = []
        total_travel = 0.0
        covered_pop = 0.0
        num_c = len(scenario.communities)
        dist_matrix = calculate_walking_distance_matrix(
            [f.model_dump() for f in scenario.facilities],
            [c.model_dump() for c in scenario.communities],
        )
        for i, f in enumerate(scenario.facilities):
            for j, c in enumerate(scenario.communities):
                idx = i * num_c + j
                if idx < len(bitstring) and bitstring[idx] == "1":
                    dist = round(dist_matrix.get((f.id, c.id), 5.0), 2)
                    assignments.append(
                        CHWSolutionAssignment(
                            facility_id=f.id,
                            facility_name=f.name,
                            community_id=c.id,
                            community_name=c.name,
                            assigned_chws=1,
                            walking_distance_km=dist,
                            demand_covered=c.population,
                        )
                    )
                    total_travel += dist
                    covered_pop += c.population
        return assignments, total_travel, covered_pop

    def _calculate_gini(self, assignments, scenario) -> float:
        from backend.optimization.metrics import gini_coefficient

        dists = [a.walking_distance_km for a in assignments]
        return gini_coefficient(dists) if dists else 0.0
