"""
Shared classical ↔ quantum benchmark catalogue.

Joins ladder instance keys so UI and scripts compare apples-to-apples.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend import config

ROOT = config.PROJECT_ROOT
CLASSICAL_JSON = ROOT / "data" / "classical_suite_results.json"
QUANTUM_JSON = ROOT / "data" / "quantum_benchmark_results.json"
VERDICT_MD = ROOT / "docs" / "quantum_advantage_verdict.md"


def _instance_key(rec: Dict[str, Any]) -> Tuple:
    return (
        rec.get("tier"),
        str(rec.get("county", "")).upper(),
        int(rec.get("seed", 0)),
        str(rec.get("constraint_setting", "nominal")).lower(),
        str(rec.get("feature_stage", "B4")).upper(),
    )


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_classical_records() -> List[Dict[str, Any]]:
    return list(_load_json(CLASSICAL_JSON).get("records") or [])


def load_quantum_records() -> List[Dict[str, Any]]:
    return list(_load_json(QUANTUM_JSON).get("records") or [])


def shared_instance_catalogue() -> Dict[str, Any]:
    """
    Catalogue of instances present in classical and/or quantum result stores.
    Enables fair side-by-side benchmarking in the UI.
    """
    classical = load_classical_records()
    quantum = load_quantum_records()

    classical_by_key: Dict[Tuple, List[Dict[str, Any]]] = {}
    for r in classical:
        if not r.get("solver_id"):
            continue
        classical_by_key.setdefault(_instance_key(r), []).append(r)

    quantum_by_key: Dict[Tuple, Dict[str, Any]] = {}
    for r in quantum:
        quantum_by_key[_instance_key(r)] = r

    all_keys = sorted(set(classical_by_key) | set(quantum_by_key))
    instances: List[Dict[str, Any]] = []
    both = 0
    classical_only = 0
    quantum_only = 0

    for key in all_keys:
        tier, county, seed, constraint, stage = key
        c_recs = classical_by_key.get(key, [])
        q_rec = quantum_by_key.get(key)
        presence = "both" if c_recs and q_rec else ("classical_only" if c_recs else "quantum_only")
        if presence == "both":
            both += 1
        elif presence == "classical_only":
            classical_only += 1
        else:
            quantum_only += 1

        best_classical = None
        if c_recs:
            scored = [r for r in c_recs if r.get("objective_value") is not None]
            if scored:
                best = min(scored, key=lambda r: r["objective_value"])
                best_classical = {
                    "solver_id": best.get("solver_id"),
                    "objective_value": best.get("objective_value"),
                    "status": best.get("status"),
                    "execution_time_sec": best.get("execution_time_sec"),
                    "gini_equity_index": best.get("gini_equity_index"),
                }

        instances.append(
            {
                "tier": tier,
                "county": county,
                "seed": seed,
                "constraint_setting": constraint,
                "feature_stage": stage,
                "presence": presence,
                "num_variables": (q_rec or (c_recs[0] if c_recs else {})).get("num_variables"),
                "classical_solver_count": len({r.get("solver_id") for r in c_recs}),
                "best_classical": best_classical,
                "quantum": {
                    "objective_value": q_rec.get("objective_value"),
                    "status": q_rec.get("status"),
                    "beats_best_classical": q_rec.get("beats_best_classical"),
                    "gap_to_best_classical": q_rec.get("gap_to_best_classical"),
                    "backend": q_rec.get("backend"),
                    "execution_time_sec": q_rec.get("execution_time_sec"),
                }
                if q_rec
                else None,
            }
        )

    qmeta = _load_json(QUANTUM_JSON)
    cmeta = _load_json(CLASSICAL_JSON)
    return {
        "classical_source": str(CLASSICAL_JSON.relative_to(ROOT)),
        "quantum_source": str(QUANTUM_JSON.relative_to(ROOT)),
        "classical_n_runs": len(classical),
        "quantum_n_runs": len(quantum),
        "instances_total": len(instances),
        "instances_both": both,
        "instances_classical_only": classical_only,
        "instances_quantum_only": quantum_only,
        "preliminary_advantage_signals": qmeta.get("preliminary_advantage_signals"),
        "classical_profile": cmeta.get("profile"),
        "quantum_status": qmeta.get("status"),
        "instances": instances,
    }


def paired_comparison_rows() -> List[Dict[str, Any]]:
    """Only instances present in both stores — ready for side-by-side table."""
    cat = shared_instance_catalogue()
    return [i for i in cat["instances"] if i["presence"] == "both"]


def _usable_classical_pick(q_rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Prefer a covered classical run from all_runs; fall back to best_classical.
    Skips empty / bottleneck incumbents that can undercut real heuristics on H(x).
    """
    bc = q_rec.get("best_classical") or {}
    candidates: List[Dict[str, Any]] = []
    for run in list(bc.get("all_runs") or []):
        if run.get("objective_value") is None:
            continue
        if run.get("status") in {"bottleneck", "error", "infeasible"}:
            continue
        if float(run.get("population_coverage_pct") or 0.0) <= 0.0:
            continue
        candidates.append(run)
    if candidates:
        best = min(candidates, key=lambda r: float(r["objective_value"]))
        return {
            "solver_id": best.get("solver_id"),
            "objective_value": float(best["objective_value"]),
            "status": best.get("status"),
            "execution_time_sec": best.get("execution_time_sec"),
            "who_compliance_pct": best.get("who_compliance_pct"),
            "population_coverage_pct": best.get("population_coverage_pct"),
            "gini_equity_index": best.get("gini_equity_index"),
        }
    if bc.get("objective_value") is not None:
        return {
            "solver_id": bc.get("solver_id"),
            "objective_value": float(bc["objective_value"]),
            "status": bc.get("status"),
            "execution_time_sec": bc.get("execution_time_sec"),
            "who_compliance_pct": bc.get("who_compliance_pct"),
            "population_coverage_pct": bc.get("population_coverage_pct"),
            "gini_equity_index": bc.get("gini_equity_index"),
        }
    return None


def objective_h_comparison() -> Dict[str, Any]:
    """
    Published H(x) table: classical optimised value vs quantum objective value
    from data/quantum_benchmark_results.json (joined against best usable classical).
    Lower H(x) is better.
    """
    qmeta = _load_json(QUANTUM_JSON)
    records = list(qmeta.get("records") or [])
    rows: List[Dict[str, Any]] = []
    n_tie = 0
    n_classical_better = 0
    n_quantum_better = 0

    for rec in records:
        classical = _usable_classical_pick(rec)
        q_obj = rec.get("objective_value")
        c_obj = None if classical is None else classical.get("objective_value")
        gap = None
        winner = "n/a"
        if q_obj is not None and c_obj is not None:
            q_f = float(q_obj)
            c_f = float(c_obj)
            gap = (q_f - c_f) / max(abs(c_f), 1e-9)
            if abs(q_f - c_f) <= 1e-6 * max(abs(c_f), 1.0):
                winner = "tie"
                n_tie += 1
            elif q_f < c_f:
                winner = "quantum"
                n_quantum_better += 1
            else:
                winner = "classical"
                n_classical_better += 1

        rows.append(
            {
                "tier": rec.get("tier"),
                "county": rec.get("county"),
                "seed": rec.get("seed"),
                "constraint_setting": rec.get("constraint_setting"),
                "feature_stage": rec.get("feature_stage"),
                "num_variables": rec.get("num_variables"),
                "classical_solver": None if classical is None else classical.get("solver_id"),
                "classical_H": c_obj,
                "classical_status": None if classical is None else classical.get("status"),
                "classical_time_sec": None if classical is None else classical.get("execution_time_sec"),
                "quantum_H": None if q_obj is None else float(q_obj),
                "quantum_status": rec.get("status"),
                "quantum_backend": rec.get("backend"),
                "quantum_time_sec": rec.get("execution_time_sec"),
                "gap_qaoa_to_classical": None if gap is None else round(float(gap), 6),
                "lower_H_wins": winner,
                "beats_best_classical": winner == "quantum",
            }
        )

    # Stable demo order: tier then county
    tier_order = {f"T{i}": i for i in range(7)}
    rows.sort(key=lambda r: (tier_order.get(str(r.get("tier")), 99), str(r.get("county") or "")))

    return {
        "source": str(QUANTUM_JSON.relative_to(ROOT)),
        "classical_source": str(CLASSICAL_JSON.relative_to(ROOT)),
        "metric": "shared objective H(x) — lower is better",
        "n": len(rows),
        "summary": {
            "tie": n_tie,
            "classical_lower_H": n_classical_better,
            "quantum_lower_H": n_quantum_better,
        },
        "rows": rows,
    }


def dataset_inventory() -> Dict[str, Any]:
    """Account for all primary CSVs used by the ladder / ML pipeline."""
    files = {
        "unified_chw_dataset.csv": ROOT / "data" / "unified_chw_dataset.csv",
        "community_units_kmhfr.csv": ROOT / "data" / "community_units_kmhfr.csv",
        "county_verified_indicators.csv": ROOT / "data" / "county_verified_indicators.csv",
        "classical_suite_results.json": CLASSICAL_JSON,
        "quantum_benchmark_results.json": QUANTUM_JSON,
        "classical_hurdles.json": ROOT / "data" / "classical_hurdles.json",
        "DATA_SOURCES.md": ROOT / "data" / "DATA_SOURCES.md",
    }
    inventory = {}
    for name, path in files.items():
        inventory[name] = {
            "exists": path.exists(),
            "path": str(path.relative_to(ROOT)) if path.exists() else None,
            "bytes": path.stat().st_size if path.exists() else 0,
        }
    return {
        "target_counties": 14,
        "files": inventory,
        "notes": (
            "Facilities + CHUs feed ladder T0–T6. Classical and quantum JSON share "
            "(tier, county, seed, constraint, feature_stage) keys for fair compare."
        ),
    }


def load_verdict_summary() -> Dict[str, Any]:
    if not VERDICT_MD.exists():
        return {
            "status": "not_yet_computed",
            "note": "Run scripts/write_advantage_verdict.py after Phase 2 + Phase 3.",
            "path": None,
        }
    text = VERDICT_MD.read_text()
    verdict_line = "Verdict pending"
    for line in text.splitlines():
        if "**Primary verdict:**" in line:
            # Strip markdown bold markers for clean UI text
            verdict_line = line.replace("**", "").replace("#", "").strip()
            break
        if line.startswith("## Verdict"):
            verdict_line = line.strip("# ").strip()
            break
    return {
        "status": "ready",
        "path": str(VERDICT_MD.relative_to(ROOT)),
        "summary_line": verdict_line,
        "markdown": text,
    }
