"""
FastAPI Route Handlers for AfyaDeploy Quantum API.
Exposes endpoints for rural Kenya scenarios, QML demand estimation & classical ML benchmarks, qBraid job status syncing, and solver benchmarks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.scenario.loader import list_available_scenarios
from backend.scenario.builder import get_scenario_by_name, build_custom_chw_scenario
from backend.ai.demand_qml import default_qml_estimator
from backend.ai.classical_demand import default_classical_estimator
from backend.ai.recommender import generate_chw_recommendation
from backend import config
from backend.optimization.compare import (
    compare_chw_solvers,
    compare_classical_suite,
    compare_classical_suite_all_scenarios,
)
from backend.optimization.benchmark_store import (
    dataset_inventory,
    load_verdict_summary,
    objective_h_comparison,
    paired_comparison_rows,
    shared_instance_catalogue,
)
from backend.optimization.classical_evaluation import build_classical_quantum_evaluation
from backend.optimization.classical_suite import get_classical_solver, list_classical_solver_ids
from backend.optimization.quantum_solver import QAOAQuantumSolver
from backend.judging import judging_scorecard_template
from backend.qbraid_client.manager import qbraid_manager
from backend.scenario.constraints import list_constraint_presets, get_constraint_preset
from backend.scenario.features import (
    default_enabled_factors,
    list_demand_factors,
    list_feature_stages,
)
from backend.scenario.ladder import build_ladder_instance, ladder_catalog
from backend.optimization.hurdles import classify_instance
from pathlib import Path
import json

router = APIRouter(prefix="/api")


class QMLDemandRequest(BaseModel):
    vulnerability_score: float = 0.8
    distance_km: float = 8.5
    disease_risk: float = 0.65


class SolveRequest(BaseModel):
    scenario_name: str
    backend_name: str = config.QBRAID_FREE_SIMULATOR
    run_quantum: bool = True
    classical_budget_sec: float = 12.0
    seed: int = 42
    classical_include: Optional[List[str]] = None


class ClassicalSolveRequest(BaseModel):
    scenario_name: str
    solver_id: str = "c3_greedy"
    time_budget_sec: float = 15.0
    seed: int = 42


class ClassicalSuiteRequest(BaseModel):
    scenario_name: str
    time_budget_sec: float = 10.0
    seed: int = 42
    include: Optional[List[str]] = None


class ClassicalAllCountiesRequest(BaseModel):
    time_budget_sec: float = 4.0
    seed: int = 42
    include: Optional[List[str]] = None


@router.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "app": "AfyaDeploy — Classical-first CHW deployment (Kenya)",
        "qbraid_connected": qbraid_manager.is_connected(),
        "classical_execution_target": config.CLASSICAL_EXECUTION_TARGET,
        "qbraid_lab_instance": config.QBRAID_LAB_INSTANCE,
        "qbraid_lab_vcpus": config.QBRAID_LAB_VCPUS,
        "qbraid_lab_ram_gb": config.QBRAID_LAB_RAM_GB,
        "quantum_default_device": config.QBRAID_DEFAULT_DEVICE,
        "quantum_free_simulator": config.QBRAID_FREE_SIMULATOR,
        "target_counties_count": 14,
        "classical_methods": list_classical_solver_ids(),
    }


@router.get("/judging/criteria")
def get_judging_criteria() -> Dict[str, Any]:
    """Q-SOLVE Kenya 2026 judging scorecard context (JC1–JC7)."""
    return judging_scorecard_template()


@router.get("/scenarios")
def get_scenarios() -> List[Dict[str, Any]]:
    return list_available_scenarios()


@router.get("/scenario/{name}")
def get_scenario(name: str) -> Dict[str, Any]:
    s = get_scenario_by_name(name)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scenario '{name}' not found.")
    return s.model_dump()


@router.post("/qml/predict_demand")
def predict_qml_demand(req: QMLDemandRequest) -> Dict[str, Any]:
    return default_qml_estimator.estimate_community_demand(
        vulnerability_score=req.vulnerability_score,
        distance_km=req.distance_km,
        disease_risk=req.disease_risk,
    )


@router.post("/qml/compare_demand")
def compare_qml_classical_demand(req: QMLDemandRequest) -> Dict[str, Any]:
    """Compare Quantum Machine Learning (QML) vs Classical Random Forest demand predictions."""
    qml_res = default_qml_estimator.estimate_community_demand(
        vulnerability_score=req.vulnerability_score,
        distance_km=req.distance_km,
        disease_risk=req.disease_risk,
    )
    comp_res = default_classical_estimator.compare_with_qml(
        vulnerability_score=req.vulnerability_score,
        distance_km=req.distance_km,
        disease_risk=req.disease_risk,
        qml_score=qml_res["demand_score"],
    )
    comp_res["estimated_weekly_patients"] = qml_res["estimated_weekly_patients"]
    return comp_res


@router.post("/solve/compare")
def solve_compare(req: SolveRequest) -> Dict[str, Any]:
    """Classical-first fair compare: C1–C7 ranked, optional QAOA vs best classical."""
    s = get_scenario_by_name(req.scenario_name)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scenario '{req.scenario_name}' not found.")
    res = compare_chw_solvers(
        s,
        backend_name=req.backend_name,
        classical_include=req.classical_include,
        classical_budget_sec=req.classical_budget_sec,
        seed=req.seed,
        run_quantum=req.run_quantum,
    )
    best = res.get("best_classical_result") or res.get("quantum_qaoa_result")
    if best:
        res["recommendations"] = generate_chw_recommendation(
            scenario_name=s.name,
            assignments=best.get("assignments") or [],
            gini_equity_index=best.get("gini_equity_index") or 0.0,
            total_travel_km=best.get("total_travel_km") or 0.0,
            uncovered_communities=[],
        )
    return res


@router.post("/solve/quantum")
def solve_quantum(req: SolveRequest) -> Dict[str, Any]:
    s = get_scenario_by_name(req.scenario_name)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scenario '{req.scenario_name}' not found.")
    # Default backend is free qBraid simulator; Emerald only if explicitly requested.
    solver = QAOAQuantumSolver(backend_name=req.backend_name)
    res = solver.solve(s)
    return res.model_dump()


@router.get("/solve/classical/methods")
def list_classical_methods() -> Dict[str, Any]:
    """List classical suite solvers (all local CPU; never QPU)."""
    return {
        "execution_target": config.CLASSICAL_EXECUTION_TARGET,
        "methods": list_classical_solver_ids(),
    }


@router.post("/solve/classical")
def solve_classical(req: ClassicalSolveRequest) -> Dict[str, Any]:
    s = get_scenario_by_name(req.scenario_name)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scenario '{req.scenario_name}' not found.")
    try:
        solver = get_classical_solver(req.solver_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = solver.solve(s, time_budget_sec=req.time_budget_sec, seed=req.seed)
    return result.model_dump()


@router.post("/solve/classical/suite")
def solve_classical_suite(req: ClassicalSuiteRequest) -> Dict[str, Any]:
    """Run multiple classical solvers on local CPU and rank by objective."""
    s = get_scenario_by_name(req.scenario_name)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scenario '{req.scenario_name}' not found.")
    return compare_classical_suite(
        s,
        time_budget_sec=req.time_budget_sec,
        seed=req.seed,
        include=req.include,
    )


@router.post("/solve/classical/suite/all")
def solve_classical_suite_all(req: ClassicalAllCountiesRequest) -> Dict[str, Any]:
    """
    Run classical suite on ALL 14 county scenarios (not a single location).
    Tuned for qBraid Small · VS Code. Includes Q-SOLVE judging evidence block.
    """
    return compare_classical_suite_all_scenarios(
        time_budget_sec=req.time_budget_sec,
        seed=req.seed,
        include=req.include,
    )


class LadderSolveRequest(BaseModel):
    tier: str = "T0"
    county: str = "TURKANA"
    solver_id: str = "c3_greedy"
    constraint_setting: str = "nominal"
    feature_stage: str = "B4"
    seed: int = 42
    time_budget_sec: float = 15.0
    who_capacity_mode: str = "feasible"


class InteractiveSolveRequest(BaseModel):
    """Build a real ladder instance and run classical (default) or quantum after a bottleneck."""

    tier: str = "T1"
    county: str = "TURKANA"
    constraint_setting: str = "nominal"
    feature_stage: str = "B4"
    seed: int = 42
    time_budget_sec: float = 12.0
    who_capacity_mode: str = "feasible"
    # classical (default for UI) | quantum | both
    mode: str = "classical"
    classical_include: Optional[List[str]] = None
    run_quantum: Optional[bool] = None  # overrides mode if set
    backend_name: str = config.QBRAID_FREE_SIMULATOR
    preview_only: bool = False
    # Custom constraint overrides (optional; fall back to preset)
    max_walking_dist_km: Optional[float] = None
    who_ratio: Optional[float] = None
    equity_target: Optional[float] = None
    # Which unified-dataset demand factors enter y_j (None = all for feature_stage)
    enabled_factors: Optional[List[str]] = None
    # Optional total CHW headcount override (distributes across facilities)
    num_chws_total: Optional[int] = None


def _build_from_request(req: InteractiveSolveRequest):
    return build_ladder_instance(
        tier=req.tier,
        county=req.county,
        seed=req.seed,
        constraint_setting=req.constraint_setting,
        feature_stage=req.feature_stage,
        who_capacity_mode=req.who_capacity_mode,
        enabled_factors=req.enabled_factors,
        max_walking_dist_km=req.max_walking_dist_km,
        who_ratio=req.who_ratio,
        equity_target=req.equity_target,
        num_chws_total=req.num_chws_total,
    )


def _scenario_summary(scenario) -> Dict[str, Any]:
    extra = scenario.extra or {}
    return {
        "name": scenario.name,
        "title": scenario.title,
        "county": scenario.county,
        "tier": scenario.tier,
        "seed": scenario.seed,
        "constraint_setting": scenario.constraint_setting,
        "feature_stage": scenario.feature_stage,
        "num_facilities": len(scenario.facilities),
        "num_communities": len(scenario.communities),
        "num_variables": scenario.num_variables,
        "qubit_count": scenario.qubit_count,
        "who_ratio": scenario.who_ratio,
        "equity_target": scenario.equity_target,
        "max_walking_dist_km": scenario.max_walking_dist_km,
        "num_chws_available": scenario.num_chws_available,
        "who_capacity_mode": extra.get("who_capacity_mode"),
        "requested_total_chws": extra.get("requested_total_chws") or extra.get("user_total_chws"),
        "packing_ok": extra.get("packing_ok"),
        "extra": {
            "who_capacity_mode": extra.get("who_capacity_mode"),
            "requested_total_chws": extra.get("requested_total_chws") or extra.get("user_total_chws"),
            "user_total_chws": extra.get("user_total_chws"),
            "packing_ok": extra.get("packing_ok"),
            "headcount_raised": extra.get("headcount_raised"),
        },
        "enabled_factors": extra.get("enabled_factors")
        or default_enabled_factors(scenario.feature_stage),
        "constraint_overrides": extra.get("constraint_overrides"),
        "facilities": [
            {
                "id": f.id,
                "name": f.name,
                "available_chws": f.available_chws,
                "lat": f.lat,
                "lon": f.lon,
            }
            for f in scenario.facilities
        ],
        "communities": [
            {
                "id": c.id,
                "name": c.name,
                "population": c.population,
                "demand_score": c.demand_score,
                "lat": c.lat,
                "lon": c.lon,
            }
            for c in scenario.communities
        ],
        "quantum_recommended": scenario.num_variables <= config.MAX_QUBITS,
        "lambdas": scenario.lambdas.model_dump() if scenario.lambdas else None,
    }


def _classical_batch_for_hurdle(scenario, suite: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten suite results into hurdle-classifier records."""
    batch: List[Dict[str, Any]] = []
    results = suite.get("results") or {}
    for solver_id, res in results.items():
        if not isinstance(res, dict):
            continue
        batch.append(
            {
                "solver_id": solver_id,
                "tier": scenario.tier,
                "county": scenario.county,
                "seed": scenario.seed,
                "constraint_setting": scenario.constraint_setting,
                "feature_stage": scenario.feature_stage,
                "who_capacity_mode": (scenario.extra or {}).get("who_capacity_mode"),
                "num_variables": scenario.num_variables,
                "equity_target": scenario.equity_target,
                "status": res.get("status"),
                "objective_value": res.get("objective_value"),
                "population_coverage_pct": res.get("population_coverage_pct"),
                "gini_equity_index": res.get("gini_equity_index"),
                "who_compliance_pct": res.get("who_compliance_pct"),
                "d_p90_km": res.get("d_p90_km"),
            }
        )
    return batch


@router.get("/ladder")
def get_ladder_catalog() -> Dict[str, Any]:
    cat = ladder_catalog()
    cat["max_qubits_for_qaoa"] = config.MAX_QUBITS
    cat["classical_methods"] = list_classical_solver_ids()
    cat["constraint_presets"] = list_constraint_presets()
    cat["feature_stages"] = list_feature_stages()
    cat["demand_factors"] = list_demand_factors("B4")
    cat["default_enabled_factors"] = default_enabled_factors("B4")
    cat["tier_labels"] = {
        "T0": "Tiny cluster (2 facilities × 3 communities)",
        "T1": "Small cluster (3 × 4)",
        "T2": "Medium cluster (4 × 5)",
        "T3": "Large cluster (6 × 6)",
        "T4": "Extra-large cluster (6 × 9)",
        "T5": "Whole county",
        "T6": "Multi-county region",
    }
    return cat


@router.get("/constraints")
def get_constraints() -> Dict[str, Any]:
    return {
        "presets": list_constraint_presets(),
        "detail": {k: {
            "max_walking_dist_km": get_constraint_preset(k)["max_walking_dist_km"],
            "who_ratio": get_constraint_preset(k)["who_ratio"],
            "equity_target": get_constraint_preset(k)["equity_target"],
        } for k in list_constraint_presets()},
        "defaults": {
            "max_walking_dist_km": get_constraint_preset("nominal")["max_walking_dist_km"],
            "who_ratio": get_constraint_preset("nominal")["who_ratio"],
            "equity_target": get_constraint_preset("nominal")["equity_target"],
        },
    }


@router.get("/features")
def get_feature_stages() -> Dict[str, Any]:
    return {
        "stages": list_feature_stages(),
        "factors": list_demand_factors("B4"),
        "default_enabled_factors": default_enabled_factors("B4"),
    }


@router.post("/scenario/preview")
def preview_ladder_scenario(req: InteractiveSolveRequest) -> Dict[str, Any]:
    """Build instance from knobs without solving — for UI confirmation."""
    try:
        scenario = _build_from_request(req)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "scenario": _scenario_summary(scenario)}


@router.post("/solve/interactive")
def solve_interactive(req: InteractiveSolveRequest) -> Dict[str, Any]:
    """
    End-user entrypoint: configure county, constraints, and demand factors,
    then run classical solvers on the shared objective.

    Quantum runs when mode is quantum/both/compare and N ≤ MAX_QUBITS.
    Whole-county instances are skipped with an explicit reason (not silent).
    Public UI defaults to mode=classical; opt-in compare sets mode=both.
    """
    try:
        scenario = _build_from_request(req)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    summary = _scenario_summary(scenario)
    if req.preview_only:
        return {"ok": True, "scenario": summary, "solved": False}

    mode = (req.mode or "classical").strip().lower()
    if req.run_quantum is True and mode == "classical":
        mode = "both"
    elif req.run_quantum is False and mode in {"both", "quantum", "compare"}:
        mode = "classical"

    force_quantum_only = mode == "quantum"
    want_classical = mode in {"classical", "both", "compare"}
    allow_quantum_request = mode in {"quantum", "both", "compare"}

    classical_include = req.classical_include
    if want_classical:
        if not classical_include:
            classical_include = list(list_classical_solver_ids())
        classical_include = [
            m for m in classical_include
            if not (m == "c1_brute_force" and scenario.num_variables > 12)
            and not (m == "c6_genetic_algorithm" and scenario.num_variables > 54)
            and not (m == "c2_milp" and scenario.num_variables > 400)
            and not (m == "c5_simulated_annealing" and scenario.num_variables > 2000)
        ]

    payload: Dict[str, Any] = {
        "ok": True,
        "solved": True,
        "mode": mode,
        "scenario": summary,
        "classical_execution_target": config.CLASSICAL_EXECUTION_TARGET,
        "quantum_backend": None,
        "hurdle": None,
    }

    hurdle_info: Optional[Dict[str, Any]] = None
    if want_classical:
        suite = compare_classical_suite(
            scenario,
            time_budget_sec=req.time_budget_sec,
            seed=req.seed,
            include=classical_include,
        )
        payload["classical"] = {
            "best_classical": suite.get("best_classical"),
            "ranking_by_objective": suite.get("ranking_by_objective"),
            "results": suite.get("results"),
            "time_budget_sec": req.time_budget_sec,
        }
        payload["optimized_solution"] = None
        best = suite.get("best_classical")
        if best and suite.get("results", {}).get(best):
            best_res = suite["results"][best]
            # Primary UI block: optimized x* reported in H(x) variables
            payload["optimized_solution"] = {
                "solver": best,
                "objective_value": best_res.get("objective_value"),
                "objective_terms": best_res.get("objective_terms") or {},
                "objective_raw": best_res.get("objective_raw") or {},
                "objective_inputs": best_res.get("objective_inputs") or {},
                "demand_weighted_travel": best_res.get("demand_weighted_travel"),
                "total_travel_km": best_res.get("total_travel_km"),
                "gini_equity_index": best_res.get("gini_equity_index"),
                "who_compliance_pct": best_res.get("who_compliance_pct"),
                "population_coverage_pct": best_res.get("population_coverage_pct"),
                "assignments": best_res.get("assignments") or [],
                "status": best_res.get("status"),
                "note": (
                    "objective_value is H(x*). Travel term uses d_ij × y_j "
                    "(demand_weighted_travel); total_travel_km is raw walking km."
                ),
            }
            payload["recommendations"] = generate_chw_recommendation(
                scenario_name=scenario.name,
                assignments=best_res.get("assignments") or [],
                gini_equity_index=best_res.get("gini_equity_index") or 0.0,
                total_travel_km=best_res.get("total_travel_km") or 0.0,
                uncovered_communities=[],
            )
        hurdle_info = classify_instance(_classical_batch_for_hurdle(scenario, suite))
        payload["hurdle"] = hurdle_info
    else:
        payload["classical"] = None
        payload["optimized_solution"] = None

    quantum_candidate = bool(hurdle_info and hurdle_info.get("quantum_candidate"))
    # Explicit UI/API compare (mode=both|compare|quantum) runs QAOA when N fits.
    # Hurdle labels stay in the payload so we never claim advantage vs greedy.
    want_quantum = False
    if force_quantum_only or allow_quantum_request:
        want_quantum = True

    if want_quantum:
        payload["quantum_backend"] = req.backend_name
        if scenario.num_variables > config.MAX_QUBITS:
            payload["quantum"] = {
                "skipped": True,
                "reason": (
                    f"This instance has {scenario.num_variables} assignment variables "
                    f"(facilities × communities). QAOA needs one qubit per variable and "
                    f"the comparator cap is {config.MAX_QUBITS} qubits — use Tiny/Small/"
                    f"Medium cluster (T0–T2), not whole county."
                ),
                "result": None,
                "triggered_by_hurdle": (hurdle_info or {}).get("hurdle"),
                "quantum_candidate": quantum_candidate,
            }
        else:
            solver = QAOAQuantumSolver(backend_name=req.backend_name)
            qres = solver.solve(scenario)
            payload["quantum"] = {
                "skipped": False,
                "reason": None,
                "result": qres.model_dump(),
                "triggered_by_hurdle": (hurdle_info or {}).get("hurdle"),
                "quantum_candidate": quantum_candidate,
            }
    else:
        payload["quantum"] = None

    classical_best = None
    if payload.get("classical") and payload["classical"].get("best_classical"):
        bid = payload["classical"]["best_classical"]
        classical_best = (payload["classical"].get("results") or {}).get(bid)
    qres = (payload.get("quantum") or {}).get("result")
    if (
        classical_best
        and qres
        and classical_best.get("objective_value") is not None
        and qres.get("objective_value") is not None
    ):
        c_h = float(classical_best["objective_value"])
        q_h = float(qres["objective_value"])
        gap = (q_h - c_h) / max(abs(c_h), 1e-9)
        payload["side_by_side"] = {
            "classical_solver": payload["classical"]["best_classical"],
            "classical_H": c_h,
            "classical_time_sec": classical_best.get("execution_time_sec"),
            "classical_coverage_pct": classical_best.get("population_coverage_pct"),
            "classical_gini": classical_best.get("gini_equity_index"),
            "classical_travel_km": classical_best.get("total_travel_km"),
            "classical_demand_weighted_travel": classical_best.get("demand_weighted_travel"),
            "classical_objective_terms": classical_best.get("objective_terms"),
            "quantum_H": q_h,
            "quantum_time_sec": qres.get("execution_time_sec"),
            "quantum_coverage_pct": qres.get("population_coverage_pct"),
            "quantum_gini": qres.get("gini_equity_index"),
            "quantum_travel_km": qres.get("total_travel_km"),
            "quantum_demand_weighted_travel": qres.get("demand_weighted_travel"),
            "quantum_objective_terms": qres.get("objective_terms"),
            "gap_qaoa_to_best_classical": round(gap, 4),
            "qaoa_beats_best_classical": q_h < c_h,
            "note": "Lower objective H(x) is better. Advantage requires beating best classical.",
        }
    else:
        payload["side_by_side"] = None

    return payload


@router.post("/solve/classical/ladder")
def solve_classical_ladder(req: LadderSolveRequest) -> Dict[str, Any]:
    try:
        scenario = build_ladder_instance(
            tier=req.tier,
            county=req.county,
            seed=req.seed,
            constraint_setting=req.constraint_setting,
            feature_stage=req.feature_stage,
            who_capacity_mode=req.who_capacity_mode,
        )
        solver = get_classical_solver(req.solver_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = solver.solve(scenario, time_budget_sec=req.time_budget_sec, seed=req.seed)
    payload = result.model_dump()
    payload["scenario"] = _scenario_summary(scenario)
    return payload


@router.get("/benchmarks/scaling")
def get_scaling_benchmarks() -> Dict[str, Any]:
    path = Path("data/classical_suite_results.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run scripts/run_classical_suite.py first.")
    return json.loads(path.read_text())


@router.get("/benchmarks/quantum")
def get_quantum_benchmarks() -> Dict[str, Any]:
    path = Path("data/quantum_benchmark_results.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run scripts/run_quantum_phase3.py first.")
    return json.loads(path.read_text())


@router.get("/benchmarks/shared")
def get_shared_benchmark_catalogue() -> Dict[str, Any]:
    """Instances aligned by (tier, county, seed, constraint, feature_stage) for fair compare."""
    return shared_instance_catalogue()


@router.get("/benchmarks/paired")
def get_paired_benchmarks() -> Dict[str, Any]:
    """Only instances present in both classical and quantum stores."""
    rows = paired_comparison_rows()
    return {"n": len(rows), "rows": rows}


@router.get("/benchmarks/objective-compare")
def get_objective_h_compare() -> Dict[str, Any]:
    """
    Published results table: classical optimised H(x) vs quantum objective value
    from data/quantum_benchmark_results.json (usable classical pick).
    """
    payload = objective_h_comparison()
    if not payload.get("rows"):
        raise HTTPException(
            status_code=404,
            detail="No quantum benchmark rows — run scripts/run_quantum_phase3.py first.",
        )
    return payload


@router.get("/benchmarks/classical-evaluation")
def get_classical_quantum_evaluation() -> Dict[str, Any]:
    """
    Dashboard evaluation: rank C1–C7 from published ladder metrics, and map
    each classical failure / limit to where quantum can add hybrid value
    (even when classical already solves the instance).
    """
    payload = build_classical_quantum_evaluation()
    if payload.get("status") == "missing_classical":
        raise HTTPException(
            status_code=404,
            detail="Run scripts/run_classical_suite.py first to publish classical results.",
        )
    return payload


@router.get("/dataset/inventory")
def get_dataset_inventory() -> Dict[str, Any]:
    return dataset_inventory()


@router.get("/verdict")
def get_advantage_verdict() -> Dict[str, Any]:
    """§6 advantage verdict (generated by scripts/write_advantage_verdict.py)."""
    return load_verdict_summary()


@router.get("/qbraid/devices")
def list_qbraid_devices() -> List[Dict[str, Any]]:
    """List free simulators (default) and optional QPUs on qBraid."""
    return qbraid_manager.list_available_backends()


@router.get("/qbraid/jobs")
def list_qbraid_jobs() -> List[Dict[str, Any]]:
    """Sync and list qBraid platform job history for frontend telemetry."""
    return [job.model_dump() for job in qbraid_manager.list_jobs()]


@router.get("/qbraid/job/{job_id}")
def get_qbraid_job_status(job_id: str) -> Dict[str, Any]:
    job = qbraid_manager.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"qBraid job '{job_id}' not found.")
    return job.model_dump()
