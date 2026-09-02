#!/usr/bin/env python3
"""
Optional FR9 stretch: submit one small QAOA circuit to IBM Quantum hardware.

NEVER use this in a live demo — queues are unpredictable. Run once beforehand,
screenshot the job result, and show it on a slide.

Requires IBM_QUANTUM_TOKEN in .env (see .env.example).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402


def main() -> None:
    if not config.IBM_QUANTUM_TOKEN:
        print(
            "No IBM_QUANTUM_TOKEN in environment.\n"
            "Add it to .env (see .env.example), then re-run.\n"
            "Live demo path does NOT need this — use the Aer/Statevector simulator."
        )
        sys.exit(1)

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except ImportError:
        print("Install qiskit-ibm-runtime first: pip install qiskit-ibm-runtime")
        sys.exit(1)

    print("Saving IBM Quantum account…")
    QiskitRuntimeService.save_account(
        channel=config.IBM_QUANTUM_CHANNEL,
        token=config.IBM_QUANTUM_TOKEN,
        overwrite=True,
    )
    service = QiskitRuntimeService(channel=config.IBM_QUANTUM_CHANNEL)
    backends = list(service.backends(simulator=False, operational=True))
    if not backends:
        print("No operational hardware backends found.")
        sys.exit(1)

    # Pick least busy small backend if possible
    backend = sorted(backends, key=lambda b: b.status().pending_jobs)[0]
    print(f"Selected backend: {backend.name}")

    from qiskit.primitives import StatevectorSampler  # local fallback reference
    from backend.scenario import toy_3clinic_scenario
    from backend.optimization.qubo_builder import build_penalty_qubo

    # Build circuit size note for the slide — full hardware QAOA loop is long;
    # we print the qubit count and leave the team to submit via Runtime Sampler
    # once queued. For the stretch goal, screenshoting a completed job is enough.
    sc = toy_3clinic_scenario()
    build = build_penalty_qubo(sc)
    print(f"Toy penalty QUBO qubits: {build.num_vars}")
    print(
        "Next: use QiskitRuntimeService Sampler on this QUBO Ising operator "
        f"against backend '{backend.name}', then screenshot the job in IBM Quantum.\n"
        "Do not block the live demo on the queue."
    )
    _ = StatevectorSampler  # documents local parity path
    print("Account saved. Hardware submission left as a manual stretch step.")


if __name__ == "__main__":
    main()
