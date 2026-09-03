"""
Benchmark Comparison Engine for CHW Deployment Solvers.

Classical suite runs on local CPU (qBraid Small · VS Code friendly).
Quantum comparator defaults to free qBraid simulator (not Emerald QPU).
Fair compare: QAOA vs best of C2–C7 (never greedy alone as "advantage").
Every multi-scenario report attaches Q-SOLVE judging context (JC1–JC7).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend import config
from backend.judging import attach_judging_to_report
from backend.optimization.classical_suite import get_classical_solver, list_classical_solver_ids, run_all_classical
from backend.optimization.quantum_solver import QAOAQuantumSolver
from backend.scenario.models import CHWDeploymentScenario, CHWSolutionResult
from backend.scenario.sample_scenarios import SAMPLE_SCENARIOS

# Primary classical rivals for quantum comparison (plan §5.2)
CLASSICAL_RIVALS = [
    "c2_milp",
    "c3_greedy",
    "c4_local_search",
    "c5_simulated_annealing",
    "c6_genetic_algorithm",
    "c7_tabu_search",
]


def _rank_classical(results: Dict[str, CHWSolutionResult]) -> List[tuple]:
    """Lower objective wins; empty / unassigned plans are ranked last."""

    def key(kv):
        sid, res = kv
        n_assign = len(res.assignments or [])
        empty = 0 if n_assign > 0 else 1
        obj = float("inf") if res.objective_value is None else float(res.objective_value)
        status_penalty = 0 if res.status in {"optimal", "feasible", "heuristic"} else 1
        return (empty, obj, status_penalty, res.execution_time_sec)

    return sorted(results.items(), key=key)


def compare_chw_solvers(
    scenario: CHWDeploymentScenario,
    backend_name: Optional[str] = None,
    classical_include: Optional[List[str]] = None,
    classical_budget_sec: float = 15.0,
    seed: int = 42,
    run_quantum: bool = True,
) -> Dict[str, Any]:
    """
    Fair classical-first compare: run C2–C7 (default), optionally QAOA.

    Primary rival for quantum is **best classical**, not greedy alone.
    """
    backend_name = backend_name or config.QBRAID_FREE_SIMULATOR
    methods = classical_include or [m for m in CLASSICAL_RIVALS if m in list_classical_solver_ids()]
    # Always include C1 on tiny instances for exact reference
    if scenario.num_variables <= 12 and "c1_brute_force" not in methods:
        methods = ["c1_brute_force"] + methods

    classical_results = run_all_classical(
        scenario,
        time_budget_sec=classical_budget_sec,
        seed=seed,
        include=methods,
    )
    ranked = _rank_classical(classical_results)
    best_id, best_res = ranked[0] if ranked else (None, None)

    qaoa_result: Optional[CHWSolutionResult] = None
    if run_quantum and scenario.num_variables <= config.MAX_QUBITS:
        qaoa_solver = QAOAQuantumSolver(backend_name=backend_name)
        qaoa_result = qaoa_solver.solve(scenario)

    beats_best = False
    gap = None
    if qaoa_result and best_res and best_res.objective_value is not None and qaoa_result.objective_value is not None:
        gap = round(
            (qaoa_result.objective_value - best_res.objective_value) / max(abs(best_res.objective_value), 1e-9),
            4,
        )
        beats_best = qaoa_result.objective_value < best_res.objective_value

    greedy = classical_results.get("c3_greedy")
    metrics = {
        "best_classical_id": best_id,
        "best_classical_objective": best_res.objective_value if best_res else None,
        "gap_qaoa_to_best_classical": gap,
        "qaoa_beats_best_classical": beats_best,
        "note": "Advantage claims require beating best of C2–C7, not greedy alone.",
    }
    if greedy and best_res:
        metrics["travel_vs_greedy_km"] = round(greedy.total_travel_km - best_res.total_travel_km, 2)
        metrics["coverage_vs_greedy_pct"] = round(
            best_res.population_coverage_pct - greedy.population_coverage_pct, 2
        )

    report: Dict[str, Any] = {
        "scenario_name": scenario.name,
        "county": scenario.county,
        "tier": scenario.tier,
        "num_variables": scenario.num_variables,
        "classical_execution_target": config.CLASSICAL_EXECUTION_TARGET,
        "qbraid_lab_instance": config.QBRAID_LAB_INSTANCE,
        "quantum_backend": backend_name if run_quantum else None,
        "classical_results": {k: v.model_dump() for k, v in classical_results.items()},
        "ranking_by_objective": [
            {
                "solver_id": sid,
                "objective_value": res.objective_value,
                "objective_terms": res.objective_terms,
                "demand_weighted_travel": res.demand_weighted_travel,
                "status": res.status,
                "gini_equity_index": res.gini_equity_index,
                "who_compliance_pct": res.who_compliance_pct,
                "population_coverage_pct": res.population_coverage_pct,
                "total_travel_km": res.total_travel_km,
                "d_p90_km": res.d_p90_km,
                "execution_time_sec": res.execution_time_sec,
                "is_best": sid == best_id,
            }
            for sid, res in ranked
        ],
        "best_classical": best_id,
        "best_classical_result": best_res.model_dump() if best_res else None,
        "quantum_qaoa_result": qaoa_result.model_dump() if qaoa_result else None,
        # Backward-compatible aliases for older UI snippets
        "classical_greedy_result": greedy.model_dump() if greedy else None,
        "metrics_comparison": metrics,
        "qbraid_sync_status": "ONLINE" if qaoa_result else "CLASSICAL_ONLY",
    }
    return attach_judging_to_report(
        report,
        {
            "counties_covered": 1,
            "scenarios_run": 1,
            "classical_methods_run": len(classical_results),
            "has_shared_objective": True,
            "has_multi_metric_equity": best_res is not None and best_res.theil_index is not None,
            "classical_bottleneck_detected": any(
                r.status in {"timeout", "bottleneck", "infeasible", "error"} for r in classical_results.values()
            ),
            "quantum_ran": qaoa_result is not None,
            "quantum_claimed_advantage": False,
            "quantum_beats_best_classical": beats_best,
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
    ranked = _rank_classical(results)
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
                "objective_terms": res.objective_terms,
                "demand_weighted_travel": res.demand_weighted_travel,
                "status": res.status,
                "gini_equity_index": res.gini_equity_index,
                "theil_index": res.theil_index,
                "d_p90_km": res.d_p90_km,
                "who_compliance_pct": res.who_compliance_pct,
                "population_coverage_pct": res.population_coverage_pct,
                "total_travel_km": res.total_travel_km,
                "bottom_quintile_coverage_pct": res.bottom_quintile_coverage_pct,
                "execution_time_sec": res.execution_time_sec,
                "n_assignments": len(res.assignments or []),
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
