#!/usr/bin/env python3
"""
Phase 2 classical stress-test runner.

Runs C1–C7 on the T0–T6 instance ladder with shared H(x), writes
data/classical_suite_results.json and scaling / failure plots.

Designed for qBraid Lab free CPU: profile slug `2vCPU_4GB`
  qbraid compute up 2vCPU_4GB

Usage:
  PYTHONPATH=. python scripts/run_classical_suite.py
  PYTHONPATH=. python scripts/run_classical_suite.py --profile smoke
  PYTHONPATH=. python scripts/run_classical_suite.py --profile complete_tiers
  PYTHONPATH=. python scripts/run_classical_suite.py --profile full
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from backend import config
from backend.optimization.classical_suite import get_classical_solver, list_classical_solver_ids
from backend.optimization.hurdles import record_usable, summarize_hurdles
from backend.scenario.ladder import build_ladder_instance, list_counties


def _methods_for_tier(tier: str, all_ids: list[str]) -> list[str]:
    if tier in {"T3", "T4", "T5", "T6"}:
        return [m for m in all_ids if m != "c1_brute_force"]
    return list(all_ids)


def _pick(available: list[str], wanted: tuple[str, ...]) -> list[str]:
    have = {c.upper(): c for c in available}
    out = []
    for name in wanted:
        key = name.upper()
        if key in have:
            out.append(have[key])
    return out


def hackathon_jobs() -> list[dict]:
    """Coverage of every tier, method, and constraint knob without a 12-hour sweep."""
    counties = list_counties()
    small = [c for c in ("LAMU", "ISIOLO", "TAITA TAVETA", "TANA RIVER") if c in counties]
    mid = [c for c in ("SAMBURU", "MANDERA", "GARISSA") if c in counties]
    large = [c for c in ("KILIFI", "TURKANA") if c in counties]
    t0_counties = (small + mid + large)[:3] or counties[:3]
    t1_counties = (small + mid)[:2] or t0_counties[:2]
    t5_county = small[0] if small else counties[0]
    jobs = []
    jobs += [
        {"tier": "T0", "counties": t0_counties, "seeds": [0, 1, 2],
         "constraints": ["loose", "nominal", "tight"], "stages": ["B4"]},
        {"tier": "T1", "counties": t1_counties, "seeds": [0, 1, 2],
         "constraints": ["nominal", "tight"], "stages": ["B4"]},
        {"tier": "T2", "counties": t1_counties[:1], "seeds": [0, 1],
         "constraints": ["nominal"], "stages": ["B4"]},
        {"tier": "T3", "counties": t1_counties[:1], "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"]},
        {"tier": "T4", "counties": t1_counties[:1], "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"]},
        {"tier": "T5", "counties": [t5_county], "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"], "max_variables": 400},
        {"tier": "T6", "counties": [t5_county], "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"], "max_variables": 300},
        {"tier": "T1", "counties": t0_counties[:1], "seeds": [0],
         "constraints": ["nominal"], "stages": ["B0", "B2", "B4"]},
    ]
    return jobs


def smoke_jobs() -> list[dict]:
    counties = list_counties()[:1] or ["TURKANA"]
    return [
        {"tier": "T0", "counties": counties, "seeds": [42],
         "constraints": ["nominal"], "stages": ["B4"]},
        {"tier": "T1", "counties": counties, "seeds": [42],
         "constraints": ["nominal"], "stages": ["B4"]},
    ]


def complete_tiers_jobs() -> list[dict]:
    """
    Fill T2–T6 across landscape-diverse counties.

    WHO capacity is scaled to feasible so solver limits (timeout / scale /
    quality) are not confounded with missing CHW payroll data.
    """
    counties = list_counties()
    core = _pick(
        counties,
        ("LAMU", "KILIFI", "TURKANA", "GARISSA", "TAITA TAVETA", "MARSABIT", "NAROK", "WEST POKOT"),
    ) or counties[:8]
    t5 = _pick(counties, ("LAMU", "KILIFI", "TURKANA", "GARISSA", "MARSABIT", "NAROK")) or core[:6]
    t6 = _pick(counties, ("TURKANA", "MARSABIT", "GARISSA", "KILIFI")) or core[:4]
    tight_probe = core[:3]
    mode = "feasible"
    return [
        {"tier": "T2", "counties": core, "seeds": [0, 1],
         "constraints": ["nominal"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 20.0, "heuristic_budget": 8.0},
        {"tier": "T2", "counties": tight_probe, "seeds": [0],
         "constraints": ["tight"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 20.0, "heuristic_budget": 8.0},
        {"tier": "T3", "counties": core, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 45.0, "heuristic_budget": 15.0},
        {"tier": "T3", "counties": tight_probe, "seeds": [0],
         "constraints": ["tight"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 45.0, "heuristic_budget": 15.0},
        {"tier": "T4", "counties": core, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 45.0, "heuristic_budget": 20.0},
        {"tier": "T5", "counties": t5, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"], "max_variables": 256,
         "who_capacity_mode": mode, "exact_budget": 20.0, "heuristic_budget": 25.0},
        {"tier": "T6", "counties": t6, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"], "max_variables": 196,
         "who_capacity_mode": mode, "exact_budget": 15.0, "heuristic_budget": 25.0},
    ]


def qbraid_free_jobs() -> list[dict]:
    """
    All 14 counties × T0–T6, tuned for qBraid Lab Small (2 vCPU / 4 GB).

    Uses the free CPU-hour pool (`qbraid compute up 2vCPU_4GB`), never a QPU.
    One seed, nominal constraints, WHO-feasible packing so solver limits show.
    """
    counties = list_counties()
    t6 = _pick(counties, ("TURKANA", "MARSABIT", "GARISSA", "KILIFI", "TANA RIVER", "NAROK"))
    mode = "feasible"
    return [
        {"tier": "T0", "counties": counties, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 5.0, "heuristic_budget": 2.0},
        {"tier": "T1", "counties": counties, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 8.0, "heuristic_budget": 3.0},
        {"tier": "T2", "counties": counties, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 12.0, "heuristic_budget": 6.0},
        {"tier": "T3", "counties": counties, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 20.0, "heuristic_budget": 8.0},
        {"tier": "T4", "counties": counties, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"],
         "who_capacity_mode": mode, "exact_budget": 8.0, "heuristic_budget": 8.0},
        {"tier": "T5", "counties": counties, "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"], "max_variables": 144,
         "who_capacity_mode": mode, "exact_budget": 8.0, "heuristic_budget": 8.0},
        {"tier": "T6", "counties": t6 or counties[:4], "seeds": [0],
         "constraints": ["nominal"], "stages": ["B4"], "max_variables": 144,
         "who_capacity_mode": mode, "exact_budget": 8.0, "heuristic_budget": 8.0},
    ]


def full_jobs() -> list[dict]:
    counties = list_counties()
    jobs = hackathon_jobs()
    jobs.append(
        {"tier": "T0", "counties": counties, "seeds": [0, 1, 2, 3, 4],
         "constraints": ["loose", "nominal", "tight"], "stages": ["B4"]},
    )
    jobs.extend(complete_tiers_jobs())
    return jobs


def _budget_for(spec: dict, sid: str) -> float:
    budgets = config.CLASSICAL_TIME_BUDGETS
    default = float(budgets.get(spec["tier"], 10.0))
    exact_b = float(spec.get("exact_budget", default))
    heur_b = float(spec.get("heuristic_budget", default))
    if sid in {"c1_brute_force", "c2_milp"}:
        return exact_b
    if sid == "c3_greedy":
        return min(heur_b, 2.0)
    if sid == "c4_local_search":
        return min(heur_b, 12.0)
    return heur_b


def run_job(spec: dict, methods: list[str] | None = None) -> list[dict]:
    all_ids = methods or list_classical_solver_ids()
    records = []
    who_mode = spec.get("who_capacity_mode", "raw")
    for county in spec["counties"]:
        for seed in spec["seeds"]:
            for cons in spec["constraints"]:
                for stage in spec["stages"]:
                    try:
                        scenario = build_ladder_instance(
                            tier=spec["tier"],
                            county=county,
                            seed=int(seed),
                            constraint_setting=cons,
                            feature_stage=stage,
                            max_variables=spec.get("max_variables"),
                            who_capacity_mode=who_mode,
                        )
                    except Exception as exc:  # noqa: BLE001
                        records.append({
                            "tier": spec["tier"], "county": county, "seed": seed,
                            "constraint_setting": cons, "feature_stage": stage,
                            "who_capacity_mode": who_mode,
                            "status": "error", "error": str(exc),
                        })
                        continue
                    n = scenario.num_variables
                    m_ids = _methods_for_tier(spec["tier"], all_ids)
                    batch = []
                    for sid in m_ids:
                        solver = get_classical_solver(sid)
                        budget = _budget_for(spec, sid)
                        t0 = time.perf_counter()
                        res = solver.solve(scenario, time_budget_sec=budget, seed=int(seed))
                        elapsed = time.perf_counter() - t0
                        rec = {
                            "tier": scenario.tier,
                            "county": scenario.county,
                            "seed": int(seed),
                            "constraint_setting": cons,
                            "feature_stage": stage,
                            "who_capacity_mode": scenario.extra.get("who_capacity_mode", who_mode),
                            "solver_id": sid,
                            "num_facilities": len(scenario.facilities),
                            "num_communities": len(scenario.communities),
                            "num_variables": n,
                            "objective_value": res.objective_value,
                            "status": res.status,
                            "failure_label": res.failure_label,
                            "gini_equity_index": res.gini_equity_index,
                            "theil_index": res.theil_index,
                            "d_p90_km": res.d_p90_km,
                            "who_compliance_pct": res.who_compliance_pct,
                            "population_coverage_pct": res.population_coverage_pct,
                            "total_travel_km": res.total_travel_km,
                            "bottom_quintile_coverage_pct": res.bottom_quintile_coverage_pct,
                            "execution_time_sec": round(elapsed, 4),
                            "who_ratio": scenario.who_ratio,
                            "max_walking_dist_km": scenario.max_walking_dist_km,
                            "equity_target": scenario.equity_target,
                            "time_budget_sec": budget,
                            "scaled_total_chws": scenario.extra.get("scaled_total_chws"),
                            "raw_total_chws": scenario.extra.get("raw_total_chws"),
                        }
                        batch.append(rec)
                    usable = [r for r in batch if record_usable(r)]
                    best_h = min((r["objective_value"] for r in usable), default=None)
                    for rec in batch:
                        h = rec["objective_value"]
                        rec["gap_to_best_classical"] = (
                            None if h is None or best_h in (None, 0) or not record_usable(rec)
                            else round((h - best_h) / max(abs(best_h), 1e-9), 6)
                        )
                        gap = rec["gap_to_best_classical"]
                        gini_ok = rec.get("gini_equity_index") is not None and rec["gini_equity_index"] <= rec.get("equity_target", 1.0)
                        who_ok = rec.get("who_compliance_pct") is not None and rec["who_compliance_pct"] >= 80.0
                        if rec.get("failure_label") is None and gap is not None and gap > 0.10 and not (gini_ok and who_ok):
                            rec["failure_label"] = "F-QUALITY"
                    records.extend(batch)
                    print(
                        f"  {scenario.tier} {scenario.county:22s} seed={seed} "
                        f"{cons:8s} {stage} N={n:4d} methods={len(m_ids)} "
                        f"who={who_mode}",
                        flush=True,
                    )
    return records


def merge_records(old: list[dict], new: list[dict]) -> list[dict]:
    def key(r: dict) -> tuple:
        return (
            r.get("tier"), r.get("county"), r.get("seed"),
            r.get("constraint_setting"), r.get("feature_stage"),
            r.get("who_capacity_mode", "raw"), r.get("solver_id"),
        )
    new_keys = {key(r) for r in new if r.get("solver_id")}
    kept = [r for r in old if key(r) not in new_keys]
    return kept + new


def write_plots(records: list[dict], docs: Path) -> list[str]:
    docs.mkdir(parents=True, exist_ok=True)
    written = []
    rows = [r for r in records if r.get("objective_value") is not None and record_usable(r)]
    if not rows:
        return written

    fig, ax = plt.subplots(figsize=(8, 5))
    for sid in sorted({r["solver_id"] for r in rows if "solver_id" in r}):
        sub = [r for r in rows if r.get("solver_id") == sid]
        ax.scatter(
            [r["num_variables"] for r in sub],
            [r["execution_time_sec"] for r in sub],
            s=18, alpha=0.7, label=sid,
        )
    ax.set_xlabel("N = F × C")
    ax.set_ylabel("Wall-clock (s)")
    ax.set_title("Classical suite scaling (shared H)")
    ax.legend(fontsize=7, loc="upper left")
    ax.set_yscale("log")
    p = docs / "benchmark_classical_scaling.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    written.append(str(p))

    fig, ax = plt.subplots(figsize=(8, 5))
    for sid in sorted({r["solver_id"] for r in rows if "solver_id" in r}):
        sub = [r for r in rows if r.get("solver_id") == sid]
        ax.scatter(
            [r["num_variables"] for r in sub],
            [r["objective_value"] for r in sub],
            s=18, alpha=0.7, label=sid,
        )
    ax.set_xlabel("N = F × C")
    ax.set_ylabel("H(x) (lower better)")
    ax.set_title("Solution quality vs instance size")
    ax.set_yscale("log")
    ax.legend(fontsize=7)
    p = docs / "benchmark_classical_quality.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    written.append(str(p))

    methods = sorted({r["solver_id"] for r in records if "solver_id" in r})
    tiers = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]
    grid = np.zeros((len(methods), len(tiers)))
    for i, m in enumerate(methods):
        for j, t in enumerate(tiers):
            sub = [r for r in records if r.get("solver_id") == m and r.get("tier") == t]
            if not sub:
                grid[i, j] = np.nan
                continue
            score = 0.0
            for r in sub:
                st = r.get("status") or ""
                if st == "optimal":
                    score += 0
                elif st == "feasible":
                    score += 1
                elif st == "timeout":
                    score += 2
                elif st in {"bottleneck", "infeasible", "error"}:
                    score += 3
            grid[i, j] = score / len(sub)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    im = ax.imshow(grid, cmap="YlOrRd", vmin=0, vmax=3)
    ax.set_xticks(range(len(tiers)), tiers)
    ax.set_yticks(range(len(methods)), methods)
    ax.set_title("Failure heatmap (0=optimal … 3=scale/error)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    p = docs / "benchmark_classical_failure_heatmap.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    written.append(str(p))
    return written


def write_hurdle_plot(summary: dict, docs: Path) -> str | None:
    instances = summary.get("instances") or []
    if not instances:
        return None
    labels = [
        "classical_ok", "exact_timeout", "exact_scale",
        "heuristic_quality", "equity_geography", "staffing_or_equity", "all_failed",
    ]
    tiers = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]
    grid = np.zeros((len(labels), len(tiers)))
    for inst in instances:
        if inst.get("hurdle") in labels and inst.get("tier") in tiers:
            grid[labels.index(inst["hurdle"]), tiers.index(inst["tier"])] += 1
    fig, ax = plt.subplots(figsize=(8, 4.8))
    im = ax.imshow(grid, cmap="Blues")
    ax.set_xticks(range(len(tiers)), tiers)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_title("Classical hurdle counts by tier")
    for i in range(len(labels)):
        for j in range(len(tiers)):
            val = int(grid[i, j])
            if val:
                ax.text(j, i, str(val), ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046)
    p = docs / "benchmark_classical_hurdle_heatmap.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    return str(p)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        choices=["smoke", "hackathon", "complete_tiers", "qbraid_free", "full"],
        default="hackathon",
    )
    parser.add_argument("--methods", default="", help="comma-separated solver ids")
    parser.add_argument("--merge", action="store_true", help="merge into existing results JSON")
    parser.add_argument(
        "--out",
        default=str(ROOT / "data" / "classical_suite_results.json"),
    )
    args = parser.parse_args()
    include = [m.strip() for m in args.methods.split(",") if m.strip()] or None
    specs = {
        "smoke": smoke_jobs,
        "hackathon": hackathon_jobs,
        "complete_tiers": complete_tiers_jobs,
        "qbraid_free": qbraid_free_jobs,
        "full": full_jobs,
    }[args.profile]()

    print("=" * 72, flush=True)
    print("AfyaDeploy — Phase 2 classical suite", flush=True)
    print("qBraid Lab profile:", config.QBRAID_LAB_PROFILE_SLUG, f"({config.QBRAID_LAB_VCPUS} vCPU / {config.QBRAID_LAB_RAM_GB} GB)")
    print("Classical target:", config.CLASSICAL_EXECUTION_TARGET)
    print("Quantum free simulator:", config.QBRAID_FREE_SIMULATOR)
    print("Profile:", args.profile)
    print("=" * 72)

    t0 = time.perf_counter()
    records: list[dict] = []
    for spec in specs:
        records.extend(run_job(spec, include))
    elapsed = time.perf_counter() - t0

    out = Path(args.out)
    merge = args.merge or args.profile == "complete_tiers"
    if merge and out.exists():
        try:
            prev = json.loads(out.read_text())
            old_recs = prev.get("records", [])
            records = merge_records(old_recs, records)
            print(f"Merged with {len(old_recs)} existing records → {len(records)} total", flush=True)
        except Exception as exc:  # noqa: BLE001
            print("Merge skipped:", exc, flush=True)

    docs = ROOT / "docs"
    plots = write_plots(records, docs)
    hurdles = summarize_hurdles(records)
    hurdle_plot = write_hurdle_plot(hurdles, docs)
    if hurdle_plot:
        plots.append(hurdle_plot)

    payload = {
        "profile": args.profile,
        "execution_target": config.CLASSICAL_EXECUTION_TARGET,
        "qbraid_lab_profile_slug": config.QBRAID_LAB_PROFILE_SLUG,
        "qbraid_free_simulator": config.QBRAID_FREE_SIMULATOR,
        "elapsed_sec": round(elapsed, 2),
        "n_runs": len(records),
        "plots": plots,
        "hurdle_summary": {
            "n_instances": hurdles["n_instances"],
            "hurdle_counts": hurdles["hurdle_counts"],
            "by_tier": hurdles["by_tier"],
            "by_who_capacity_mode": hurdles.get("by_who_capacity_mode"),
            "quantum_candidate_count": hurdles["quantum_candidate_count"],
            "quantum_needed_candidate_count": hurdles["quantum_needed_candidate_count"],
            "interpretation": hurdles["interpretation"],
        },
        "records": records,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))

    hurdle_path = ROOT / "data" / "classical_hurdles.json"
    slim = dict(hurdles)
    # Keep candidates but drop bulky full instance dump duplication of records
    hurdle_path.write_text(json.dumps(slim, indent=2))

    print(f"\nRuns: {len(records)}  elapsed={elapsed:.1f}s")
    print("Hurdles:", hurdles["hurdle_counts"])
    print("Quantum-comparable candidates:", hurdles["quantum_candidate_count"])
    print("Quantum-needed (T3–T4 heuristic quality):", hurdles["quantum_needed_candidate_count"])
    print("Wrote", out)
    print("Wrote", hurdle_path)
    for p in plots:
        print("Wrote", p)


if __name__ == "__main__":
    main()
