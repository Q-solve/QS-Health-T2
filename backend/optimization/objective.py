"""
Shared multi-objective H(x) evaluator for classical and quantum solvers.

H(x) = λ1 Σ_ij d_ij y_j x_ij
     + λ2 Σ_j (Σ_i x_ij − 1)^2
     + λ3 Σ_i overflow_i^2
     + λ4 · max(0, Gini − G*) · travel
     + λ5 · walk-cap violations
     + λ6 · stipend · assigned load   (optional, default 0)

y_j uses the full demand-score × population mix from feature stages B0–B4.
d_ij is terrain/flood/mobility-adjusted walking distance.
All solvers (C1–C7 and QAOA) report this same H after decoding.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from backend.geo.chw_facilities import calculate_walking_distance_matrix
from backend.optimization.metrics import evaluate_assignment_metrics, gini_coefficient
from backend.scenario.features import demand_intensity
from backend.scenario.models import (
    CHWDeploymentScenario,
    CHWSolutionAssignment,
    CHWSolutionResult,
    ObjectiveWeights,
)


def scenario_distance_matrix(scenario: CHWDeploymentScenario) -> np.ndarray:
    """Return (F x C) terrain-adjusted walking distance matrix."""
    raw = calculate_walking_distance_matrix(
        [f.model_dump() for f in scenario.facilities],
        [c.model_dump() for c in scenario.communities],
    )
    num_f = len(scenario.facilities)
    num_c = len(scenario.communities)
    d = np.zeros((num_f, num_c), dtype=float)
    for i, f in enumerate(scenario.facilities):
        for j, c in enumerate(scenario.communities):
            d[i, j] = raw.get((f.id, c.id), scenario.max_walking_dist_km)
    return d


def demand_vector(scenario: CHWDeploymentScenario) -> np.ndarray:
    return np.array([demand_intensity(c) for c in scenario.communities], dtype=float)


def population_vector(scenario: CHWDeploymentScenario) -> np.ndarray:
    return np.array([c.population for c in scenario.communities], dtype=float)


def bitstring_to_matrix(bitstring: str, num_f: int, num_c: int) -> np.ndarray:
    expected = num_f * num_c
    bits = (bitstring + "0" * expected)[:expected]
    return np.array([1.0 if b == "1" else 0.0 for b in bits], dtype=float).reshape(num_f, num_c)


def matrix_to_bitstring(x: np.ndarray) -> str:
    flat = np.asarray(x, dtype=int).reshape(-1)
    return "".join("1" if v > 0 else "0" for v in flat)


def _weights(scenario: CHWDeploymentScenario) -> ObjectiveWeights:
    return scenario.lambdas if getattr(scenario, "lambdas", None) else ObjectiveWeights()


def evaluate_H(
    x: np.ndarray,
    dist: np.ndarray,
    scenario: CHWDeploymentScenario,
    *,
    lambda_travel: Optional[float] = None,
    lambda_assign: Optional[float] = None,
    lambda_capacity: Optional[float] = None,
    lambda_equity: Optional[float] = None,
    lambda_walk_cap: Optional[float] = None,
    who_ratio: Optional[float] = None,
) -> float:
    """Shared objective H(x) (minimize). x: (F, C) binary assignment."""
    w = _weights(scenario)
    lambda_travel = w.travel if lambda_travel is None else lambda_travel
    lambda_assign = w.assign if lambda_assign is None else lambda_assign
    lambda_capacity = w.capacity if lambda_capacity is None else lambda_capacity
    lambda_equity = w.equity if lambda_equity is None else lambda_equity
    lambda_walk_cap = w.walk_cap if lambda_walk_cap is None else lambda_walk_cap
    who_ratio = scenario.who_ratio if who_ratio is None else who_ratio

    x = np.asarray(x, dtype=float)
    num_f, num_c = x.shape
    pop = population_vector(scenario)
    y = demand_vector(scenario)

    travel = float(np.sum(dist * y * x))

    assign_pen = 0.0
    for j in range(num_c):
        s = float(x[:, j].sum())
        assign_pen += (s - 1.0) ** 2

    cap_pen = 0.0
    stipend_cost = 0.0
    for i, f in enumerate(scenario.facilities):
        load = float(np.sum(pop * x[i, :]))
        capacity = float(f.available_chws) * float(who_ratio)
        overflow = max(0.0, load - capacity)
        cap_pen += overflow ** 2
        stipend_cost += (load / max(who_ratio, 1.0)) * float(f.chw_monthly_stipend_kes) / 5000.0

    access = []
    for j in range(num_c):
        chosen = np.where(x[:, j] > 0.5)[0]
        if chosen.size:
            access.append(float(dist[chosen[0], j]))
        else:
            access.append(float(dist[:, j].max()) if num_f else float(scenario.max_walking_dist_km))
    g = gini_coefficient(access)
    g_star = float(getattr(scenario, "equity_target", 0.25) or 0.25)
    equity_excess = max(0.0, g - g_star)

    walk_pen = float(np.sum((dist > scenario.max_walking_dist_km) * x))

    return (
        lambda_travel * travel
        + lambda_assign * assign_pen
        + lambda_capacity * cap_pen
        + lambda_equity * equity_excess * max(travel, 1.0)
        + lambda_walk_cap * walk_pen
        + float(w.stipend) * stipend_cost
    )


def decode_assignments(
    scenario: CHWDeploymentScenario,
    x: np.ndarray,
    dist: np.ndarray,
) -> list[CHWSolutionAssignment]:
    assignments: list[CHWSolutionAssignment] = []
    for i, f in enumerate(scenario.facilities):
        for j, c in enumerate(scenario.communities):
            if x[i, j] > 0.5:
                assignments.append(
                    CHWSolutionAssignment(
                        facility_id=f.id,
                        facility_name=f.name,
                        community_id=c.id,
                        community_name=c.name,
                        assigned_chws=1,
                        walking_distance_km=round(float(dist[i, j]), 2),
                        demand_covered=int(round(demand_intensity(c))),
                    )
                )
    return assignments


def failure_label_for(status: str, metrics: Dict[str, float], scenario: CHWDeploymentScenario) -> Optional[str]:
    if status == "timeout":
        return "F-TIMEOUT"
    if status in {"bottleneck", "error"}:
        return "F-SCALE"
    if status == "infeasible":
        return "F-INFEASIBLE"
    return None


def build_solution_result(
    scenario: CHWDeploymentScenario,
    x: np.ndarray,
    *,
    solver_type: str,
    execution_time_sec: float,
    status: str = "feasible",
    peak_memory_mb: Optional[float] = None,
    extra_metrics: Optional[Dict[str, Any]] = None,
) -> CHWSolutionResult:
    dist = scenario_distance_matrix(scenario)
    x = np.asarray(x, dtype=float)
    pop = [c.population for c in scenario.communities]
    vuln = [c.vulnerability_score for c in scenario.communities]
    caps = [f.available_chws for f in scenario.facilities]
    metrics = evaluate_assignment_metrics(
        assignment_matrix=x,
        dist_matrix=dist,
        populations=pop,
        vulnerability=vuln,
        facility_chw_caps=caps,
        who_ratio=float(scenario.who_ratio),
        max_walking_km=scenario.max_walking_dist_km,
    )
    objective = evaluate_H(x, dist, scenario)
    label = failure_label_for(status, metrics, scenario)
    extra = dict(extra_metrics or {})
    extra["demand_stage"] = scenario.feature_stage
    extra["who_ratio"] = scenario.who_ratio
    extra["equity_target"] = scenario.equity_target
    extra["num_variables"] = scenario.num_variables
    return CHWSolutionResult(
        scenario_name=scenario.name,
        solver_type=solver_type,
        bitstring=matrix_to_bitstring(x),
        population_coverage_pct=metrics["population_coverage_pct"],
        total_travel_km=metrics["total_travel_km"],
        gini_equity_index=metrics["gini_equity_index"],
        assignments=decode_assignments(scenario, x, dist),
        execution_time_sec=round(execution_time_sec, 6),
        qbraid_job_id=None,
        qbraid_synced=False,
        objective_value=round(objective, 6),
        status=status,
        who_compliance_pct=metrics["who_compliance_pct"],
        d_p90_km=metrics["d_p90_km"],
        theil_index=metrics["theil_index"],
        atkinson_index=metrics["atkinson_index"],
        bottom_quintile_coverage_pct=metrics["bottom_quintile_coverage_pct"],
        peak_memory_mb=peak_memory_mb,
        extra_metrics=extra,
        failure_label=label,
        tier=scenario.tier,
        feature_stage=scenario.feature_stage,
        constraint_setting=scenario.constraint_setting,
        seed=scenario.seed,
    )


def empty_matrix(scenario: CHWDeploymentScenario) -> np.ndarray:
    return np.zeros((len(scenario.facilities), len(scenario.communities)), dtype=float)
