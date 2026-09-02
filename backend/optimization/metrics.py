"""
Shared equity, access, and optimization metrics for classical + quantum solvers.
Phase 1: single source of truth beyond Gini alone.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


def gini_coefficient(values: Sequence[float]) -> float:
    """Gini coefficient of non-negative values. 0 = perfect equality."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0
    arr = np.clip(arr, 0.0, None)
    if np.allclose(arr.sum(), 0.0):
        return 0.0
    arr = np.sort(arr)
    n = arr.size
    idx = np.arange(1, n + 1, dtype=float)
    return float((2.0 * np.sum(idx * arr) - (n + 1) * np.sum(arr)) / (n * np.sum(arr)))


def theil_index(values: Sequence[float]) -> float:
    """Theil T index (decomposable inequality). 0 = equality."""
    arr = np.asarray(values, dtype=float)
    arr = arr[arr > 0]
    if arr.size == 0:
        return 0.0
    mean = float(arr.mean())
    if mean <= 0:
        return 0.0
    return float(np.mean((arr / mean) * np.log(arr / mean)))


def atkinson_index(values: Sequence[float], epsilon: float = 0.5) -> float:
    """Atkinson inequality index with aversion parameter epsilon."""
    arr = np.asarray(values, dtype=float)
    arr = arr[arr > 0]
    if arr.size == 0:
        return 0.0
    mean = float(arr.mean())
    if mean <= 0:
        return 0.0
    if abs(epsilon - 1.0) < 1e-12:
        geo = float(np.exp(np.mean(np.log(arr))))
        return float(1.0 - geo / mean)
    power_mean = float(np.mean(arr ** (1.0 - epsilon)) ** (1.0 / (1.0 - epsilon)))
    return float(1.0 - power_mean / mean)


def percentile(values: Sequence[float], q: float) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0
    return float(np.percentile(arr, q))


def approximation_ratio(objective: float, best_known: Optional[float], minimize: bool = True) -> Optional[float]:
    """AR relative to best-known. For minimization: best/current (capped)."""
    if best_known is None:
        return None
    if minimize:
        if objective <= 0 and best_known <= 0:
            return 1.0
        if objective == 0:
            return None
        return float(min(1.0, best_known / objective)) if best_known >= 0 else None
    if best_known == 0:
        return None
    return float(min(1.0, objective / best_known))


def evaluate_assignment_metrics(
    *,
    assignment_matrix: np.ndarray,
    dist_matrix: np.ndarray,
    populations: Sequence[float],
    vulnerability: Sequence[float],
    facility_chw_caps: Sequence[float],
    who_ratio: float = 1000.0,
    max_walking_km: float = 7.5,
) -> Dict[str, float]:
    """
    Evaluate equity/access metrics from an (F x C) binary assignment matrix.

    dist_matrix: shape (F, C) walking km
    """
    x = np.asarray(assignment_matrix, dtype=float)
    d = np.asarray(dist_matrix, dtype=float)
    pop = np.asarray(populations, dtype=float)
    vuln = np.asarray(vulnerability, dtype=float)
    caps = np.asarray(facility_chw_caps, dtype=float)

    num_f, num_c = x.shape
    assigned_mask = x.sum(axis=0) > 0.5
    covered_pop = float(pop[assigned_mask].sum()) if num_c else 0.0
    total_pop = float(pop.sum()) if num_c else 1.0
    coverage_pct = 100.0 * covered_pop / max(total_pop, 1.0)

    travel_terms = []
    access_distances = []
    for j in range(num_c):
        for i in range(num_f):
            if x[i, j] > 0.5:
                travel_terms.append(d[i, j])
                access_distances.append(d[i, j])
        if not any(x[i, j] > 0.5 for i in range(num_f)):
            # Unassigned: treat as worst observed or max walk penalty
            access_distances.append(float(d[:, j].max()) if num_f else max_walking_km)

    total_travel = float(np.sum(travel_terms)) if travel_terms else 0.0
    d_p90 = percentile(access_distances, 90) if access_distances else 0.0

    # Facility loads in population units
    loads = []
    who_ok = 0
    for i in range(num_f):
        load_pop = float(np.sum(pop * x[i, :]))
        loads.append(load_pop)
        capacity_pop = float(caps[i]) * who_ratio if i < len(caps) else who_ratio
        if load_pop <= capacity_pop + 1e-6:
            who_ok += 1
    who_compliance = 100.0 * who_ok / max(num_f, 1)

    # Bottom vulnerability quintile coverage
    if num_c >= 5:
        order = np.argsort(-vuln)  # highest vulnerability first
        k = max(1, num_c // 5)
        bottom = order[:k]
        bq_cov = 100.0 * float(np.mean(assigned_mask[bottom]))
    else:
        bq_cov = coverage_pct

    return {
        "population_coverage_pct": round(coverage_pct, 4),
        "total_travel_km": round(total_travel, 4),
        "gini_equity_index": round(gini_coefficient(access_distances), 6),
        "theil_index": round(theil_index(access_distances), 6),
        "atkinson_index": round(atkinson_index(access_distances), 6),
        "d_p90_km": round(d_p90, 4),
        "who_compliance_pct": round(who_compliance, 4),
        "bottom_quintile_coverage_pct": round(bq_cov, 4),
        "max_facility_load_pop": round(float(max(loads) if loads else 0.0), 2),
        "unassigned_communities": int(num_c - int(assigned_mask.sum())),
    }


def simple_2sfca_proxy(
    dist_matrix: np.ndarray,
    facility_supply: Sequence[float],
    community_demand: Sequence[float],
    catchment_km: float = 7.5,
) -> Tuple[float, float]:
    """
    Lightweight E2SFCA-style accessibility: median and IQR of CU access scores.
    Higher median + lower IQR ⇒ more equitable spatial access.
    """
    d = np.asarray(dist_matrix, dtype=float)
    supply = np.asarray(facility_supply, dtype=float)
    demand = np.asarray(community_demand, dtype=float)
    num_f, num_c = d.shape
    # Step 1: facility supply/demand ratios in catchment
    R = np.zeros(num_f)
    for i in range(num_f):
        in_catch = d[i, :] <= catchment_km
        dem = float(demand[in_catch].sum()) if np.any(in_catch) else 1.0
        R[i] = supply[i] / max(dem, 1.0)
    # Step 2: community accessibility
    A = np.zeros(num_c)
    for j in range(num_c):
        in_catch = d[:, j] <= catchment_km
        A[j] = float(R[in_catch].sum()) if np.any(in_catch) else 0.0
    if A.size == 0:
        return 0.0, 0.0
    q75, q25 = np.percentile(A, 75), np.percentile(A, 25)
    return float(np.median(A)), float(q75 - q25)
