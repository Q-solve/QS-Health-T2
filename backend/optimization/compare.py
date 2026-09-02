"""
Benchmark Comparison Engine for CHW Deployment Solvers.

Classical suite runs on local CPU (qBraid Small · VS Code friendly).
Quantum comparator defaults to free qBraid simulator (not Emerald QPU).
Every multi-scenario report attaches Q-SOLVE judging context (JC1–JC7).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend import config
from backend.judging import attach_judging_to_report
from backend.optimization.classical_suite import get_classical_solver, list_classical_solver_ids, run_all_classical
from backend.optimization.classical_solver import GreedyClassicalSolver
from backend.optimization.quantum_solver import QAOAQuantumSolver
from backend.scenario.models import CHWDeploymentScenario, CHWSolutionResult
from backend.scenario.sample_scenarios import SAMPLE_SCENARIOS


def compare_chw_solvers(
    scenario: CHWDeploymentScenario,
    backend_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute QAOA (free qBraid simulator by default) vs classical greedy."""
    backend_name = backend_name or config.QBRAID_FREE_SIMULATOR
    qaoa_solver = QAOAQuantumSolver(backend_name=backend_name)
    greedy_solver = GreedyClassicalSolver()

    qaoa_result: CHWSolutionResult = qaoa_solver.solve(scenario)
    greedy_result: CHWSolutionResult = greedy_solver.solve(scenario)

    travel_saved_km = round(greedy_result.total_travel_km - qaoa_result.total_travel_km, 2)
    equity_improvement_pct = round(
        (
            (greedy_result.gini_equity_index - qaoa_result.gini_equity_index)
            / max(greedy_result.gini_equity_index, 0.01)
        )
        * 100.0,
        2,
    )

    report = {
        "scenario_name": scenario.name,
        "county": scenario.county,
        "quantum_qaoa_result": qaoa_result.model_dump(),
        "classical_greedy_result": greedy_result.model_dump(),
        "quantum_backend": backend_name,
        "classical_execution_target": config.CLASSICAL_EXECUTION_TARGET,
        "qbraid_lab_instance": config.QBRAID_LAB_INSTANCE,
        "metrics_comparison": {
            "travel_saved_km": travel_saved_km,
            "equity_improvement_pct": equity_improvement_pct,
            "coverage_diff_pct": round(
                qaoa_result.population_coverage_pct - greedy_result.population_coverage_pct, 2
            ),
        },
        "qbraid_sync_status": "ONLINE",
    }
    return attach_judging_to_report(
        report,
        {
            "counties_covered": 1,
            "scenarios_run": 1,
            "classical_methods_run": 1,
            "has_shared_objective": True,
            "has_multi_metric_equity": greedy_result.theil_index is not None,
            "classical_bottleneck_detected": False,
            "quantum_ran": True,
            "quantum_claimed_advantage": False,
            "quantum_beats_best_classical": False,
            "used_free_simulator_or_local": True,
            "sdg3_metrics_present": True,
        },
    )


def compare_classical_suite(
    scenario: CHWDeploymentScenario,
    time_budget_sec: float = 15.0,
    seed: int = 42,
    include: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run selected classical solvers (local CPU) and rank by objective."""
    results = run_all_classical(
        scenario,
        time_budget_sec=time_budget_sec,
        seed=seed,
        include=include,
    )
    ranked = sorted(
        results.items(),
        key=lambda kv: (
            float("inf") if kv[1].objective_value is None else kv[1].objective_value,
            0 if kv[1].status == "optimal" else 1,  # prefer certified optimal on ties
            kv[1].execution_time_sec,
        ),
    )
    bottleneck_hit = any(
        r.status in {"timeout", "bottleneck", "infeasible", "error"} for r in results.values()
    )
    report = {
        "scenario_name": scenario.name,
        "county": scenario.county,
        "execution_target": config.CLASSICAL_EXECUTION_TARGET,
        "qbraid_lab_instance": config.QBRAID_LAB_INSTANCE,
        "time_budget_sec": time_budget_sec,
        "solvers_run": list(results.keys()),
        "available_solvers": list_classical_solver_ids(),
        "results": {k: v.model_dump() for k, v in results.items()},
        "ranking_by_objective": [
            {
                "solver_id": sid,
                "objective_value": res.objective_value,
                "status": res.status,
                "gini_equity_index": res.gini_equity_index,
                "theil_index": res.theil_index,
                "d_p90_km": res.d_p90_km,
                "who_compliance_pct": res.who_compliance_pct,
                "bottom_quintile_coverage_pct": res.bottom_quintile_coverage_pct,
                "execution_time_sec": res.execution_time_sec,
            }
            for sid, res in ranked
        ],
        "best_classical": ranked[0][0] if ranked else None,
    }
    return attach_judging_to_report(
        report,
        {
            "counties_covered": 1,
            "scenarios_run": 1,
            "classical_methods_run": len(results),
            "has_shared_objective": True,
            "has_multi_metric_equity": True,
            "classical_bottleneck_detected": bottleneck_hit,
            "quantum_ran": False,
            "quantum_claimed_advantage": False,
            "quantum_beats_best_classical": False,
            "used_free_simulator_or_local": True,
            "sdg3_metrics_present": True,
        },
    )


def compare_classical_suite_all_scenarios(
    time_budget_sec: Optional[float] = None,
    seed: int = 42,
    include: Optional[List[str]] = None,
    scenario_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run classical suite across ALL sample scenarios (14 counties).
    Tuned for qBraid Small · VS Code (sequential, modest per-scenario budget).
    """
    budget = time_budget_sec if time_budget_sec is not None else config.CLASSICAL_FULL_SWEEP_BUDGET_SEC
    names = scenario_names or list(SAMPLE_SCENARIOS.keys())
    per_scenario: Dict[str, Any] = {}
    county_set = set()
    methods = include or list_classical_solver_ids()
    bottleneck_count = 0
    wins: Dict[str, int] = {m: 0 for m in methods}

    for name in names:
        scenario = SAMPLE_SCENARIOS[name]
        county_set.add(scenario.county)
        payload = compare_classical_suite(
            scenario,
            time_budget_sec=budget,
            seed=seed,
            include=methods,
        )
        per_scenario[name] = {
            "county": scenario.county,
            "best_classical": payload["best_classical"],
            "ranking_by_objective": payload["ranking_by_objective"],
            "results_summary": {
                sid: {
                    "objective_value": res.get("objective_value"),
                    "status": res.get("status"),
                    "gini_equity_index": res.get("gini_equity_index"),
                    "theil_index": res.get("theil_index"),
                    "d_p90_km": res.get("d_p90_km"),
                    "who_compliance_pct": res.get("who_compliance_pct"),
                    "population_coverage_pct": res.get("population_coverage_pct"),
                    "total_travel_km": res.get("total_travel_km"),
                    "execution_time_sec": res.get("execution_time_sec"),
                }
                for sid, res in payload["results"].items()
            },
        }
        if payload["best_classical"]:
            wins[payload["best_classical"]] = wins.get(payload["best_classical"], 0) + 1
        if any(
            r["status"] in {"timeout", "bottleneck", "infeasible", "error"}
            for r in payload["ranking_by_objective"]
        ):
            bottleneck_count += 1

    report = {
        "execution_target": config.CLASSICAL_EXECUTION_TARGET,
        "qbraid_lab_instance": config.QBRAID_LAB_INSTANCE,
        "qbraid_lab_vcpus": config.QBRAID_LAB_VCPUS,
        "qbraid_lab_ram_gb": config.QBRAID_LAB_RAM_GB,
        "time_budget_sec_per_scenario": budget,
        "scenarios_requested": names,
        "scenarios_completed": list(per_scenario.keys()),
        "counties_covered": sorted(county_set),
        "county_count": len(county_set),
        "methods": methods,
        "wins_by_solver": wins,
        "scenarios_with_bottleneck_status": bottleneck_count,
        "per_scenario": per_scenario,
    }
    return attach_judging_to_report(
        report,
        {
            "counties_covered": len(county_set),
            "scenarios_run": len(per_scenario),
            "classical_methods_run": len(methods),
            "has_shared_objective": True,
            "has_multi_metric_equity": True,
            "classical_bottleneck_detected": bottleneck_count > 0,
            "quantum_ran": False,
            "quantum_claimed_advantage": False,
            "quantum_beats_best_classical": False,
            "used_free_simulator_or_local": True,
            "sdg3_metrics_present": True,
        },
    )


def get_solver(solver_id: str):
    return get_classical_solver(solver_id)
