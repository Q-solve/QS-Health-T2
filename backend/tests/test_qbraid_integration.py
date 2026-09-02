"""Tests for qBraid platform manager and device list sync."""

from backend.qbraid_client.manager import qbraid_manager


def test_qbraid_backends_list():
    backends = qbraid_manager.list_available_backends()
    assert isinstance(backends, list)
    assert len(backends) > 0
    ids = [b["id"] for b in backends]
    assert len(ids) > 0


def test_qbraid_job_submission():
    status = qbraid_manager.submit_job(circuit_or_hamiltonian="dummy_circuit")
    assert status.job_id.startswith("local_sim_") or status.job_id.startswith("qbraid_") or len(status.job_id) > 0
    assert status.status in ["QUEUED", "COMPLETED", "RUNNING", "SIMULATED_LOCAL"]
    
    retrieved = qbraid_manager.get_job_status(status.job_id)
    assert retrieved is not None
    assert retrieved.job_id == status.job_id
