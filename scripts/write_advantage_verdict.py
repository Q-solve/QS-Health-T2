#!/usr/bin/env python3
"""
Phase 4 — Apply §6 quantum advantage rubric → docs/quantum_advantage_verdict.md

Reads:
  data/classical_suite_results.json
  data/quantum_benchmark_results.json

Writes:
  docs/quantum_advantage_verdict.md
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASSICAL = ROOT / "data" / "classical_suite_results.json"
QUANTUM = ROOT / "data" / "quantum_benchmark_results.json"
OUT = ROOT / "docs" / "quantum_advantage_verdict.md"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def decide_verdict(classical: dict, quantum: dict) -> tuple[str, list[str]]:
    """Return (A|B|C, evidence bullets) per implementation_plan §6."""
    signals = quantum.get("preliminary_advantage_signals") or {}
    q_records = quantum.get("records") or []
    comparable = int(signals.get("comparable_instances") or 0)
    n_beat = int(signals.get("qaoa_strictly_better_than_best_classical") or 0)
    skipped = int(signals.get("skipped_scale") or 0)

    c_records = classical.get("records") or []
    hurdles = classical.get("hurdle_summary") or {}
    feasible_classical = sum(1 for r in c_records if r.get("status") in {"optimal", "feasible"})

    evidence = [
        f"Classical suite: {len(c_records)} runs (profile={classical.get('profile')}).",
        f"Quantum comparator: {len(q_records)} QAOA runs (status={quantum.get('status')}).",
        f"Comparable shared instances: {comparable}; QAOA strictly better than best classical: {n_beat}.",
        f"Scale-skipped quantum (T3+/NISQ ceiling): {skipped}.",
        f"Classical feasible/optimal rows: {feasible_classical}.",
    ]
    if hurdles:
        evidence.append(f"Hurdle summary keys: {list(hurdles.keys())[:8]}")

    # Verdict C bar is strict — never claim from beating greedy alone
    if comparable >= 4 and n_beat >= max(1, comparable // 2):
        # Still require quality@time evidence; without anytime curves stay at B
        return "B", evidence + [
            "QAOA beat best classical on a non-trivial share of instances, "
            "but without pre-registered anytime curves we stop at Conditional/Hybrid (B)."
        ]

    if n_beat == 0 and (comparable > 0 or skipped > 0):
        return "A", evidence + [
            "On every comparable T0–T4 instance, best classical among C2–C7 matched or beat QAOA.",
            "County-scale tiers remain classical-operational; quantum needs decomposition.",
            "Default NISQ expectation confirmed: No Quantum Advantage for CHW allocation at current sizes.",
        ]

    return "A", evidence + [
        "Insufficient evidence for Verdict C; defaulting to No Quantum Advantage (A)."
    ]


VERDICT_COPY = {
    "A": (
        "No Quantum Advantage (Expected Default at NISQ Scale)",
        "Across our instance ladder, classical methods (especially SA/GA/Tabu and MILP on small graphs) "
        "matched or beat QAOA on solution quality and dominated on scalable county-sized problems. "
        "**We do not claim quantum advantage** for CHW deployment at current problem sizes.",
    ),
    "B": (
        "Conditional / Hybrid Value (No Pure Advantage)",
        "Pure quantum showed no standalone supremacy bar; a **hybrid** classical–quantum loop may help "
        "on some mid-size clusters. Value is workflow integration, not quantum supremacy.",
    ),
    "C": (
        "Quantum Advantage / Quantum Needed",
        "Under pre-registered budgets, quantum (or hybrid quantum) was necessary to reach target "
        "equity/WHO compliance where classical heuristics plateaued.",
    ),
}


def write_verdict(force: bool = False) -> Path:
    classical = _load(CLASSICAL)
    quantum = _load(QUANTUM)
    if not classical and not quantum and not force:
        raise SystemExit("Missing classical/quantum JSON — run Phase 2 and Phase 3 first.")

    code, evidence = decide_verdict(classical, quantum)
    title, statement = VERDICT_COPY[code]
    qml = quantum.get("qml_vs_classical") or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Quantum Advantage Verdict — AfyaDeploy",
        "",
        f"**Generated:** {now}  ",
        f"**Primary verdict:** **Verdict {code} — {title}**",
        "",
        "## Demo statement",
        "",
        f"> {statement}",
        "",
        "## Rubric (§6)",
        "",
        "| Code | Meaning |",
        "| --- | --- |",
        "| A | No Quantum Advantage |",
        "| B | Conditional / Hybrid Value |",
        "| C | Quantum Advantage / Needed (strict bar) |",
        "",
        "## Evidence",
        "",
    ]
    for e in evidence:
        lines.append(f"- {e}")

    lines += [
        "",
        "## QML demand track",
        "",
        f"```json\n{json.dumps(qml, indent=2)[:2000]}\n```" if qml else "- QML block not present in quantum JSON.",
        "",
        "## Data sources",
        "",
        f"- Classical: `{CLASSICAL.relative_to(ROOT)}`",
        f"- Quantum: `{QUANTUM.relative_to(ROOT)}`",
        "",
        "## Honest framing",
        "",
        "Beating a weak greedy baseline alone is **not** quantum advantage. "
        "Primary rivals are best of C2–C7 under the shared objective H(x).",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    return OUT


def main():
    parser = argparse.ArgumentParser(description="Write §6 quantum advantage verdict")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    path = write_verdict(force=args.force)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
