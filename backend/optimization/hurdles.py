"""
Classical hurdle labels for the instance ladder.

Separates *algorithm* failure from *staffing* failure so quantum is only
considered where classical solvers actually stall.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

EXACT_IDS = {"c1_brute_force", "c2_milp"}
HEURISTIC_IDS = {
    "c3_greedy",
    "c4_local_search",
    "c5_simulated_annealing",
    "c6_genetic_algorithm",
    "c7_tabu_search",
}

# T0–T4 are NISQ-comparable; T5–T6 need decomposition for any quantum path.
QUANTUM_COMPARABLE_TIERS = {"T0", "T1", "T2", "T3", "T4"}


def record_usable(rec: Dict[str, Any]) -> bool:
    if rec.get("status") in {"bottleneck", "error", "infeasible"}:
        return False
    if rec.get("objective_value") is None:
        return False
    if float(rec.get("population_coverage_pct") or 0.0) <= 0.0:
        return False
    return True


def instance_key(rec: Dict[str, Any]) -> Tuple:
    return (
        rec.get("tier"),
        rec.get("county"),
        rec.get("seed"),
        rec.get("constraint_setting"),
        rec.get("feature_stage"),
        rec.get("who_capacity_mode"),
    )


def classify_instance(batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """One hurdle label per (tier, county, seed, constraint, stage) batch."""
    if not batch:
        return {"hurdle": "no_data", "quantum_candidate": False}

    sample = batch[0]
    usable = [r for r in batch if record_usable(r)]
    exact = [r for r in batch if r.get("solver_id") in EXACT_IDS]
    exact_usable = [r for r in exact if record_usable(r)]
    heur_usable = [r for r in usable if r.get("solver_id") in HEURISTIC_IDS]

    g_star = float(sample.get("equity_target") or 0.25)
    best = min(usable, key=lambda r: r["objective_value"]) if usable else None
    best_meets = False
    who_ok = False
    gini_ok = False
    if best is not None:
        gini_ok = (best.get("gini_equity_index") or 1.0) <= g_star
        who_ok = (best.get("who_compliance_pct") or 0.0) >= 80.0
        best_meets = gini_ok and who_ok

    exact_statuses = {r.get("status") for r in exact}
    exact_all_unusable = bool(exact) and not exact_usable
    exact_scale = exact_all_unusable and all(
        r.get("status") in {"bottleneck", "error"} for r in exact
    )
    exact_timeout = exact_all_unusable and any(r.get("status") == "timeout" for r in exact)

    if not usable:
        hurdle = "all_failed"
        note = "No solver returned a covered assignment."
    elif not who_ok and exact_usable:
        hurdle = "staffing_or_equity"
        note = "Even exact classical misses WHO load targets (staffing/packing)."
    elif not who_ok:
        hurdle = "heuristic_quality"
        note = "Heuristics missed WHO load even though a packing-feasible staff level was provided."
    elif not gini_ok:
        hurdle = "equity_geography"
        note = "WHO load is met; remaining Gini gap is distance inequality, not a solver crash."
    elif exact_scale:
        hurdle = "exact_scale"
        note = "Exact C1/C2 cannot run; heuristics still return a plan that meets WHO."
    elif exact_timeout:
        hurdle = "exact_timeout"
        note = "Exact solver hit the time budget; heuristics still meet WHO."
    else:
        hurdle = "classical_ok"
        note = "Best classical meets coverage + WHO + Gini under this budget."

    quantum_candidate = (
        sample.get("tier") in QUANTUM_COMPARABLE_TIERS
        and hurdle in {"exact_scale", "exact_timeout", "heuristic_quality", "all_failed"}
    )
    # Quantum is *needed* only if heuristics also fail operational targets on T3–T4.
    quantum_needed_candidate = (
        sample.get("tier") in {"T3", "T4"}
        and hurdle in {"heuristic_quality", "all_failed"}
    )

    return {
        "tier": sample.get("tier"),
        "county": sample.get("county"),
        "seed": sample.get("seed"),
        "constraint_setting": sample.get("constraint_setting"),
        "feature_stage": sample.get("feature_stage"),
        "who_capacity_mode": sample.get("who_capacity_mode"),
        "num_variables": sample.get("num_variables"),
        "hurdle": hurdle,
        "note": note,
        "quantum_candidate": quantum_candidate,
        "quantum_needed_candidate": quantum_needed_candidate,
        "best_solver": None if best is None else best.get("solver_id"),
        "best_objective": None if best is None else best.get("objective_value"),
        "best_gini": None if best is None else best.get("gini_equity_index"),
        "best_who_pct": None if best is None else best.get("who_compliance_pct"),
        "best_coverage_pct": None if best is None else best.get("population_coverage_pct"),
        "best_d_p90_km": None if best is None else best.get("d_p90_km"),
        "n_solvers": len(batch),
        "n_usable": len(usable),
        "exact_statuses": sorted(s for s in exact_statuses if s),
    }


def summarize_hurdles(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    groups: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
    for rec in records:
        if not rec.get("solver_id"):
            continue
        groups[instance_key(rec)].append(rec)
    instances = [classify_instance(batch) for batch in groups.values()]
    by_tier: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_hurdle: Dict[str, int] = defaultdict(int)
    by_mode: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for inst in instances:
        by_tier[str(inst.get("tier"))][inst["hurdle"]] += 1
        by_hurdle[inst["hurdle"]] += 1
        by_mode[str(inst.get("who_capacity_mode") or "raw")][inst["hurdle"]] += 1

    q_cand = [i for i in instances if i.get("quantum_candidate")]
    q_need = [i for i in instances if i.get("quantum_needed_candidate")]
    return {
        "n_instances": len(instances),
        "hurdle_counts": dict(by_hurdle),
        "by_tier": {t: dict(h) for t, h in sorted(by_tier.items())},
        "by_who_capacity_mode": {m: dict(h) for m, h in sorted(by_mode.items())},
        "quantum_candidate_count": len(q_cand),
        "quantum_needed_candidate_count": len(q_need),
        "quantum_candidates": q_cand,
        "instances": instances,
        "interpretation": {
            "classical_ok": "Classical meets coverage + WHO + Gini — not a quantum-necessity instance.",
            "staffing_or_equity": "Even exact classical misses WHO. Quantum cannot invent staff.",
            "equity_geography": "WHO is met; Gini stays high because of real walking distances. Quantum cannot shorten roads.",
            "exact_scale": "Exact classical cannot run at this N. Heuristics still work — hybrid/decomposition, not QPU, is the operational path.",
            "exact_timeout": "Exact classical timed out; heuristics produced a WHO-feasible plan. Compare quantum only vs best heuristic, not vs greedy.",
            "heuristic_quality": "Heuristics missed WHO load. This is the only regime where a fair QAOA vs C4–C7 test could matter.",
            "all_failed": "No covered assignment. Check data/capacity before claiming a solver failure.",
        },
    }
