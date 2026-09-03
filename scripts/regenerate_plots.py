#!/usr/bin/env python3
"""Regenerate classical scaling / quality / failure plots from existing JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_classical_suite import write_hurdle_plot, write_plots  # noqa: E402


def main() -> None:
    results = ROOT / "data" / "classical_suite_results.json"
    hurdles_path = ROOT / "data" / "classical_hurdles.json"
    docs = ROOT / "docs"
    payload = json.loads(results.read_text())
    records = payload.get("records") or []
    plots = write_plots(records, docs)
    if hurdles_path.exists():
        summary = json.loads(hurdles_path.read_text())
        hp = write_hurdle_plot(summary, docs)
        if hp:
            plots.append(hp)
    # Also refresh plot list in JSON
    payload["plots"] = plots
    results.write_text(json.dumps(payload, indent=2))
    print("Wrote plots:")
    for p in plots:
        print(" ", p)


if __name__ == "__main__":
    main()
