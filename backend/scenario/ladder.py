"""
Instance ladder T0–T6.

Builds contiguous sub-county (or county / multi-county) assignment graphs
from the unified dataset. Distances stay real; only the sampled F×C size changes.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from backend.geo.chw_facilities import haversine_distance_km
from backend.scenario.constraints import get_constraint_preset
from backend.scenario.data_store import (
    TARGET_COUNTIES,
    build_community_units,
    build_health_facilities,
    county_community_units,
    county_facilities,
    list_counties,
    load_chu_frame,
    load_facility_frame,
    norm_county,
)
from backend.scenario.features import apply_demand_to_communities
from backend.scenario.models import CHWDeploymentScenario, CommunityUnit, HealthFacility

TIER_SPEC: Dict[str, Dict] = {
    "T0": {"num_f": 2, "num_c": 3, "scope": "cluster"},
    "T1": {"num_f": 3, "num_c": 4, "scope": "cluster"},
    "T2": {"num_f": 4, "num_c": 5, "scope": "cluster"},
    "T3": {"num_f": 6, "num_c": 6, "scope": "cluster"},
    "T4": {"num_f": 6, "num_c": 9, "scope": "cluster"},
    "T5": {"num_f": None, "num_c": None, "scope": "county"},
    "T6": {"num_f": None, "num_c": None, "scope": "multi_county"},
}

# Adjacent-ish ASAL / coastal groups for T6 slices
T6_GROUPS: List[List[str]] = [
    ["TURKANA", "WEST POKOT", "SAMBURU"],
    ["MARSABIT", "ISIOLO", "SAMBURU"],
    ["GARISSA", "WAJIR", "MANDERA"],
    ["TANA RIVER", "LAMU", "GARISSA"],
    ["KILIFI", "KWALE", "TAITA TAVETA"],
    ["NAROK", "KWALE"],
]


def _subcounty_groups(fac_df, chu_df) -> List[str]:
    subs = sorted(set(fac_df["sub_county"].dropna().astype(str)) | set(chu_df["sub_county"].dropna().astype(str)))
    return [s for s in subs if s and s.lower() != "nan"]


def _filter_sub(df, sub: str):
    return df[df["sub_county"].astype(str) == str(sub)].copy()


def _select_contiguous(
    fac_df,
    chu_df,
    num_f: int,
    num_c: int,
    rng: np.random.Generator,
) -> Tuple:
    """Pick a sub-county (or nearest) that can supply F and C, then sample nearby points."""
    subs = _subcounty_groups(fac_df, chu_df)
    order = list(subs)
    rng.shuffle(order)
    candidates = order + [None]  # None = whole county
    for sub in candidates:
        fsub = _filter_sub(fac_df, sub) if sub is not None else fac_df
        csub = _filter_sub(chu_df, sub) if sub is not None else chu_df
        if len(fsub) < min(num_f, 1) or len(csub) < min(num_c, 1):
            continue
        # If this sub-county is short, pad from the rest of the county by proximity
        f_pick = fsub
        c_pick = csub
        if len(f_pick) < num_f:
            rest = fac_df.drop(f_pick.index, errors="ignore")
            f_pick = pd_concat_closest(f_pick, rest, num_f)
        if len(c_pick) < num_c:
            rest = chu_df.drop(c_pick.index, errors="ignore")
            c_pick = pd_concat_closest(c_pick, rest, num_c)
        if len(f_pick) >= num_f and len(c_pick) >= num_c:
            f_pick = _sample_or_all(f_pick, num_f, rng)
            c_pick = _sample_or_all(c_pick, num_c, rng)
            return f_pick, c_pick, sub or "county"
    # last resort: sample from full county frames
    f_pick = _sample_or_all(fac_df, min(num_f, len(fac_df)), rng)
    c_pick = _sample_or_all(chu_df, min(num_c, len(chu_df)), rng)
    return f_pick, c_pick, "county"


def pd_concat_closest(base, rest, target_n: int):
    if base.empty or rest.empty:
        return pd.concat([base, rest]).head(target_n)
    blat, blon = float(base["lat"].mean()), float(base["lon"].mean())
    rest = rest.copy()
    rest["_d"] = [
        haversine_distance_km(blat, blon, float(r.lat), float(r.lon))
        for r in rest.itertuples()
    ]
    extra = rest.sort_values("_d").head(max(0, target_n - len(base)))
    extra = extra.drop(columns=["_d"])
    return pd.concat([base, extra], ignore_index=True)


def _sample_or_all(df, n: int, rng: np.random.Generator):
    if len(df) <= n:
        return df.reset_index(drop=True)
    idx = rng.choice(len(df), size=n, replace=False)
    return df.iloc[np.sort(idx)].reset_index(drop=True)


def _cap_for_memory(fac_n: int, chu_n: int, max_n: Optional[int]) -> Tuple[int, int]:
    """Keep N=F×C under max_n by scaling C first, then F."""
    if max_n is None or fac_n * chu_n <= max_n:
        return fac_n, chu_n
    # Prefer keeping facilities, shrink CUs
    c = max(2, min(chu_n, max_n // max(fac_n, 1)))
    if fac_n * c > max_n:
        f = max(2, int(np.sqrt(max_n)))
        c = max(2, max_n // f)
        return f, c
    return fac_n, c


def _first_fit_decreasing_feasible(pops: List[int], caps: List[float]) -> bool:
    residual = [float(c) for c in caps]
    for p in sorted(pops, reverse=True):
        residual.sort(reverse=True)
        placed = False
        for i, r in enumerate(residual):
            if r + 1e-9 >= p:
                residual[i] = r - p
                placed = True
                break
        if not placed:
            return False
    return True


def scale_facilities_to_who(
    facilities: List[HealthFacility],
    communities: List[CommunityUnit],
    who_ratio: float,
    slack: float = 1.05,
) -> Dict[str, Any]:
    """
    Scale CHW headcount so a WHO-feasible assignment can exist.

    Ward-level populations on ~2 placeholder CHWs make every exact plan
    overflow capacity. CUs are atomic, so total seats >= total population
    is not enough — we raise headcount until first-fit-decreasing packing
    succeeds. That isolates combinatorial solver limits from missing payroll.
    """
    raw_chws = [int(f.available_chws) for f in facilities]
    pops = [int(c.population) for c in communities]
    total_pop = float(sum(pops))
    max_cu = float(max(pops) if pops else 0.0)
    n_f = max(len(facilities), 1)
    who = max(float(who_ratio), 1.0)
    min_chws_each = max(1, int(math.ceil(max_cu / who)))
    need_total = max(
        int(math.ceil(total_pop * slack / who)),
        min_chws_each * n_f,
    )

    def apply(total_chws: int) -> None:
        base, rem = divmod(int(total_chws), n_f)
        for i, f in enumerate(facilities):
            f.available_chws = max(int(raw_chws[i]), base + (1 if i < rem else 0), min_chws_each)

    apply(need_total)
    guard = 0
    while not _first_fit_decreasing_feasible(
        pops, [f.available_chws * who for f in facilities]
    ) and guard < 500:
        need_total += n_f
        apply(need_total)
        guard += 1

    return {
        "who_capacity_mode": "feasible",
        "raw_total_chws": float(sum(raw_chws)),
        "scaled_total_chws": float(sum(f.available_chws for f in facilities)),
        "total_population": total_pop,
        "who_ratio": who,
        "slack": slack,
        "packing_ok": _first_fit_decreasing_feasible(
            pops, [f.available_chws * who for f in facilities]
        ),
        "capacity_increments": guard,
    }


def build_ladder_instance(
    *,
    tier: str = "T0",
    county: str = "TURKANA",
    seed: int = 42,
    constraint_setting: str = "nominal",
    feature_stage: str = "B4",
    counties: Optional[Sequence[str]] = None,
    max_variables: Optional[int] = None,
    who_capacity_mode: str = "raw",
) -> CHWDeploymentScenario:
    tier = tier.upper()
    if tier not in TIER_SPEC:
        raise KeyError(f"Unknown tier {tier}")
    spec = TIER_SPEC[tier]
    rng = np.random.default_rng(seed)
    preset = get_constraint_preset(constraint_setting)
    stage = feature_stage.upper()

    if spec["scope"] == "multi_county":
        group = list(counties) if counties else None
        if not group:
            # pick a T6 group that contains `county` if possible
            key = norm_county(county)
            group = next((g for g in T6_GROUPS if key in g), T6_GROUPS[0])
        fac_parts, chu_parts = [], []
        for cty in group:
            f = county_facilities(cty)
            u = county_community_units(cty)
            if len(f):
                fac_parts.append(f)
            if len(u):
                chu_parts.append(u)
        fac_df = pd.concat(fac_parts, ignore_index=True) if fac_parts else county_facilities(county)
        chu_df = pd.concat(chu_parts, ignore_index=True) if chu_parts else county_community_units(county)
        county_label = "+".join(norm_county(c) for c in group)
        num_f, num_c = _cap_for_memory(len(fac_df), len(chu_df), max_variables)
        fac_df = _sample_or_all(fac_df, num_f, rng)
        chu_df = _sample_or_all(chu_df, num_c, rng)
        sub_label = "multi"
    elif spec["scope"] == "county":
        fac_df = county_facilities(county)
        chu_df = county_community_units(county)
        county_label = norm_county(county)
        num_f, num_c = _cap_for_memory(len(fac_df), len(chu_df), max_variables)
        fac_df = _sample_or_all(fac_df, num_f, rng)
        chu_df = _sample_or_all(chu_df, num_c, rng)
        sub_label = "full_county"
    else:
        fac_df = county_facilities(county)
        chu_df = county_community_units(county)
        county_label = norm_county(county)
        num_f, num_c = int(spec["num_f"]), int(spec["num_c"])
        fac_df, chu_df, sub_label = _select_contiguous(fac_df, chu_df, num_f, num_c, rng)

    facilities: List[HealthFacility] = build_health_facilities(fac_df)
    communities: List[CommunityUnit] = build_community_units(chu_df)
    communities = apply_demand_to_communities(communities, facilities, stage=stage)

    cap_meta: Dict = {"who_capacity_mode": "raw"}
    if str(who_capacity_mode).lower() in {"feasible", "who_feasible", "scaled"}:
        cap_meta = scale_facilities_to_who(facilities, communities, float(preset["who_ratio"]))

    n_vars = len(facilities) * len(communities)
    name = f"{county_label.lower().replace(' ', '_')}_{tier.lower()}_s{seed}_{constraint_setting}_{stage.lower()}"
    return CHWDeploymentScenario(
        name=name,
        title=f"{county_label} {tier} CHW assignment ({constraint_setting}, {stage})",
        county=county_label,
        description=(
            f"Ladder {tier} from real KMHFR/OSM coordinates. "
            f"Scope={sub_label}. F={len(facilities)} C={len(communities)} N={n_vars}."
        ),
        num_chws_available=int(sum(f.available_chws for f in facilities)),
        max_walking_dist_km=float(preset["max_walking_dist_km"]),
        facilities=facilities,
        communities=communities,
        qubit_count=n_vars,
        who_ratio=float(preset["who_ratio"]),
        equity_target=float(preset["equity_target"]),
        constraint_setting=constraint_setting,
        feature_stage=stage,
        tier=tier,
        seed=seed,
        lambdas=preset["lambdas"],
        extra={
            "sub_scope": sub_label,
            "num_facilities": len(facilities),
            "num_communities": len(communities),
            "num_variables": n_vars,
            **cap_meta,
        },
    )


def iter_ladder_instances(
    tiers: Sequence[str] = ("T0", "T1"),
    counties: Optional[Sequence[str]] = None,
    seeds: Sequence[int] = (42,),
    constraints: Sequence[str] = ("nominal",),
    feature_stages: Sequence[str] = ("B4",),
    max_variables: Optional[int] = None,
    who_capacity_mode: str = "raw",
) -> List[CHWDeploymentScenario]:
    counties = list(counties) if counties else list_counties()
    out: List[CHWDeploymentScenario] = []
    for tier in tiers:
        for county in counties:
            for seed in seeds:
                for cons in constraints:
                    for stage in feature_stages:
                        try:
                            inst = build_ladder_instance(
                                tier=tier,
                                county=county,
                                seed=int(seed),
                                constraint_setting=cons,
                                feature_stage=stage,
                                max_variables=max_variables,
                                who_capacity_mode=who_capacity_mode,
                            )
                        except Exception:
                            continue
                        if len(inst.facilities) < 1 or len(inst.communities) < 1:
                            continue
                        out.append(inst)
    return out


def ladder_catalog() -> Dict:
    return {
        "tiers": TIER_SPEC,
        "counties": list_counties(),
        "target_counties": TARGET_COUNTIES,
        "t6_groups": T6_GROUPS,
    }
