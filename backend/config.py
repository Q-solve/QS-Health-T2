"""Constants and environment loading for AfyaDeploy."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Qubit budgets (QAOA comparator only)
# ---------------------------------------------------------------------------
MAX_QUBITS = int(os.getenv("MAX_QUBITS", "24"))
MAX_QUBITS_SIMULATOR = MAX_QUBITS
RECOMMENDED_QAOA_QUBITS = int(os.getenv("RECOMMENDED_QAOA_QUBITS", "16"))

QAOA_REPS = 1
QAOA_MAXITER = 40

# Default objective weights (shared H / QUBO)
WEIGHT_TRAVEL = 1.0
WEIGHT_UNMET = 5.0
WEIGHT_OVERALLOC = 3.0
PENALTY_ASSIGN = 50.0
PENALTY_CAPACITY = 50.0

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Optional Claude API — natural-language recommendations
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "1800"))

# qBraid — classical solvers never use QPU; quantum defaults to FREE simulator.
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
    QBRAID_DEFAULT_DEVICE = QBRAID_FREE_SIMULATOR

CLASSICAL_EXECUTION_TARGET = "local_cpu"
QAOA_SHOTS = int(os.getenv("QAOA_SHOTS", "1000"))

QBRAID_LAB_INSTANCE = os.getenv("QBRAID_LAB_INSTANCE", "vscode_8vCPU_25GB")
QBRAID_LAB_PROFILE_SLUG = os.getenv("QBRAID_LAB_PROFILE_SLUG", "vscode_8vCPU_25GB")
QBRAID_LAB_VCPUS = int(os.getenv("QBRAID_LAB_VCPUS", "8"))
QBRAID_LAB_RAM_GB = int(os.getenv("QBRAID_LAB_RAM_GB", "25"))
QBRAID_GPU_PROFILE_SLUG = os.getenv("QBRAID_GPU_PROFILE_SLUG", "gpu-l4")
QAOA_WAIT_TIMEOUT_SEC = float(os.getenv("QAOA_WAIT_TIMEOUT_SEC", "600"))
QAOA_USE_LOCAL_AER = os.getenv("QAOA_USE_LOCAL_AER", "1").strip().lower() in {"1", "true", "yes"}

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
CLASSICAL_FULL_SWEEP_BUDGET_SEC = float(
    os.getenv("CLASSICAL_FULL_SWEEP_BUDGET_SEC", "4.0" if _small else "10.0")
)
CLASSICAL_FULL_SWEEP_PARALLEL = False

# Optional Kenya Areas API (public demo key via env)
KENYA_AREAS_API_KEY = os.getenv("KENYA_AREAS_API_KEY", "")
