"""
qBraid Quantum Execution Wrapper.

Default target: FREE qBraid simulator (`qbraid:qbraid:sim:qir-sv`).
IQM Emerald QPU is optional and must be requested explicitly.
Classical solvers never call this module.
"""

from __future__ import annotations

import time
from typing import Any, Dict

import numpy as np

from backend import config
from backend.qbraid_client.manager import QBraidJobStatus, qbraid_manager


def run_qbraid_quantum_job(
    cost_hamiltonian: Any,
    ansatz_circuit: Any,
    parameters: np.ndarray,
    backend_name: str | None = None,
    shots: int = 1000,
) -> Dict[str, Any]:
    """
    Execute a quantum circuit on a free qBraid simulator by default.
    Pass QBRAID_QPU_DEVICE explicitly only when QPU credits are intentional.
    """
    del cost_hamiltonian, parameters  # reserved for future circuit binding
    start_time = time.time()
    backend_name = backend_name or config.QBRAID_FREE_SIMULATOR
    effective_shots = min(shots, 1000)

    job_status: QBraidJobStatus = qbraid_manager.submit_job(
        circuit_or_hamiltonian=ansatz_circuit,
        backend_name=backend_name,
        shots=effective_shots,
    )

    exec_time = time.time() - start_time
    is_free_sim = "sim" in backend_name.lower() or "simulator" in backend_name.lower()

    return {
        "job_id": job_status.job_id,
        "backend": backend_name,
        "device_name": (
            "qBraid Free Simulator"
            if is_free_sim
            else "IQM Emerald QPU (explicit opt-in)"
        ),
        "status": job_status.status,
        "shots": effective_shots,
        "execution_time_sec": round(exec_time, 4),
        "is_real_qpu_job": job_status.is_real_qpu_job,
        "is_free_simulator": is_free_sim,
        "qbraid_synced": True,
    }
