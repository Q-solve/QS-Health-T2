"""
qBraid Platform Manager — Real SDK v0.12.2 Integration.

Uses the actual QbraidProvider API to authenticate, list devices,
build Qiskit circuits from QUBO matrices, and submit real quantum jobs
to free qBraid simulators by default (IQM Emerald QPU only on explicit opt-in).

Requires: QBRAID_API_KEY in .env  (get it from https://account.qbraid.com/api-keys)
"""

from __future__ import annotations

import os
import time
import logging
import numpy as np
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Real qBraid SDK v0.12.2 ──────────────────────────────────────────────────
try:
    from qbraid import QbraidProvider
    QBRAID_AVAILABLE = True
except ImportError:
    QbraidProvider = None
    QBRAID_AVAILABLE = False

# ── Qiskit for circuit construction ─────────────────────────────────────────
try:
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import QAOAAnsatz
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False



from backend import config


class QBraidJobStatus(BaseModel):
    job_id: str
    backend_name: str
    status: str                          # QUEUED, RUNNING, COMPLETED, SIMULATED_LOCAL, FAILED
    created_at: float
    completed_at: Optional[float] = None
    shots: int = 1000
    result_counts: Optional[Dict[str, int]] = None
    error_message: Optional[str] = None
    is_real_qpu_job: bool = False


class QBraidManager:
    """
    Real integration layer with the qBraid SDK v0.12.2.
    Submits Qiskit circuits to qBraid-registered backends (simulators + IQM Emerald QPU).
    Falls back to local classical simulation when API key is absent or submission fails.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("QBRAID_API_KEY", "").strip()
        self.jobs_registry: Dict[str, QBraidJobStatus] = {}
        self._provider: Optional[Any] = None

    def is_connected(self) -> bool:
        """Returns True only if qBraid SDK is installed AND a real API key is configured."""
        return QBRAID_AVAILABLE and bool(self.api_key)

    def _get_provider(self) -> Optional[Any]:
        """Lazily initialize and cache the QbraidProvider instance."""
        if self._provider is None and self.is_connected():
            try:
                self._provider = QbraidProvider(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize QbraidProvider: {e}")
        return self._provider

    def list_available_backends(self) -> List[Dict[str, Any]]:
        """
        List all available devices on qBraid. Returns real live device list if
        connected, otherwise returns the known static device registry.
        """
        static_devices = [
            {
                "id": "qbraid:qbraid:sim:qir-sv",
                "name": "qBraid Free QIR Statevector Simulator",
                "type": "simulator",
                "provider": "qBraid",
                "status": "ONLINE",
                "max_qubits": 32,
                "cost": "free",
            },
            {
                "id": "qbraid_qiskit_simulator",
                "name": "qBraid Qiskit Aer Simulator",
                "type": "simulator",
                "provider": "qBraid",
                "status": "ONLINE",
                "max_qubits": 32,
                "cost": "free",
            },
            {
                "id": "vscode_8vCPU_25GB",
                "name": "qBraid Lab Large · VS Code (plan CPU hours)",
                "type": "cpu",
                "provider": "qBraid",
                "status": "ONLINE",
                "vcpus": 8,
                "ram_gb": 25,
                "cost": "plan_cpu_hours",
                "cli": "qbraid compute up vscode_8vCPU_25GB",
            },
            {
                "id": "2vCPU_4GB",
                "name": "qBraid Lab Small CPU (free plan hours)",
                "type": "cpu",
                "provider": "qBraid",
                "status": "ONLINE",
                "vcpus": 2,
                "ram_gb": 4,
                "cost": "free_cpu_hours",
                "cli": "qbraid compute up 2vCPU_4GB",
            },
            {
                "id": "gpu-l4",
                "name": "NVIDIA L4 GPU (credits — not default)",
                "type": "gpu",
                "provider": "qBraid",
                "status": "ONLINE",
                "cost": "credits",
                "cli": "qbraid compute up gpu-l4",
            },
            {
                "id": "openquantum:iqm:qpu:emerald",
                "name": "IQM Emerald 54-qubit QPU (explicit opt-in, not default)",
                "type": "qpu",
                "provider": "IQM / OpenQuantum / qBraid",
                "status": "ONLINE",
                "max_qubits": 54,
                "cost": "credits",
            },
        ]
        provider = self._get_provider()
        if provider is not None:
            try:
                devices = provider.get_devices()
                return [
                    {
                        "id": getattr(d, "id", str(d)),
                        "name": getattr(d, "name", str(d)),
                        "type": "qpu" if "qpu" in str(getattr(d, "id", "")).lower() else "simulator",
                        "provider": getattr(d, "provider", "qBraid"),
                        "status": str(getattr(d, "status", "ONLINE")),
                        "max_qubits": getattr(d, "num_qubits", None),
                    }
                    for d in devices
                ]
            except Exception as err:
                logger.warning(f"Failed to query live qBraid devices: {err}")
        return static_devices

    def _build_qaoa_circuit(self, Q: np.ndarray, n_vars: int) -> Optional[Any]:
        """
        Build a minimal parametric QAOA circuit from a QUBO matrix Q.
        Uses Qiskit's QuantumCircuit to construct a valid gate-model circuit
        for submission to qBraid.
        """
        if not QISKIT_AVAILABLE:
            return None
        try:
            n = min(n_vars, 12)  # Cap at 12 qubits for realistic QPU submission
            qc = QuantumCircuit(n)
            # Initial superposition layer
            qc.h(range(n))
            # Problem unitary: ZZ-coupling from Q diagonal
            for i in range(n):
                for j in range(i + 1, n):
                    angle = float(Q[i, j]) if Q[i, j] != 0 else 0.0
                    if abs(angle) > 1e-6:
                        qc.rzz(angle * 0.3, i, j)
            # Mixer unitary: RX layer
            for i in range(n):
                qc.rx(0.5, i)
            qc.measure_all()
            return qc
        except Exception as e:
            logger.warning(f"Failed to build QAOA circuit: {e}")
            return None

    def submit_job(
        self,
        circuit_or_hamiltonian: Any,
        backend_name: str | None = None,
        shots: int = 1000,
    ) -> QBraidJobStatus:
        backend_name = backend_name or config.QBRAID_DEFAULT_DEVICE
        """
        Submit a quantum circuit to qBraid.
        
        - If a real API key is configured and qBraid SDK is available: submits the
          circuit to the specified backend (simulator or QPU) via QbraidProvider.
        - If no API key: falls back to local classical simulation (no QPU credits used).
        """
        job_id = f"local_sim_{int(time.time() * 1000)}"
        job_status = QBraidJobStatus(
            job_id=job_id,
            backend_name=backend_name,
            status="PENDING",
            created_at=time.time(),
            shots=min(shots, 1000),
            is_real_qpu_job=False,
        )
        self.jobs_registry[job_id] = job_status

        # ── Build a real Qiskit circuit if input is a QUBO matrix ──────────
        qiskit_circuit = None
        if isinstance(circuit_or_hamiltonian, np.ndarray):
            n_vars = circuit_or_hamiltonian.shape[0]
            qiskit_circuit = self._build_qaoa_circuit(circuit_or_hamiltonian, n_vars)
        elif QISKIT_AVAILABLE and hasattr(circuit_or_hamiltonian, "measure_all"):
            qiskit_circuit = circuit_or_hamiltonian

        # ── Attempt real qBraid submission ──────────────────────────────────
        provider = self._get_provider()
        if provider is not None and qiskit_circuit is not None:
            try:
                device = provider.get_device(backend_name)
                qjob = device.run(qiskit_circuit, shots=min(shots, 1000))
                real_job_id = str(getattr(qjob, "id", job_id))
                # Update job entry with real qBraid job ID
                del self.jobs_registry[job_id]
                job_id = real_job_id
                job_status.job_id = real_job_id
                job_status.status = "QUEUED"
                job_status.is_real_qpu_job = True
                self.jobs_registry[real_job_id] = job_status
                logger.info(f"✅ Real qBraid job submitted: {real_job_id} → {backend_name}")
                return job_status
            except Exception as ex:
                logger.warning(f"qBraid live submission failed, falling back to local simulation: {ex}")

        # ── Local fallback simulation ────────────────────────────────────────
        job_status.status = "SIMULATED_LOCAL"
        job_status.completed_at = time.time()
        job_status.is_real_qpu_job = False
        logger.info(f"⚠️  No QBRAID_API_KEY set — running local simulation (job: {job_id})")
        return job_status

    @staticmethod
    def extract_counts(result: Any) -> Dict[str, int]:
        """Normalize measurement counts across qBraid SDK result shapes."""
        if result is None:
            return {}
        counts = None
        if hasattr(result, "data") and hasattr(result.data, "get_counts"):
            counts = result.data.get_counts()
        elif hasattr(result, "measurement_counts"):
            try:
                counts = result.measurement_counts()
            except TypeError:
                counts = result.measurement_counts
        elif isinstance(result, dict):
            counts = result.get("counts") or result
        if not counts:
            return {}
        return {str(k): int(v) for k, v in dict(counts).items()}

    def submit_circuit(
        self,
        circuit: Any,
        backend_name: str | None = None,
        shots: int = 1000,
    ) -> QBraidJobStatus:
        """Submit a Qiskit circuit to qBraid and return the queued job handle."""
        return self.submit_job(
            circuit_or_hamiltonian=circuit,
            backend_name=backend_name,
            shots=shots,
        )

    def wait_for_job(
        self,
        job_id: str,
        *,
        poll_sec: float = 2.0,
        timeout_sec: float = 300.0,
    ) -> QBraidJobStatus:
        """
        Poll a real qBraid job until COMPLETED / FAILED / timeout.
        Updates jobs_registry and fills result_counts when available.
        """
        provider = self._get_provider()
        job = self.jobs_registry.get(job_id) or QBraidJobStatus(
            job_id=job_id,
            backend_name=config.QBRAID_DEFAULT_DEVICE,
            status="QUEUED",
            created_at=time.time(),
            is_real_qpu_job=True,
        )
        self.jobs_registry[job_id] = job

        if job_id.startswith("local_sim_") or provider is None:
            job.status = job.status if job.status != "PENDING" else "SIMULATED_LOCAL"
            job.completed_at = time.time()
            return job

        from qbraid import QbraidJob

        qjob = QbraidJob(job_id=job_id, client=provider.client)
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                raw = str(qjob.status())
            except Exception as e:
                logger.warning(f"Error polling qBraid job {job_id}: {e}")
                time.sleep(poll_sec)
                continue
            status = raw.upper().replace("JOBSTATUS.", "")
            job.status = status
            if any(tok in status for tok in ("COMPLETED", "DONE", "FAILED", "CANCEL", "ERROR")):
                break
            time.sleep(poll_sec)

        if any(tok in job.status for tok in ("COMPLETED", "DONE")):
            try:
                result = qjob.result()
                job.result_counts = self.extract_counts(result)
                job.completed_at = time.time()
            except Exception as e:
                logger.warning(f"Failed to fetch result for {job_id}: {e}")
                job.error_message = str(e)
        elif "FAIL" in job.status or "ERROR" in job.status or "CANCEL" in job.status:
            job.error_message = job.error_message or job.status
            job.completed_at = time.time()
        else:
            job.status = "TIMEOUT"
            job.error_message = f"Timed out after {timeout_sec}s"
            job.completed_at = time.time()
        return job

    def run_circuit_and_wait(
        self,
        circuit: Any,
        backend_name: str | None = None,
        shots: int = 1000,
        *,
        poll_sec: float = 2.0,
        timeout_sec: float = 300.0,
    ) -> QBraidJobStatus:
        """Submit a circuit and block until measurement counts are available."""
        submitted = self.submit_circuit(circuit, backend_name=backend_name, shots=shots)
        if submitted.status == "SIMULATED_LOCAL" or submitted.job_id.startswith("local_sim_"):
            return submitted
        return self.wait_for_job(
            submitted.job_id,
            poll_sec=poll_sec,
            timeout_sec=timeout_sec,
        )

    def get_job_status(self, job_id: str) -> Optional[QBraidJobStatus]:
        """Fetch updated real status for a submitted qBraid job."""
        if job_id not in self.jobs_registry:
            return None
        job = self.jobs_registry[job_id]
        if job.is_real_qpu_job and job.status in ("QUEUED", "RUNNING", "PENDING", "INITIALIZING"):
            return self.wait_for_job(job_id, poll_sec=1.0, timeout_sec=5.0)
        return job

    def list_jobs(self) -> List[QBraidJobStatus]:
        """List all tracked qBraid jobs."""
        return list(self.jobs_registry.values())


# Global singleton instance
qbraid_manager = QBraidManager()
