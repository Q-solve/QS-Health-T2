#!/usr/bin/env python3
"""
Headless benchmark used for pitch-deck plots (Day 3).

Runs classical (+ QAOA when qubit budget allows) across sample scenarios
and writes docs/benchmark_classical_vs_quantum.png plus a CSV summary.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402
from backend.optimization.compare import compare_solvers  # noqa: E402
from backend.scenario import (  # noqa: E402
    demo_nairobi_kajiado_scenario,
    quantum_sized_scenario,
    toy_3clinic_scenario,
)


def main() -> None:
    scenarios = [
        toy_3clinic_scenario(),
        quantum_sized_scenario(),
        demo_nairobi_kajiado_scenario(),
    ]
    records: list[dict] = []

    for sc in scenarios:
        methods = ["greedy"]
        if sc.num_binary_vars <= config.MAX_QUBITS_SIMULATOR:
            methods.append("qaoa")
        print(f"→ {sc.name} methods={methods} vars={sc.num_binary_vars}")
        payload = compare_solvers(sc, methods=methods, qaoa_maxiter=30)
        for row in payload["results"]:
            records.append(
                {
                    "scenario": sc.name,
                    "method": row["method"],
                    "total_cost": row["total_cost"],
                    "runtime_s": row["runtime_seconds"],
                    "quality": row["quality_score"],
                    "n_vars": sc.num_binary_vars,
                }
            )
            print(
                f"   {row['method']:22s} cost={row['total_cost']:.2f}  "
                f"t={row['runtime_seconds']:.2f}s  q={row['quality_score']}"
            )

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    csv_path = docs / "benchmark_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    print("Wrote", csv_path)

    # Plot
    methods = sorted({r["method"] for r in records})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    colors = {
        "greedy": "#4a5568",
        "qaoa": "#0f766e",
    }

    for method in methods:
        pts = [r for r in records if r["method"] == method]
        pts = sorted(pts, key=lambda r: r["n_vars"])
        xs = [p["n_vars"] for p in pts]
        axes[0].plot(xs, [p["total_cost"] for p in pts], "o-", label=method, color=colors.get(method))
        axes[1].plot(xs, [p["runtime_s"] for p in pts], "o-", label=method, color=colors.get(method))

    axes[0].set_xlabel("# binary variables")
    axes[0].set_ylabel("Soft cost (lower better)")
    axes[0].set_title("Solution quality vs problem size")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)

    axes[1].set_xlabel("# binary variables")
    axes[1].set_ylabel("Runtime (seconds)")
    axes[1].set_title("Runtime vs problem size")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)

    fig.suptitle(
        "Outbreak planner — classical vs QAOA (honest NISQ-scale comparison)",
        fontsize=11,
    )
    plt.tight_layout()
    png = docs / "benchmark_classical_vs_quantum.png"
    plt.savefig(png, dpi=150)
    print("Wrote", png)


if __name__ == "__main__":
    main()
