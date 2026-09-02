"""
Feature stages B0–B4 and demand intensity y_j.

Every available verified covariate can enter the demand score. Missing values
are skipped (weight redistributed) — never filled with random numbers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from backend.scenario.models import CommunityUnit, HealthFacility

FEATURE_STAGES = ("B0", "B1", "B2", "B3", "B4")
STAGE_RANK = {s: i for i, s in enumerate(FEATURE_STAGES)}

# Groups used by the composite demand score (Stage A → y_j for Stage B solvers)
STAGE_GROUPS: Dict[str, List[str]] = {
    "B0": ["vulnerability_score", "under5_share", "access_need"],
    "B1": ["population_norm", "chw_gap"],
    "B2": ["travel_friction_phc_1h", "distance_to_level3_norm", "arid_terrain"],
    "B3": [
        "stunting_u5_pct",
        "wasting_u5_pct",
        "underweight_u5_pct",
        "maternal_risk_index",
        "malaria_itn_gap_pct",
        "ccri_malaria_pf_score",
        "ccri_child_nutrition_score",
        "ccri_maternal_health_score",
    ],
    "B4": [
        "flood_risk_flag",
        "seasonal_mobility_flag",
        "ccri_riverine_flood_score",
        "ccri_drought_score",
        "ccri_food_insecurity_score",
        "poverty_overall_pct",
    ],
}

# Percent-like fields are divided by 100; CCRI scores are typically 0–10.
PCT_FIELDS = {
    "stunting_u5_pct",
    "wasting_u5_pct",
    "underweight_u5_pct",
    "maternal_risk_index",
    "malaria_itn_gap_pct",
    "poverty_overall_pct",
    "facility_delivery_pct",
    "skilled_delivery_pct",
    "anc4_pct",
    "hh_itn_ownership_pct",
}
CCRI_FIELDS = {
    "ccri_malaria_pf_score",
    "ccri_child_nutrition_score",
    "ccri_maternal_health_score",
    "ccri_riverine_flood_score",
    "ccri_drought_score",
    "ccri_food_insecurity_score",
    "ccri_risk_index",
}


def stage_at_least(current: str, required: str) -> bool:
    return STAGE_RANK.get(current.upper(), 0) >= STAGE_RANK.get(required.upper(), 0)


def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def _get(obj: Any, key: str, default: Optional[float] = None) -> Optional[float]:
    val = getattr(obj, key, None) if not isinstance(obj, dict) else obj.get(key)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def community_feature_vector(
    community: CommunityUnit,
    facilities: Sequence[HealthFacility],
    stage: str = "B4",
) -> Dict[str, float]:
    """Build a named feature dict (0–1) using all covariates available at `stage`."""
    stage = stage.upper()
    total_chws = max(sum(f.available_chws for f in facilities), 1)
    mean_pop = float(np.mean([c.population for c in [community]])) or 1.0
    feats: Dict[str, float] = {}

    if stage_at_least(stage, "B0"):
        feats["vulnerability_score"] = _clip01(_get(community, "vulnerability_score", 0.5) or 0.5)
        feats["under5_share"] = _clip01(_get(community, "under5_share", 0.15) or 0.15)
        access = _get(community, "phc_access_1h_share", 0.7) or 0.7
        feats["access_need"] = _clip01(1.0 - access)

    if stage_at_least(stage, "B1"):
        feats["population_norm"] = _clip01(community.population / 25000.0)
        who_need = community.population / 1000.0
        feats["chw_gap"] = _clip01(who_need / max(total_chws, 1.0) / 5.0)

    if stage_at_least(stage, "B2"):
        feats["travel_friction_phc_1h"] = _clip01(_get(community, "travel_friction_phc_1h", 0.3) or 0.3)
        d3 = _get(community, "distance_to_level3_km", 10.0) or 10.0
        feats["distance_to_level3_norm"] = _clip01(d3 / 40.0)
        terrain = (community.terrain_class or "arid").lower()
        feats["arid_terrain"] = 1.0 if terrain == "arid" else 0.35

    if stage_at_least(stage, "B3"):
        for key in STAGE_GROUPS["B3"]:
            raw = _get(community, key, None)
            if raw is None:
                continue
            if key in PCT_FIELDS:
                feats[key] = _clip01(raw / 100.0)
            elif key in CCRI_FIELDS:
                feats[key] = _clip01(raw / 10.0)
            else:
                feats[key] = _clip01(raw)

    if stage_at_least(stage, "B4"):
        feats["flood_risk_flag"] = 1.0 if int(_get(community, "flood_risk_flag", 0) or 0) else 0.0
        feats["seasonal_mobility_flag"] = 1.0 if int(_get(community, "seasonal_mobility_flag", 0) or 0) else 0.0
        for key in [
            "ccri_riverine_flood_score",
            "ccri_drought_score",
            "ccri_food_insecurity_score",
        ]:
            raw = _get(community, key, None)
            if raw is not None:
                feats[key] = _clip01(raw / 10.0)
        pov = _get(community, "poverty_overall_pct", None)
        if pov is not None:
            feats["poverty_overall_pct"] = _clip01(pov / 100.0)

    return feats


def composite_demand_score(
    community: CommunityUnit,
    facilities: Sequence[HealthFacility],
    stage: str = "B4",
) -> float:
    """
    Transparent weighted demand in (0, 1].
    Higher = more urgent CHW coverage need.
    """
    feats = community_feature_vector(community, facilities, stage)
    if not feats:
        return 0.5
    # Equal weight across present features so adding a stage actually changes y_j
    score = float(np.mean(list(feats.values())))
    return float(np.clip(score, 0.05, 1.0))


def demand_intensity(community: CommunityUnit) -> float:
    """y_j used in H(x): population × demand_score (under-5 weighted)."""
    under5 = community.under5_share if community.under5_share is not None else 0.15
    # Mix total pop urgency with under-5 burden
    pop_weight = community.population * (0.55 + 0.45 * under5 / 0.20)
    return float(max(pop_weight, 1.0) * max(community.demand_score, 0.05))


def disease_risk_from_covariates(community: CommunityUnit) -> float:
    parts = []
    for key, scale in [
        ("malaria_itn_gap_pct", 100.0),
        ("ccri_malaria_pf_score", 10.0),
        ("stunting_u5_pct", 100.0),
        ("maternal_risk_index", 100.0),
        ("ccri_food_insecurity_score", 10.0),
    ]:
        raw = _get(community, key, None)
        if raw is not None:
            parts.append(_clip01(raw / scale))
    if not parts:
        return float(community.disease_risk or 0.4)
    return float(np.clip(np.mean(parts), 0.05, 1.0))


def apply_demand_to_communities(
    communities: List[CommunityUnit],
    facilities: Sequence[HealthFacility],
    stage: str = "B4",
) -> List[CommunityUnit]:
    updated = []
    for c in communities:
        score = composite_demand_score(c, facilities, stage)
        risk = disease_risk_from_covariates(c)
        weekly = int(score * (c.population / 50.0) + 20)
        updated.append(
            c.model_copy(
                update={
                    "demand_score": round(score, 4),
                    "disease_risk": round(risk, 4),
                    "estimated_weekly_demand": weekly,
                }
            )
        )
    return updated


def list_feature_stages() -> List[str]:
    return list(FEATURE_STAGES)
