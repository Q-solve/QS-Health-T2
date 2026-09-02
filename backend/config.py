"""Constants and environment loading for the outbreak resource planner."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Qubit budgets
# ---------------------------------------------------------------------------
# Penalty QUBO uses 1 qubit per binary var:  (#resource units) × (#sites).
#
# Aer StatevectorSampler memory ~ O(2^n). 24 qubits ≈ 16M amplitudes — still
# workable on a laptop for shallow QAOA (reps=1). Above that prefer classical.
MAX_QUBITS = int(os.getenv("MAX_QUBITS", "24"))
MAX_QUBITS_SIMULATOR = MAX_QUBITS

# IBM Heron processors expose up to 156 qubits
# (https://quantum.cloud.ibm.com/docs/guides/processor-types). Practical QAOA
# depth/noise still favour smaller encodings; we allow up to this ceiling for
# hardware submission paths, but the UI should only select the resource types
# needed for a given run.
MAX_QUBITS_HARDWARE = int(os.getenv("MAX_QUBITS_HARDWARE", "156"))

# Soft guidance shown in the UI / meta endpoint (not a hard reject for classical).
RECOMMENDED_QAOA_QUBITS = int(os.getenv("RECOMMENDED_QAOA_QUBITS", "16"))

# QAOA defaults (tuned for <60s demo runs on toy / quantum-sized scenarios)
QAOA_REPS = 1
QAOA_MAXITER = 40

# Default objective weights (tunable via scenario / API later).
WEIGHT_TRAVEL = 1.0
WEIGHT_UNMET = 5.0
WEIGHT_OVERALLOC = 3.0

# Constraint penalty multipliers — must dominate any objective gain from violating.
PENALTY_ASSIGN = 50.0
PENALTY_CAPACITY = 50.0

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Optional IBM Quantum (FR9 stretch)
IBM_QUANTUM_TOKEN = os.getenv("IBM_QUANTUM_TOKEN", "")
IBM_QUANTUM_CHANNEL = os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum")

# Claude API — post-optimization natural-language recommendations (quantum + AI)
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "1800"))

# qBraid platform settings
# Classical solvers always run on local CPU (never on QPU).
# Quantum comparator defaults to the FREE qBraid simulator — not IQM Emerald.
# Set ALLOW_QPU_DEFAULT=1 only when you intentionally want Emerald as default.
QBRAID_API_KEY = os.getenv("QBRAID_API_KEY", "")
QBRAID_FREE_SIMULATOR = os.getenv("QBRAID_FREE_SIMULATOR", "qbraid:qbraid:sim:qir-sv")
QBRAID_QPU_DEVICE = os.getenv("QBRAID_QPU_DEVICE", "openquantum:iqm:qpu:emerald")
_raw_qbraid_default = os.getenv("QBRAID_DEFAULT_DEVICE", "").strip()
_allow_qpu_default = os.getenv("ALLOW_QPU_DEFAULT", "").strip().lower() in {"1", "true", "yes"}
if _allow_qpu_default and _raw_qbraid_default:
    QBRAID_DEFAULT_DEVICE = _raw_qbraid_default
elif _raw_qbraid_default and ("sim" in _raw_qbraid_default.lower() or "simulator" in _raw_qbraid_default.lower()):
    QBRAID_DEFAULT_DEVICE = _raw_qbraid_default
else:
    # Ignore legacy .env values that pointed at Emerald / other QPUs.
    QBRAID_DEFAULT_DEVICE = QBRAID_FREE_SIMULATOR
CLASSICAL_EXECUTION_TARGET = "local_cpu"  # never emerald / never qpu
QAOA_SHOTS = int(os.getenv("QAOA_SHOTS", "1000"))

# qBraid Lab / compute instance (CPU hours, not QPU)
# Free plan: 100 CPU-hours/month on subscription Small (2 vCPU / 4 GB).
# CLI slug from `qbraid compute up 2vCPU_4GB` (docs.qbraid.com/v2/cli).
# GPUs (gpu-l4, …) consume credits — never the default.
QBRAID_LAB_INSTANCE = os.getenv("QBRAID_LAB_INSTANCE", "vscode_8vCPU_25GB")
QBRAID_LAB_PROFILE_SLUG = os.getenv("QBRAID_LAB_PROFILE_SLUG", "vscode_8vCPU_25GB")
QBRAID_LAB_VCPUS = int(os.getenv("QBRAID_LAB_VCPUS", "8"))
QBRAID_LAB_RAM_GB = int(os.getenv("QBRAID_LAB_RAM_GB", "25"))
QBRAID_GPU_PROFILE_SLUG = os.getenv("QBRAID_GPU_PROFILE_SLUG", "gpu-l4")  # paid; opt-in only
QAOA_WAIT_TIMEOUT_SEC = float(os.getenv("QAOA_WAIT_TIMEOUT_SEC", "600"))
QAOA_USE_LOCAL_AER = os.getenv("QAOA_USE_LOCAL_AER", "1").strip().lower() in {"1", "true", "yes"}

# Classical suite time budgets (seconds) by tier label — tuned for Small (2 vCPU / 4GB)
_inst = QBRAID_LAB_INSTANCE.lower()
_small = _inst.startswith("small") or "2vcpu" in _inst or QBRAID_LAB_VCPUS <= 2
CLASSICAL_TIME_BUDGETS = {
    "T0": 5.0 if _small else 10.0,
    "T1": 8.0 if _small else 10.0,
    "T2": 30.0 if _small else 60.0,
    "T3": 60.0 if _small else 120.0,
    "T4": 90.0 if _small else 180.0,
    "T5": 120.0 if _small else 300.0,
    "T6": 180.0 if _small else 600.0,
}
# Default per-scenario budget when sweeping all counties on Small VS Code
CLASSICAL_FULL_SWEEP_BUDGET_SEC = float(os.getenv("CLASSICAL_FULL_SWEEP_BUDGET_SEC", "4.0" if _small else "10.0"))
CLASSICAL_FULL_SWEEP_PARALLEL = False  # keep sequential on 2 vCPU


