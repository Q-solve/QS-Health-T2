"""
Classical solver ranking + quantum opportunity map for the dashboard.

Reads published classical ladder results and (optionally) quantum comparator
JSON. Ranking is quality-first under shared H(x); quantum opportunities are
framed as additive / hybrid value — not claims that quantum replaces classical.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Optional, Tuple

from backend import config
from backend.optimization.benchmark_store import CLASSICAL_JSON, QUANTUM_JSON
from backend.optimization.hurdles import (
    instance_key,
    record_usable,
    summarize_hurdles,
)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(config.PROJECT_ROOT.resolve()))
    except Exception:
        return str(path)

SOLVER_META = {
    "c1_brute_force": {
        "short": "C1 Brute Force",
        "role": "Exact oracle on tiny graphs (T0–T1).",
        "scope": "exact_small",
    },
    "c2_milp": {
        "short": "C2 MILP",
        "role": "Exact / near-exact ILP; hits scale wall mid-ladder.",
        "scope": "exact_mid",
    },
    "c3_greedy": {
        "short": "C3 Greedy",
        "role": "Fast baseline; rarely near-optimal H(x).",
        "scope": "heuristic_all",
    },
    "c4_local_search": {
        "short": "C4 Local Search",
        "role": "Strong quality/time workhorse across tiers.",
        "scope": "heuristic_all",
    },
    "c5_simulated_annealing": {
        "short": "C5 Simulated Annealing",
        "role": "Metaheuristic; competitive near-best rate.",
        "scope": "heuristic_all",
    },
    "c6_genetic_algorithm": {
        "short": "C6 Genetic Algorithm",
        "role": "Population search; often ties best, slower.",
        "scope": "heuristic_all",
    },
    "c7_tabu_search": {
        "short": "C7 Tabu Search",
        "role": "Metaheuristic; frequent time-budget hits.",
        "scope": "heuristic_all",
    },
}

# Honest opportunity catalogue: classical failure / limit → quantum role.
# Evidence status is calibrated to current NISQ results (Verdict A default).
QUANTUM_OPPORTUNITY_CATALOGUE: List[Dict[str, Any]] = [
    {
        "id": "exact_scale",
        "classical_failure": "Exact solvers (C1/C2) bottleneck or cannot run at T4+",
        "when_classical_still_works": (
            "Heuristics (C4–C7) usually still return a covered WHO-feasible plan."
        ),
        "quantum_can_add": (
            "Hybrid path: partition the county graph, run QAOA on hard mid-size "
            "subQUBOs, then stitch with classical local search. Quantum explores "
            "assignment modes classical exact methods never reach under the budget."
        ),
        "advantage_type": "scalability_hybrid",
        "evidence_status": "candidate",
        "not_a_claim": "Does not mean pure QAOA beats heuristics on full county N today.",
    },
    {
        "id": "exact_timeout",
        "classical_failure": "MILP times out before proving optimality (T3+)",
        "when_classical_still_works": (
            "Incumbent or heuristics often remain operationally usable."
        ),
        "quantum_can_add": (
            "Quality-at-time: QAOA shot samples give a diverse pool of near-feasible "
            "bitstrings in one circuit execution; classical repair + evaluate_H can "
            "pick improvements while MILP is still branching."
        ),
        "advantage_type": "anytime_sampling",
        "evidence_status": "candidate",
        "not_a_claim": "Current p=1 fixed-angle QAOA has not beaten best classical yet.",
    },
    {
        "id": "heuristic_quality",
        "classical_failure": "Heuristics miss WHO load / packing targets on some instances",
        "when_classical_still_works": (
            "Coverage may still be 100%; the gap is capacity packing quality."
        ),
        "quantum_can_add": (
            "QAOA on the capacity–assignment QUBO can sample alternate packings. "
            "Use as a diversifier inside a classical loop (warm-start / reseed C4–C7)."
        ),
        "advantage_type": "landscape_diversification",
        "evidence_status": "candidate",
        "not_a_claim": "Staffing shortages still cannot be invented by any solver.",
    },
    {
        "id": "equity_geography",
        "classical_failure": "WHO met but Gini stays high because walks are long",
        "when_classical_still_works": (
            "Classical already returns a feasible plan; geography is the limit."
        ),
        "quantum_can_add": (
            "Not road-shortening. Value is multi-objective tradeoff sampling: "
            "quantum + classical can surface Pareto-ish assignment variants that "
            "trade a little travel for better equity under the same H(x) weights."
        ),
        "advantage_type": "multiobjective_exploration",
        "evidence_status": "aspirational",
        "not_a_claim": "Quantum cannot change terrain; equity gaps are mostly geographic.",
    },
    {
        "id": "staffing_or_equity",
        "classical_failure": "Even exact classical misses WHO under raw staffing",
        "when_classical_still_works": "N/A — problem is under-staffed, not under-solved.",
        "quantum_can_add": (
            "No solver advantage. Quantum's role here is analysis only: show that "
            "the bottleneck is headcount, then recommend CHW hiring — not a QPU."
        ),
        "advantage_type": "none_data_limit",
        "evidence_status": "not_applicable",
        "not_a_claim": "Quantum cannot invent CHWs.",
    },
    {
        "id": "classical_ok",
        "classical_failure": "No failure — classical meets coverage + WHO + Gini",
        "when_classical_still_works": "Primary operational path is classical.",
        "quantum_can_add": (
            "Additive value even when classical wins: (1) solution-ensemble from "
            "measurement counts for contingency planning, (2) second-opinion "
            "comparator on NISQ-sized wards, (3) research evidence for JC2/JC5 "
            "that quantum was stress-tested fairly against best of C2–C7."
        ),
        "advantage_type": "ensemble_and_evidence",
        "evidence_status": "demonstrated_workflow",
        "not_a_claim": "Beating greedy alone is not advantage; current QAOA ties or loses vs best classical.",
    },
    {
        "id": "time_budget_metaheuristics",
        "classical_failure": "GA / Tabu hit wall-clock budgets at larger tiers",
        "when_classical_still_works": "Greedy / local search / SA usually still finish.",
        "quantum_can_add": (
            "On partitions small enough for the simulator/QPU, fixed-depth QAOA "
            "amortizes exploration across shots instead of long serial cooling loops."
        ),
        "advantage_type": "parallel_sampling",
        "evidence_status": "candidate",
        "not_a_claim": "Queue + circuit time still dominate vs millisecond greedy.",
    },
    {
        "id": "county_scale_decomposition",
        "classical_failure": "T5–T6 county graphs exceed NISQ and stress exact classical",
        "when_classical_still_works": "Heuristics remain the deployment engine today.",
        "quantum_can_add": (
            "Spatial decomposition hybrid: classical clustering → quantum on hard "
            "clusters → classical stitch. This is the intended scale-up path, not "
            "monolithic QAOA on thousands of variables."
        ),
        "advantage_type": "decomposition_hybrid",
        "evidence_status": "roadmap",
        "not_a_claim": "Not implemented as a production win in current benchmarks.",
    },
]


def _safe_median(vals: List[float]) -> Optional[float]:
    if not vals:
        return None
    return float(median(vals))


def _safe_mean(vals: List[float]) -> Optional[float]:
    if not vals:
        return None
    return float(mean(vals))


def _near_best(obj: float, best: float, rtol: float = 1e-6) -> bool:
    return abs(obj - best) <= rtol * max(abs(best), 1.0)


def rank_classical_solvers(records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Rank C1–C7 from published ladder runs.

    Primary sort: near-best rate (share of usable runs within ~best H).
    Tie-breakers: exclusive wins, usable rate, lower median gap, lower median time.
    """
    if records is None:
        records = list(_load_json(CLASSICAL_JSON).get("records") or [])

    groups: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
    for rec in records:
        sid = rec.get("solver_id")
        if not sid:
            continue
        groups[instance_key(rec)].append(rec)

    stats: Dict[str, Dict[str, Any]] = {
        sid: {
            "solver_id": sid,
            "n_runs": 0,
            "n_usable": 0,
            "exclusive_wins": 0,
            "near_best_count": 0,
            "gaps": [],
            "times": [],
            "who": [],
            "gini": [],
            "coverage": [],
            "status_counts": defaultdict(int),
            "tier_near_best": defaultdict(int),
            "tier_runs": defaultdict(int),
        }
        for sid in SOLVER_META
    }

    n_instances = 0
    for _key, batch in groups.items():
        n_instances += 1
        usable = [r for r in batch if record_usable(r) and r.get("solver_id") in stats]
        best_obj = min((float(r["objective_value"]) for r in usable), default=None)

        for rec in batch:
            sid = rec.get("solver_id")
            if sid not in stats:
                continue
            s = stats[sid]
            s["n_runs"] += 1
            s["status_counts"][str(rec.get("status") or "unknown")] += 1
            s["tier_runs"][str(rec.get("tier") or "?")] += 1
            t = rec.get("execution_time_sec")
            if t is not None:
                s["times"].append(float(t))
            if not record_usable(rec) or best_obj is None:
                continue
            s["n_usable"] += 1
            obj = float(rec["objective_value"])
            gap = (obj - best_obj) / max(abs(best_obj), 1e-9)
            s["gaps"].append(gap)
            if rec.get("who_compliance_pct") is not None:
                s["who"].append(float(rec["who_compliance_pct"]))
            if rec.get("gini_equity_index") is not None:
                s["gini"].append(float(rec["gini_equity_index"]))
            if rec.get("population_coverage_pct") is not None:
                s["coverage"].append(float(rec["population_coverage_pct"]))
            if _near_best(obj, best_obj):
                s["near_best_count"] += 1
                s["tier_near_best"][str(rec.get("tier") or "?")] += 1

        if usable and best_obj is not None:
            winners = [r for r in usable if _near_best(float(r["objective_value"]), best_obj)]
            if len(winners) == 1:
                sid = winners[0]["solver_id"]
                if sid in stats:
                    stats[sid]["exclusive_wins"] += 1

    ranked_rows: List[Dict[str, Any]] = []
    for sid, s in stats.items():
        n_runs = s["n_runs"] or 1
        n_usable = s["n_usable"]
        near = s["near_best_count"]
        timeouts = int(s["status_counts"].get("timeout", 0))
        bottlenecks = int(s["status_counts"].get("bottleneck", 0))
        usable_rate = (n_usable / n_runs) if n_runs else 0.0
        near_best_rate = (near / n_usable) if n_usable else 0.0
        fail_rate = (timeouts + bottlenecks) / n_runs if n_runs else 0.0
        med_gap = _safe_median(s["gaps"])
        med_time = _safe_median(s["times"])

        # Composite: quality first, then reliability, then speed (inverted).
        # Speed score saturates so ms vs seconds does not dominate quality.
        speed_score = 1.0 / (1.0 + (med_time or 0.0))
        composite = (
            0.55 * near_best_rate
            + 0.20 * usable_rate
            + 0.15 * (1.0 - min(fail_rate, 1.0))
            + 0.10 * speed_score
        )

        ranked_rows.append(
            {
                "solver_id": sid,
                "name": SOLVER_META[sid]["short"],
                "role": SOLVER_META[sid]["role"],
                "scope": SOLVER_META[sid]["scope"],
                "n_runs": s["n_runs"],
                "n_usable": n_usable,
                "usable_rate": round(usable_rate, 4),
                "near_best_rate": round(near_best_rate, 4),
                "near_best_count": near,
                "exclusive_wins": s["exclusive_wins"],
                "median_gap_to_best": None if med_gap is None else round(med_gap, 6),
                "median_time_sec": None if med_time is None else round(med_time, 4),
                "mean_who_compliance_pct": None
                if not s["who"]
                else round(_safe_mean(s["who"]) or 0.0, 2),
                "mean_gini": None if not s["gini"] else round(_safe_mean(s["gini"]) or 0.0, 4),
                "mean_coverage_pct": None
                if not s["coverage"]
                else round(_safe_mean(s["coverage"]) or 0.0, 2),
                "timeout_count": timeouts,
                "bottleneck_count": bottlenecks,
                "fail_rate": round(fail_rate, 4),
                "status_counts": dict(s["status_counts"]),
                "tier_near_best": dict(s["tier_near_best"]),
                "tier_runs": dict(s["tier_runs"]),
                "composite_score": round(composite, 4),
            }
        )

    ranked_rows.sort(
        key=lambda r: (
            -r["composite_score"],
            -r["near_best_rate"],
            -r["exclusive_wins"],
            -r["usable_rate"],
            r["median_gap_to_best"] if r["median_gap_to_best"] is not None else 1e9,
            r["median_time_sec"] if r["median_time_sec"] is not None else 1e9,
        )
    )
    for i, row in enumerate(ranked_rows, start=1):
        row["rank"] = i

    # Operational board: exclude C1 (toy exact only). Primary demo rival is best of C2–C7.
    operational = [r for r in ranked_rows if r["solver_id"] != "c1_brute_force"]
    for i, row in enumerate(operational, start=1):
        row["operational_rank"] = i
    for row in ranked_rows:
        if "operational_rank" not in row:
            row["operational_rank"] = None

    return {
        "n_instances": n_instances,
        "n_runs": len(records),
        "ranking_metric": (
            "composite = 0.55·near_best_rate + 0.20·usable_rate + "
            "0.15·(1−fail_rate) + 0.10·speed_score; lower H(x) is better. "
            "Operational top excludes C1 (exact oracle only on tiny graphs)."
        ),
        "solvers": ranked_rows,
        "top_solver": ranked_rows[0]["solver_id"] if ranked_rows else None,
        "top_operational_solver": operational[0]["solver_id"] if operational else None,
    }


def build_failure_quantum_map(records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Attach observed hurdle counts to the quantum opportunity catalogue."""
    if records is None:
        records = list(_load_json(CLASSICAL_JSON).get("records") or [])
    summary = summarize_hurdles(records)
    counts = summary.get("hurdle_counts") or {}
    q_signals = (_load_json(QUANTUM_JSON) or {}).get("preliminary_advantage_signals") or {}

    # Extra observed signal: metaheuristic timeouts
    tabu_timeouts = sum(
        1
        for r in records
        if r.get("solver_id") == "c7_tabu_search" and r.get("status") == "timeout"
    )
    ga_slow = sum(
        1
        for r in records
        if r.get("solver_id") == "c6_genetic_algorithm"
        and float(r.get("execution_time_sec") or 0) >= 20.0
    )

    observed_extra = {
        "time_budget_metaheuristics": tabu_timeouts + ga_slow,
        "county_scale_decomposition": int(
            sum(1 for inst in summary.get("instances") or [] if inst.get("tier") in {"T5", "T6"})
        ),
    }

    opportunities: List[Dict[str, Any]] = []
    for item in QUANTUM_OPPORTUNITY_CATALOGUE:
        oid = item["id"]
        observed = int(counts.get(oid, 0))
        if oid in observed_extra:
            observed = int(observed_extra[oid])
        opportunities.append(
            {
                **item,
                "observed_instances": observed,
                "priority": (
                    "high"
                    if oid in {"exact_scale", "exact_timeout", "heuristic_quality"} and observed
                    else "medium"
                    if oid in {"classical_ok", "county_scale_decomposition", "time_budget_metaheuristics"}
                    else "low"
                    if oid == "staffing_or_equity"
                    else "medium"
                ),
            }
        )

    # Sort: high priority with observations first, then by observed count
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    opportunities.sort(
        key=lambda o: (
            priority_rank.get(o["priority"], 9),
            -int(o.get("observed_instances") or 0),
            o["id"],
        )
    )

    return {
        "hurdle_summary": {
            "n_instances": summary.get("n_instances"),
            "hurdle_counts": counts,
            "quantum_candidate_count": summary.get("quantum_candidate_count"),
            "quantum_needed_candidate_count": summary.get("quantum_needed_candidate_count"),
            "by_tier": summary.get("by_tier"),
        },
        "quantum_benchmark_signals": q_signals,
        "framing": (
            "Goal is not ‘quantum completely solves CHW deployment.’ "
            "Even when classical succeeds, quantum can add ensemble sampling, "
            "hybrid partition search, and fair NISQ evidence — without overstating advantage."
        ),
        "opportunities": opportunities,
    }


def build_classical_quantum_evaluation(
    classical_path: Optional[Path] = None,
    quantum_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Full dashboard payload: ranking + failure→quantum map + paired snapshot."""
    cpath = classical_path or CLASSICAL_JSON
    qpath = quantum_path or QUANTUM_JSON
    classical = _load_json(cpath)
    quantum = _load_json(qpath)
    records = list(classical.get("records") or [])

    ranking = rank_classical_solvers(records)
    failure_map = build_failure_quantum_map(records)

    qml = quantum.get("qml_vs_classical") or {}
    return {
        "status": "ready" if records else "missing_classical",
        "source": {
            "classical": _rel(Path(cpath)),
            "quantum": _rel(Path(qpath)),
            "classical_profile": classical.get("profile"),
            "quantum_status": quantum.get("status"),
        },
        "headline": {
            "top_classical": ranking.get("top_solver"),
            "top_classical_name": next(
                (s["name"] for s in ranking["solvers"] if s["solver_id"] == ranking.get("top_solver")),
                None,
            ),
            "top_operational": ranking.get("top_operational_solver"),
            "top_operational_name": next(
                (
                    s["name"]
                    for s in ranking["solvers"]
                    if s["solver_id"] == ranking.get("top_operational_solver")
                ),
                None,
            ),
            "qaoa_strictly_better": int(
                (failure_map.get("quantum_benchmark_signals") or {}).get(
                    "qaoa_strictly_better_than_best_classical", 0
                )
            ),
            "quantum_needed_candidates": failure_map["hurdle_summary"].get(
                "quantum_needed_candidate_count", 0
            ),
            "message": (
                "Classical heuristics remain primary. Quantum’s role is hybrid / "
                "additive at failure points and as a fair NISQ comparator — not replacement."
            ),
        },
        "classical_ranking": ranking,
        "failure_to_quantum": failure_map,
        "qml_vs_classical": {
            "qml_beats_classical_by_5pct_rmse": qml.get("qml_beats_classical_by_5pct_rmse"),
            "verdict_note": qml.get("verdict_note"),
        }
        if qml
        else None,
    }
