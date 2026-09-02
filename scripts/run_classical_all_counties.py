#!/usr/bin/env python3
"""
Full classical sweep across ALL Kenya scenarios (14 counties).

Designed for qBraid Lab **Small · VS Code** (2 vCPU / 4 GB):
  - sequential execution
  - modest per-scenario time budget
  - local CPU only (no Emerald QPU)

Attaches Q-SOLVE Kenya 2026 judging context (JC1–JC7) to the report.

Usage:
  PYTHONPATH=. python scripts/run_classical_all_counties.py
  PYTHONPATH=. python scripts/run_classical_all_counties.py --budget 3 --methods c3_greedy,c4_local_search,c1_brute_force
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend import config
from backend.optimization.compare import compare_classical_suite_all_scenarios
from backend.optimization.classical_suite import list_classical_solver_ids


def main():
    parser = argparse.ArgumentParser(description="Run classical suite on all counties")
    parser.add_argument(
        "--budget",
        type=float,
        default=config.CLASSICAL_FULL_SWEEP_BUDGET_SEC,
        help="Per-scenario time budget seconds (Small VS Code default ~4s)",
    )
    parser.add_argument(
        "--methods",
        type=str,
        default="",
        help="Comma-separated solver ids (default: all C1–C7)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=os.path.join(ROOT, "data", "classical_suite_all_counties.json"),
    )
    args = parser.parse_args()
    include = [m.strip() for m in args.methods.split(",") if m.strip()] or None

    print("=" * 72)
    print("AfyaDeploy — Full classical sweep (all counties)")
    print("qBraid Lab instance:", config.QBRAID_LAB_INSTANCE, f"({config.QBRAID_LAB_VCPUS} vCPU / {config.QBRAID_LAB_RAM_GB} GB)")
    print("Classical target:", config.CLASSICAL_EXECUTION_TARGET)
    print("Quantum default (comparator only):", config.QBRAID_DEFAULT_DEVICE)
    print("Methods:", include or list_classical_solver_ids())
    print("Budget/scenario:", args.budget, "sec")
    print("=" * 72)

    t0 = time.perf_counter()
    payload = compare_classical_suite_all_scenarios(
        time_budget_sec=args.budget,
        seed=42,
        include=include,
    )
    elapsed = time.perf_counter() - t0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"\nCounties covered ({payload['county_count']}):", ", ".join(payload["counties_covered"]))
    print("Wins by solver:")
    for sid, n in sorted(payload["wins_by_solver"].items(), key=lambda kv: -kv[1]):
        print(f"  {sid:28s} {n}")
    judging = payload.get("q_solve_judging", {}).get("suggested_self_score", {})
    print("\nQ-SOLVE judging self-estimate:")
    print("  raw:", judging.get("raw_score"), "/ 100")
    print("  confidence:", judging.get("evidence_confidence"), "×", judging.get("multiplier"))
    print("  washing:", judging.get("quantum_washing"), "penalty", judging.get("penalty"))
    print("  final estimate:", judging.get("final_score_estimate"))
    gaps = payload.get("q_solve_judging", {}).get("evidence_gaps", [])
    if gaps:
        print("  evidence gaps:", ", ".join(gaps))
    else:
        print("  evidence gaps: none flagged")
    print(f"\nElapsed: {elapsed:.1f}s")
    print("Wrote", args.out)


if __name__ == "__main__":
    main()
