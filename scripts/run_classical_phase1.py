#!/usr/bin/env python3
"""
Phase 1 smoke runner: shared metrics + 7 classical solvers on local CPU.

Usage:
  PYTHONPATH=. python scripts/run_classical_phase1.py
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend.optimization.compare import compare_classical_suite
from backend.scenario.sample_scenarios import TURKANA_PASTORAL_SCENARIO
from backend import config


def main():
    print("Classical execution target:", config.CLASSICAL_EXECUTION_TARGET)
    print("Quantum default device (comparator only):", config.QBRAID_DEFAULT_DEVICE)
    print("Running classical suite on:", TURKANA_PASTORAL_SCENARIO.name)
    payload = compare_classical_suite(
        TURKANA_PASTORAL_SCENARIO,
        time_budget_sec=3.0,
        seed=42,
    )
    out = os.path.join(ROOT, "data", "classical_suite_phase1_smoke.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("Best classical:", payload["best_classical"])
    for row in payload["ranking_by_objective"]:
        print(
            f"  {row['solver_id']:28s}  H={row['objective_value']}  "
            f"G={row['gini_equity_index']}  t={row['execution_time_sec']}s  status={row['status']}"
        )
    print("Wrote", out)


if __name__ == "__main__":
    main()
