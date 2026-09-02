"""
Build a fixed-angle QAOA circuit from a shared CHW QUBO matrix.

Uses the same Q as classical QUBO solvers. Angles can be warm-started from
a classical baseline; defaults are mild (p=1) for NISQ-scale submission.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

try:
    from qiskit import QuantumCircuit

    QISKIT_AVAILABLE = True
except ImportError:  # pragma: no cover
    QuantumCircuit = None  # type: ignore
    QISKIT_AVAILABLE = False


def build_qaoa_circuit(
    Q: np.ndarray,
    *,
    gamma: float = 0.4,
    beta: float = 0.3,
    reps: int = 1,
    max_qubits: Optional[int] = None,
) -> Tuple["QuantumCircuit", int]:
    """
    Construct a p-layer QAOA circuit for QUBO Q (minimize x^T Q x).

    Returns (circuit, n_qubits_used).
    """
    if not QISKIT_AVAILABLE:
        raise ImportError("qiskit is required to build QAOA circuits")

    n = int(Q.shape[0])
    if max_qubits is not None:
        n = min(n, int(max_qubits))
    if n < 1:
        raise ValueError("QUBO must have at least one variable")

    # Normalize magnitudes so RZZ/RZ angles stay numerically stable on hardware/sim.
    Qn = np.asarray(Q[:n, :n], dtype=float)
    scale = float(np.max(np.abs(Qn))) or 1.0
    Qn = Qn / scale

    qc = QuantumCircuit(n)
    qc.h(range(n))

    for _ in range(max(1, int(reps))):
        # Cost unitary U_C(gamma): diagonal RZ + off-diagonal RZZ from Q
        # Keep only stronger couplings so dense capacity QUBOs stay NISQ-runnable.
        off = []
        for i in range(n):
            for j in range(i + 1, n):
                w = float(Qn[i, j])
                if abs(w) > 1e-9:
                    off.append((abs(w), i, j, w))
        off.sort(reverse=True)
        max_couplers = min(len(off), max(n * 4, 48))
        for _, i, j, w in off[:max_couplers]:
            qc.rzz(2.0 * gamma * w, i, j)
        for i in range(n):
            w_ii = float(Qn[i, i])
            if abs(w_ii) > 1e-9:
                qc.rz(2.0 * gamma * w_ii, i)
        # Mixer U_B(beta)
        for i in range(n):
            qc.rx(2.0 * beta, i)

    qc.measure_all()
    return qc, n


def repair_one_hot_assignment(
    bitstring: str,
    num_f: int,
    num_c: int,
    dist: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Map a raw QAOA bitstring to a valid one-facility-per-CU assignment.

    Preference order per community j:
      1) unique facility with bit 1
      2) among facilities with bit 1, nearest by dist
      3) nearest facility overall (fallback)
    """
    expected = num_f * num_c
    bits = (bitstring.replace(" ", "") + "0" * expected)[:expected]
    # Caller may try both endiannesses; this function interprets bits left-to-right
    # as row-major F×C (facility-major).
    raw = np.array([1.0 if b == "1" else 0.0 for b in bits], dtype=float).reshape(num_f, num_c)
    x = np.zeros((num_f, num_c), dtype=float)

    for j in range(num_c):
        ones = np.where(raw[:, j] > 0.5)[0]
        if ones.size == 1:
            x[ones[0], j] = 1.0
        elif ones.size > 1:
            if dist is not None:
                best = int(ones[np.argmin(dist[ones, j])])
            else:
                best = int(ones[0])
            x[best, j] = 1.0
        else:
            if dist is not None:
                best = int(np.argmin(dist[:, j]))
            else:
                best = 0
            x[best, j] = 1.0
    return x


def pick_best_bitstring_from_counts(
    counts: dict,
    num_f: int,
    num_c: int,
    dist: np.ndarray,
    evaluate_h,
    scenario,
    *,
    top_k: int = 32,
) -> Tuple[str, np.ndarray, float]:
    """
    Among the most frequent measurement outcomes, repair to one-hot and
    pick the assignment with lowest shared H(x).
    """
    if not counts:
        x = repair_one_hot_assignment("0" * (num_f * num_c), num_f, num_c, dist)
        return "".join("1" if v > 0 else "0" for v in x.reshape(-1).astype(int)), x, float(evaluate_h(x, dist, scenario))

    ranked = sorted(counts.items(), key=lambda kv: -int(kv[1]))[: max(1, top_k)]
    best_h = float("inf")
    best_x = None
    best_bits = None
    for bits, _freq in ranked:
        # Try both endiannesses; keep the better H
        for candidate in (bits, bits[::-1]):
            x = repair_one_hot_assignment(candidate, num_f, num_c, dist)
            h = float(evaluate_h(x, dist, scenario))
            if h < best_h:
                best_h = h
                best_x = x
                best_bits = "".join("1" if v > 0 else "0" for v in x.reshape(-1).astype(int))
    assert best_x is not None and best_bits is not None
    return best_bits, best_x, best_h
