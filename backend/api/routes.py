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
from backend.optimization.classical_suite import get_classical_solver, list_classical_solver_ids
from backend.optimization.quantum_solver import QAOAQuantumSolver
from backend.judging import judging_scorecard_template
from backend.qbraid_client.manager import qbraid_manager
from backend.scenario.constraints import list_constraint_presets, get_constraint_preset
from backend.scenario.features import list_feature_stages
from backend.scenario.ladder import build_ladder_instance, ladder_catalog
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
        "app": "AfyaDeploy Quantum - CHW Deployment Kenya",
        "qbraid_connected": qbraid_manager.is_connected(),
        "classical_execution_target": config.CLASSICAL_EXECUTION_TARGET,
        "qbraid_lab_instance": config.QBRAID_LAB_INSTANCE,
        "qbraid_lab_vcpus": config.QBRAID_LAB_VCPUS,
        "qbraid_lab_ram_gb": config.QBRAID_LAB_RAM_GB,
        "quantum_default_device": config.QBRAID_DEFAULT_DEVICE,
        "quantum_free_simulator": config.QBRAID_FREE_SIMULATOR,
        "target_counties_count": 14,
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
    s = get_scenario_by_name(req.scenario_name)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scenario '{req.scenario_name}' not found.")
    res = compare_chw_solvers(s, backend_name=req.backend_name)
    
    # Attach recommendations
    recommendation = generate_chw_recommendation(
        scenario_name=s.name,
        assignments=res["quantum_qaoa_result"]["assignments"],
        gini_equity_index=res["quantum_qaoa_result"]["gini_equity_index"],
        total_travel_km=res["quantum_qaoa_result"]["total_travel_km"],
        uncovered_communities=[],
    )
    res["recommendations"] = recommendation
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


@router.get("/ladder")
def get_ladder_catalog() -> Dict[str, Any]:
    return ladder_catalog()


@router.get("/constraints")
def get_constraints() -> Dict[str, Any]:
    return {
        "presets": list_constraint_presets(),
        "detail": {k: {
            "max_walking_dist_km": get_constraint_preset(k)["max_walking_dist_km"],
            "who_ratio": get_constraint_preset(k)["who_ratio"],
            "equity_target": get_constraint_preset(k)["equity_target"],
        } for k in list_constraint_presets()},
    }


@router.get("/features")
def get_feature_stages() -> Dict[str, Any]:
    return {"stages": list_feature_stages()}


@router.post("/solve/classical/ladder")
def solve_classical_ladder(req: LadderSolveRequest) -> Dict[str, Any]:
    try:
        scenario = build_ladder_instance(
            tier=req.tier,
            county=req.county,
            seed=req.seed,
            constraint_setting=req.constraint_setting,
            feature_stage=req.feature_stage,
        )
        solver = get_classical_solver(req.solver_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = solver.solve(scenario, time_budget_sec=req.time_budget_sec, seed=req.seed)
    payload = result.model_dump()
    payload["scenario"] = {
        "name": scenario.name,
        "tier": scenario.tier,
        "num_variables": scenario.num_variables,
        "who_ratio": scenario.who_ratio,
        "feature_stage": scenario.feature_stage,
        "constraint_setting": scenario.constraint_setting,
    }
    return payload


@router.get("/benchmarks/scaling")
def get_scaling_benchmarks() -> Dict[str, Any]:
    path = Path("data/classical_suite_results.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run scripts/run_classical_suite.py first.")
    return json.loads(path.read_text())


@router.get("/verdict")
def get_advantage_verdict() -> Dict[str, Any]:
    """Phase 4 placeholder: verdict is only valid after the classical matrix + quantum comparator."""
    path = Path("docs/quantum_advantage_verdict.md")
    return {
        "status": "not_yet_computed" if not path.exists() else "ready",
        "note": "Apply the §6 rubric only after Phase 2 (classical ladder) and Phase 3 (QAOA on T0–T4 vs best of C2–C7).",
        "path": str(path) if path.exists() else None,
    }


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
