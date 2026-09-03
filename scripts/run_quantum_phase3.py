#!/usr/bin/env python3
"""
Phase 3 — Quantum comparator (secondary to classical C1–C7).

Runs QAOA on the same shared H(x) / ladder instances used in Phase 2,
submits circuits to the free qBraid simulator via QBRAID_API_KEY, waits for
measurement counts, and writes:

  data/qbraid_submitted_jobs.json
  data/quantum_benchmark_results.json

Valid quantum tiers: T0–T2 on free sim (≤30 qubits). T3–T4 are recorded as
F-SCALE / needs QPU or decomposition (sim cap).

Usage:
  PYTHONPATH=. .venv/bin/python scripts/run_quantum_phase3.py
  PYTHONPATH=. .venv/bin/python scripts/run_quantum_phase3.py --profile smoke
  PYTHONPATH=. .venv/bin/python scripts/run_quantum_phase3.py --backend qbraid:qbraid:sim:qir-sv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from backend import config
from backend.ai.demand_qml import QMLDemandEstimator
from backend.judging import attach_judging_to_report
from backend.optimization.classical_suite import get_classical_solver
from backend.optimization.quantum_solver import QAOAQuantumSolver
from backend.scenario.ladder import build_ladder_instance, list_counties
from backend.scenario.models import CHWDeploymentScenario

JOBS_JSON = ROOT / "data" / "qbraid_submitted_jobs.json"
OUTPUT_JSON = ROOT / "data" / "quantum_benchmark_results.json"
CLASSICAL_JSON = ROOT / "data" / "classical_suite_results.json"
HURDLES_JSON = ROOT / "data" / "classical_hurdles.json"


def _log(msg: str = "") -> None:
    print(msg, flush=True)


def _jobs_from_classical_hurdles() -> List[Dict[str, Any]]:
    """
    Prefer instances where classical already hit a quantum-candidate bottleneck.
    Supports both summarize_hurdles() flat JSON and nested feasible_mode payloads.
    """
    if not HURDLES_JSON.exists():
        return []
    try:
        payload = json.loads(HURDLES_JSON.read_text())
    except Exception:
        return []

    instances: List[Dict[str, Any]] = []
    # Flat summarize_hurdles output
    if isinstance(payload.get("instances"), list):
        instances.extend(payload["instances"])
    if isinstance(payload.get("quantum_candidates"), list):
        instances.extend(payload["quantum_candidates"])
    # Nested complete_tiers / feasible_mode shape
    for nest_key in ("feasible_mode", "raw_mode_legacy", "classical_hurdle_for_quantum"):
        nest = payload.get(nest_key)
        if not isinstance(nest, dict):
            continue
        if isinstance(nest.get("quantum_candidates"), list):
            instances.extend(nest["quantum_candidates"])
        if isinstance(nest.get("instances"), list):
            instances.extend(nest["instances"])

    jobs: List[Dict[str, Any]] = []
    seen = set()
    for inst in instances:
        if not (inst.get("quantum_candidate") or inst.get("quantum_needed_candidate")):
            continue
        tier = str(inst.get("tier") or "").upper()
        county = str(inst.get("county") or "").upper()
        if not tier or not county:
            continue
        seed = int(inst.get("seed") or 0)
        constraint = str(inst.get("constraint_setting") or "nominal").lower()
        stage = str(inst.get("feature_stage") or "B4").upper()
        key = (tier, county, seed, constraint, stage)
        if key in seen:
            continue
        seen.add(key)
        jobs.append(
            {
                "tier": tier,
                "county": county,
                "seed": seed,
                "constraint": constraint,
                "stage": stage,
                "hurdle": inst.get("hurdle"),
                "hurdle_note": inst.get("note"),
                "quantum_needed": bool(inst.get("quantum_needed_candidate")),
            }
        )
    return jobs


def phase3_jobs(profile: str = "hackathon") -> List[Dict[str, Any]]:
    """
    Prefer classical-hurdle quantum candidates (classical first, then quantum).
    Fall back to a compact T0–T2 matrix only if hurdles file is missing/empty.
    """
    from_hurdles = _jobs_from_classical_hurdles()
    if from_hurdles:
        if profile == "smoke":
            return from_hurdles[:2]
        # Prefer NISQ-sized candidates; keep a couple of larger probes if present
        small = [j for j in from_hurdles if j["tier"] in {"T0", "T1", "T2"}]
        large = [j for j in from_hurdles if j["tier"] in {"T3", "T4"}]
        jobs = small[:8] + large[:2]
        if jobs:
            _log(
                f"Using {len(jobs)} quantum jobs gated on classical hurdles "
                f"({len(small)} T0–T2, {len(large)} T3–T4 candidates in file)."
            )
            for j in jobs:
                _log(
                    f"  · {j['tier']} {j['county']} seed={j['seed']} "
                    f"hurdle={j.get('hurdle')} needed={j.get('quantum_needed')}"
                )
            return jobs

    _log(
        "classical_hurdles.json missing or has no quantum_candidate rows — "
        "falling back to fixed smoke/hackathon matrix."
    )
    counties = list_counties()
    core = [c for c in ("LAMU", "GARISSA", "KILIFI", "TURKANA") if c in counties] or counties[:4]
    if profile == "smoke":
        return [
            {"tier": "T0", "county": core[0], "seed": 0, "constraint": "nominal", "stage": "B4"},
            {"tier": "T1", "county": core[0], "seed": 0, "constraint": "nominal", "stage": "B4"},
        ]
    jobs: List[Dict[str, Any]] = []
    for county in core[:3]:
        jobs.append({"tier": "T0", "county": county, "seed": 0, "constraint": "nominal", "stage": "B4"})
    for county in core[:2]:
        jobs.append({"tier": "T1", "county": county, "seed": 0, "constraint": "nominal", "stage": "B4"})
        jobs.append({"tier": "T2", "county": county, "seed": 0, "constraint": "nominal", "stage": "B4"})
    jobs.append({"tier": "T3", "county": core[0], "seed": 0, "constraint": "nominal", "stage": "B4"})
    jobs.append({"tier": "T4", "county": core[0], "seed": 0, "constraint": "nominal", "stage": "B4"})
    return jobs


def _save_partial(
    submitted_jobs: List[Dict[str, Any]],
    qaoa_records: List[Dict[str, Any]],
    backend: str,
    shots: int,
) -> None:
    JOBS_JSON.write_text(json.dumps({"jobs": submitted_jobs, "backend": backend, "shots": shots}, indent=2))
    OUTPUT_JSON.write_text(
        json.dumps(
            {
                "phase": 3,
                "status": "in_progress",
                "backend": backend,
                "shots": shots,
                "n_qaoa_runs": len(qaoa_records),
                "records": qaoa_records,
            },
            indent=2,
        )
    )


def _load_classical_best() -> Dict[Tuple, Dict[str, Any]]:
    """
    Index best classical among C1–C7 by
    (tier, county, seed, constraint, stage, who_capacity_mode).
    Prefer feasible-mode rows so comparisons match Phase 3 packing.
    """
    if not CLASSICAL_JSON.exists():
        return {}
    payload = json.loads(CLASSICAL_JSON.read_text())
    records = payload.get("records") or []
    best: Dict[Tuple, Dict[str, Any]] = {}
    for rec in records:
        solver = str(rec.get("solver_id", ""))
        if not solver.startswith("c"):
            continue
        mode = str(rec.get("who_capacity_mode") or "raw").lower()
        key = (
            str(rec.get("tier", "")).upper(),
            str(rec.get("county", "")).upper(),
            int(rec.get("seed", 0)),
            str(rec.get("constraint_setting", "")).lower(),
            str(rec.get("feature_stage", "")).upper(),
            mode,
        )
        obj = rec.get("objective_value")
        if obj is None:
            continue
        prev = best.get(key)
        if prev is None or float(obj) < float(prev["objective_value"]):
            best[key] = {
                "objective_value": float(obj),
                "solver_id": solver,
                "gini_equity_index": rec.get("gini_equity_index"),
                "who_compliance_pct": rec.get("who_compliance_pct"),
                "population_coverage_pct": rec.get("population_coverage_pct"),
                "total_travel_km": rec.get("total_travel_km"),
                "execution_time_sec": rec.get("execution_time_sec"),
                "status": rec.get("status"),
                "who_capacity_mode": mode,
                "source": "classical_suite_results",
            }
    return best


def _same_instance_classical_best(
    scenario: CHWDeploymentScenario,
    *,
    time_budget_sec: float = 8.0,
) -> Dict[str, Any]:
    """
    Run a fast classical panel on the exact same scenario QAOA just saw.
    This is the fair comparator when Phase 2 JSON used a different WHO mode.
    """
    method_ids = [
        "c3_greedy",
        "c4_local_search",
        "c5_simulated_annealing",
        "c2_milp",
    ]
    if scenario.num_variables <= 12:
        method_ids = ["c1_brute_force"] + method_ids

    best: Optional[Dict[str, Any]] = None
    all_runs = []
    for mid in method_ids:
        try:
            solver = get_classical_solver(mid)
            res = solver.solve(scenario, time_budget_sec=time_budget_sec, seed=scenario.seed or 0)
        except Exception as exc:
            all_runs.append({"solver_id": mid, "status": "error", "error": str(exc)})
            continue
        row = {
            "solver_id": mid,
            "objective_value": res.objective_value,
            "gini_equity_index": res.gini_equity_index,
            "who_compliance_pct": res.who_compliance_pct,
            "population_coverage_pct": res.population_coverage_pct,
            "total_travel_km": res.total_travel_km,
            "execution_time_sec": res.execution_time_sec,
            "status": res.status,
            "who_capacity_mode": "feasible",
            "source": "same_instance",
        }
        all_runs.append(row)
        if res.objective_value is None:
            continue
        if best is None or float(res.objective_value) < float(best["objective_value"]):
            best = row
    if best is None:
        return {"status": "error", "all_runs": all_runs, "source": "same_instance"}
    best = dict(best)
    best["all_runs"] = all_runs
    return best

def _run_qml_vs_classical() -> Dict[str, Any]:
    """Demand-track comparator: QML VQC vs RF / XGB / Ridge on held-out rows."""
    import pandas as pd
    from backend.geo.chw_facilities import haversine_distance_km

    csv_path = ROOT / "data" / "unified_chw_dataset.csv"
    df = pd.read_csv(csv_path)
    df = df[df["lat"].notna() & df["lon"].notna()].copy()
    hubs = df[df["keph_level"].isin(["Level 4", "Level 5", "Level 6"])].copy()
    min_distances = []
    for _, row in df.iterrows():
        c_hubs = hubs[hubs["county"] == row["county"]]
        if len(c_hubs) == 0:
            c_hubs = hubs
        dists = [
            haversine_distance_km(row["lat"], row["lon"], h["lat"], h["lon"])
            for _, h in c_hubs.iterrows()
        ]
        min_distances.append(min(dists) if dists else 5.0)

    max_dist = max(min_distances) or 1.0
    vulnerability = df["vulnerability_score"].astype(float).values
    dist_norm = np.clip(np.array(min_distances) / max_dist, 0.0, 1.0)
    gap_ratio = (
        np.clip(
            (df["ward_population"].astype(float).values / 1000.0)
            / np.maximum(df["available_chws"].astype(float).values, 1.0),
            0.0,
            5.0,
        )
        / 5.0
    )
    X = np.column_stack([vulnerability, dist_norm, gap_ratio])
    rng = np.random.default_rng(42)
    y = np.clip(
        0.40 * vulnerability + 0.35 * dist_norm + 0.25 * gap_ratio + rng.normal(0, 0.02, len(df)),
        0.05,
        1.0,
    )
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    qml = QMLDemandEstimator(num_features=3)
    t0 = time.time()
    qml.train_on_historical_data(X_train, y_train, epochs=20, learning_rate=0.04)
    qml_fit_ms = round((time.time() - t0) * 1000.0, 2)
    qml_preds = [
        qml.estimate_community_demand(float(x[0]), float(x[1]) * 30.0, float(x[2]))["qml_demand_score"]
        for x in X_test
    ]

    # Fresh classical models on the same 3 features / target (fair held-out compare)
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge

    rf = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
    ridge = Ridge(alpha=1.0)
    rf.fit(X_train, y_train)
    ridge.fit(X_train, y_train)
    xgb_preds = None
    try:
        from xgboost import XGBRegressor

        xgb = XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
        xgb.fit(X_train, y_train)
        xgb_preds = xgb.predict(X_test)
    except Exception:
        xgb_preds = None

    def _metrics(preds):
        return {
            "mse": round(float(mean_squared_error(y_test, preds)), 6),
            "rmse": round(float(np.sqrt(mean_squared_error(y_test, preds))), 6),
            "mae": round(float(mean_absolute_error(y_test, preds)), 6),
            "r2": round(float(r2_score(y_test, preds)), 6),
        }

    out: Dict[str, Any] = {
        "qml_vqc": {
            **_metrics(qml_preds),
            "fit_time_ms": qml_fit_ms,
            "model": "3-qubit ZZFeatureMap VQC",
        },
        "random_forest": _metrics(rf.predict(X_test)),
        "ridge": _metrics(ridge.predict(X_test)),
    }
    if xgb_preds is not None:
        out["xgboost"] = _metrics(xgb_preds)

    qml_rmse = out["qml_vqc"]["rmse"]
    best_classical_rmse = min(
        m["rmse"] for k, m in out.items() if k != "qml_vqc" and "rmse" in m
    )
    rel = (best_classical_rmse - qml_rmse) / max(best_classical_rmse, 1e-9)
    out["verdict_note"] = (
        f"QML RMSE relative improvement vs best classical = {rel*100:.1f}% "
        f"(need >5% for meaningful QML edge; negative means classical better)."
    )
    out["qml_beats_classical_by_5pct_rmse"] = bool(rel > 0.05)
    return out


def run_phase3(profile: str, backend: str, shots: int) -> Dict[str, Any]:
    _log("═" * 70)
    _log("  AfyaDeploy — Phase 3 Quantum Comparator (qBraid)")
    _log(f"  Backend: {backend}")
    _log(f"  Shots:   {shots}")
    _log(f"  Profile: {profile}")
    _log(
        f"  Lab:     {config.QBRAID_LAB_PROFILE_SLUG} "
        f"({config.QBRAID_LAB_VCPUS} vCPU / {config.QBRAID_LAB_RAM_GB} GB) "
        f"Aer={config.QAOA_USE_LOCAL_AER}"
    )
    _log("═" * 70)

    api_key = (config.QBRAID_API_KEY or os.getenv("QBRAID_API_KEY", "")).strip()
    if not api_key:
        _log("ERROR: QBRAID_API_KEY not set in .env — cannot submit platform jobs.")
        sys.exit(1)
    _log(f"Authenticated with qBraid (key length {len(api_key)})")

    classical_best = _load_classical_best()
    _log(f"Loaded {len(classical_best)} best-classical instance keys from Phase 2 results.")

    solver = QAOAQuantumSolver(
        backend_name=backend,
        shots=shots,
        wait_timeout_sec=float(getattr(config, "QAOA_WAIT_TIMEOUT_SEC", 600.0)),
    )
    jobs_spec = phase3_jobs(profile)
    qaoa_records: List[Dict[str, Any]] = []
    submitted_jobs: List[Dict[str, Any]] = []
    t_wall0 = time.time()

    for i, spec in enumerate(jobs_spec, 1):
        tier = spec["tier"]
        county = spec["county"]
        seed = int(spec["seed"])
        constraint = spec["constraint"]
        stage = spec["stage"]
        _log(f"\n[{i}/{len(jobs_spec)}] {tier} · {county} · seed={seed} · {constraint}/{stage}")
        if spec.get("hurdle"):
            _log(f"    Classical hurdle: {spec.get('hurdle')} — {spec.get('hurdle_note') or ''}")

        scenario = build_ladder_instance(
            tier=tier,
            county=county,
            seed=seed,
            constraint_setting=constraint,
            feature_stage=stage,
            who_capacity_mode="feasible",
        )
        n_vars = scenario.num_variables
        _log(f"    N={n_vars} (F={len(scenario.facilities)} × C={len(scenario.communities)})")

        result = solver.solve(scenario)
        job_meta = solver.last_job or {}
        _log(f"    qBraid status={job_meta.get('status')} job={result.qbraid_job_id}")

        # Fair classical baseline on the IDENTICAL instance (shared H / WHO packing)
        classical = _same_instance_classical_best(
            scenario,
            time_budget_sec=5.0 if scenario.num_variables <= 12 else 10.0,
        )
        # Optional archive match (feasible mode only) for cross-check
        key = (
            tier.upper(),
            county.upper(),
            seed,
            constraint.lower(),
            stage.upper(),
            "feasible",
        )
        archived = classical_best.get(key)
        if archived and (
            classical.get("objective_value") is None
            or float(archived["objective_value"]) < float(classical["objective_value"])
        ):
            classical = {**archived, "all_runs": classical.get("all_runs", [])}

        q_obj = result.objective_value
        c_obj = classical.get("objective_value") if classical else None
        gap = None
        beats_classical = None
        if c_obj is not None and q_obj is not None:
            gap = (float(q_obj) - float(c_obj)) / max(abs(float(c_obj)), 1e-9)
            beats_classical = float(q_obj) < float(c_obj) - 1e-6

        record = {
            "tier": tier,
            "county": county,
            "seed": seed,
            "constraint_setting": constraint,
            "feature_stage": stage,
            "who_capacity_mode": "feasible",
            "num_facilities": len(scenario.facilities),
            "num_communities": len(scenario.communities),
            "num_variables": n_vars,
            "solver_id": "qaoa_qbraid",
            "backend": backend,
            "shots": shots,
            "qbraid_job_id": result.qbraid_job_id,
            "qbraid_status": job_meta.get("status"),
            "used_platform_counts": job_meta.get("used_platform_counts", False),
            "objective_value": q_obj,
            "status": result.status,
            "failure_label": result.failure_label,
            "gini_equity_index": result.gini_equity_index,
            "who_compliance_pct": result.who_compliance_pct,
            "population_coverage_pct": result.population_coverage_pct,
            "total_travel_km": result.total_travel_km,
            "d_p90_km": result.d_p90_km,
            "execution_time_sec": result.execution_time_sec,
            "bitstring": result.bitstring,
            "extra_metrics": result.extra_metrics,
            "best_classical": classical,
            "gap_to_best_classical": gap,
            "beats_best_classical": beats_classical,
        }
        qaoa_records.append(record)
        submitted_jobs.append(
            {
                "cluster": scenario.name,
                "tier": tier,
                "county": county,
                "seed": seed,
                "constraint_setting": constraint,
                "feature_stage": stage,
                "n_qubits": n_vars,
                "backend": backend,
                "job_id": result.qbraid_job_id,
                "shots": shots,
                "status": job_meta.get("status") or result.status,
                "used_platform_counts": job_meta.get("used_platform_counts", False),
                "top5_counts": job_meta.get("top5_counts"),
                "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "objective_value": q_obj,
                "error": job_meta.get("error_message"),
            }
        )
        tag = "PLATFORM" if job_meta.get("used_platform_counts") else (job_meta.get("status") or result.status)
        _log(
            f"    → {tag} | H={q_obj} | Gini={result.gini_equity_index} | "
            f"beats_classical={beats_classical}"
        )
        _save_partial(submitted_jobs, qaoa_records, backend, shots)

    _log("\n[QML] Training demand-track comparator …")
    qml_block = _run_qml_vs_classical()
    _log(f"    → {qml_block.get('verdict_note')}")

    # Summary for Phase 4 rubric
    comparable = [r for r in qaoa_records if r.get("best_classical") and r.get("objective_value") is not None
                  and r.get("status") != "bottleneck"]
    n_beat = sum(1 for r in comparable if r.get("beats_best_classical"))
    n_platform = sum(1 for r in qaoa_records if r.get("used_platform_counts"))
    preliminary = {
        "comparable_instances": len(comparable),
        "qaoa_strictly_better_than_best_classical": n_beat,
        "platform_jobs_with_counts": n_platform,
        "skipped_scale": sum(1 for r in qaoa_records if r.get("status") == "bottleneck"),
        "hint": (
            "Verdict A likely if QAOA never beats best classical on quality@time. "
            "Apply full §6 rubric in Phase 4 after reviewing gaps."
        ),
    }

    payload: Dict[str, Any] = {
        "phase": 3,
        "profile": profile,
        "status": "complete",
        "backend": backend,
        "shots": shots,
        "execution_target": "qbraid_platform",
        "qbraid_free_simulator": config.QBRAID_FREE_SIMULATOR,
        "qbraid_lab_profile_slug": config.QBRAID_LAB_PROFILE_SLUG,
        "qbraid_lab_vcpus": config.QBRAID_LAB_VCPUS,
        "qbraid_lab_ram_gb": config.QBRAID_LAB_RAM_GB,
        "qaoa_use_local_aer": config.QAOA_USE_LOCAL_AER,
        "elapsed_sec": round(time.time() - t_wall0, 2),
        "n_qaoa_runs": len(qaoa_records),
        "qml_vs_classical": qml_block,
        "preliminary_advantage_signals": preliminary,
        "records": qaoa_records,
        "honest_framing": (
            "QAOA is a secondary NISQ comparator on shared H(x). "
            "Beating greedy alone is not quantum advantage; primary rivals are best of C2–C7."
        ),
    }
    payload = attach_judging_to_report(
        payload,
        {
            "counties_covered": len({r["county"] for r in qaoa_records}),
            "scenarios_run": len(qaoa_records),
            "classical_methods_run": 7,
            "has_shared_objective": True,
            "has_multi_metric_equity": True,
            "classical_bottleneck_detected": any(r.get("status") == "bottleneck" for r in qaoa_records),
            "quantum_ran": n_platform > 0,
            "quantum_claimed_advantage": False,
            "quantum_beats_best_classical": n_beat > 0 and n_beat >= max(1, len(comparable) // 2),
            "used_free_simulator_or_local": "sim" in backend.lower(),
            "sdg3_metrics_present": True,
        },
    )

    JOBS_JSON.write_text(json.dumps({"jobs": submitted_jobs, "backend": backend, "shots": shots}, indent=2))
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2))
    _log(f"\nSaved job ledger → {JOBS_JSON}")
    _log(f"Saved benchmark  → {OUTPUT_JSON}")
    _log(
        f"Summary: {n_platform} platform jobs with counts | "
        f"{n_beat}/{len(comparable)} beat best classical | "
        f"{preliminary['skipped_scale']} scale-skipped"
    )
    _log("═" * 70)
    return payload


def main():
    parser = argparse.ArgumentParser(description="AfyaDeploy Phase 3 — qBraid quantum comparator")
    parser.add_argument("--profile", choices=["hackathon", "smoke"], default="hackathon")
    parser.add_argument(
        "--backend",
        default=config.QBRAID_DEFAULT_DEVICE or config.QBRAID_FREE_SIMULATOR,
        help="qBraid device id (default: free simulator from .env)",
    )
    parser.add_argument("--shots", type=int, default=config.QAOA_SHOTS)
    args = parser.parse_args()
    run_phase3(args.profile, args.backend, args.shots)


if __name__ == "__main__":
    main()
