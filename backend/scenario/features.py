"""
Feature stages B0–B4 and demand intensity y_j.

Every available verified covariate can enter the demand score. Missing values
are skipped (weight redistributed) — never filled with random numbers.

Callers may pass `enabled_factors` to include only selected covariates
(interactive planner); when omitted, stage B0–B4 behavior is unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

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
        "facility_delivery_pct",
        "skilled_delivery_pct",
        "anc4_pct",
        "malaria_itn_gap_pct",
        "hh_itn_ownership_pct",
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
        "ccri_risk_index",
        "poverty_overall_pct",
    ],
}

FACTOR_META: Dict[str, Dict[str, str]] = {
    "vulnerability_score": {
        "label": "Community vulnerability",
        "group": "Access & need",
        "description": "Baseline vulnerability score for the community unit",
    },
    "under5_share": {
        "label": "Share of children under 5",
        "group": "Access & need",
        "description": "Higher under-5 population increases coverage urgency",
    },
    "access_need": {
        "label": "Poor clinic access",
        "group": "Access & need",
        "description": "Gap in population within 1 hour of primary care",
    },
    "population_norm": {
        "label": "Population size",
        "group": "Workforce gap",
        "description": "Larger communities need more CHW attention",
    },
    "chw_gap": {
        "label": "CHW staffing gap",
        "group": "Workforce gap",
        "description": "Population relative to available CHWs at nearby hubs",
    },
    "travel_friction_phc_1h": {
        "label": "Travel difficulty to clinic",
        "group": "Terrain & travel",
        "description": "Friction getting to a primary health facility within 1 hour",
    },
    "distance_to_level3_norm": {
        "label": "Distance to higher-level facility",
        "group": "Terrain & travel",
        "description": "How far the community is from a Level 3+ facility",
    },
    "arid_terrain": {
        "label": "Arid / pastoral terrain",
        "group": "Terrain & travel",
        "description": "Arid counties have harder walking and seasonal movement",
    },
    "stunting_u5_pct": {
        "label": "Child stunting",
        "group": "Nutrition & maternal",
        "description": "County under-5 stunting rate (KDHS)",
    },
    "wasting_u5_pct": {
        "label": "Child wasting",
        "group": "Nutrition & maternal",
        "description": "County under-5 wasting rate (KDHS)",
    },
    "underweight_u5_pct": {
        "label": "Child underweight",
        "group": "Nutrition & maternal",
        "description": "County under-5 underweight rate (KDHS)",
    },
    "maternal_risk_index": {
        "label": "Maternal care risk",
        "group": "Nutrition & maternal",
        "description": "Higher when facility deliveries are lower",
    },
    "facility_delivery_pct": {
        "label": "Facility delivery rate",
        "group": "Nutrition & maternal",
        "description": "Share of births in a health facility (higher = lower need)",
    },
    "skilled_delivery_pct": {
        "label": "Skilled birth attendance",
        "group": "Nutrition & maternal",
        "description": "Share of births with a skilled attendant (higher = lower need)",
    },
    "anc4_pct": {
        "label": "ANC4 coverage",
        "group": "Nutrition & maternal",
        "description": "Four or more antenatal visits (higher = lower need)",
    },
    "malaria_itn_gap_pct": {
        "label": "Malaria protection gap",
        "group": "Malaria & disease",
        "description": "Households without insecticide-treated nets",
    },
    "hh_itn_ownership_pct": {
        "label": "ITN ownership",
        "group": "Malaria & disease",
        "description": "Household insecticide-treated net ownership (higher = lower need)",
    },
    "ccri_malaria_pf_score": {
        "label": "Malaria exposure (CCRI)",
        "group": "Malaria & disease",
        "description": "Child malaria exposure score from CCRI-DRM",
    },
    "ccri_child_nutrition_score": {
        "label": "Child nutrition risk (CCRI)",
        "group": "Nutrition & maternal",
        "description": "CCRI child nutrition risk score",
    },
    "ccri_maternal_health_score": {
        "label": "Maternal health risk (CCRI)",
        "group": "Nutrition & maternal",
        "description": "CCRI maternal health risk score",
    },
    "flood_risk_flag": {
        "label": "Flood isolation risk",
        "group": "Climate & poverty",
        "description": "Community in a flood-exposed area",
    },
    "seasonal_mobility_flag": {
        "label": "Seasonal pastoral mobility",
        "group": "Climate & poverty",
        "description": "Arid pastoral counties with seasonal movement",
    },
    "ccri_riverine_flood_score": {
        "label": "River flood hazard",
        "group": "Climate & poverty",
        "description": "CCRI riverine flood hazard score",
    },
    "ccri_drought_score": {
        "label": "Drought risk",
        "group": "Climate & poverty",
        "description": "CCRI drought risk score",
    },
    "ccri_food_insecurity_score": {
        "label": "Food insecurity",
        "group": "Climate & poverty",
        "description": "CCRI food insecurity score",
    },
    "ccri_risk_index": {
        "label": "Composite climate risk",
        "group": "Climate & poverty",
        "description": "Overall CCRI-DRM child climate risk index",
    },
    "poverty_overall_pct": {
        "label": "Poverty rate",
        "group": "Climate & poverty",
        "description": "County overall poverty rate (KNBS)",
    },
}

# Higher values mean better outcomes — invert so they raise urgency when low.
INVERSE_NEED_FIELDS = {
    "facility_delivery_pct",
    "skilled_delivery_pct",
    "anc4_pct",
    "hh_itn_ownership_pct",
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


def all_factor_ids() -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for stage in FEATURE_STAGES:
        for fid in STAGE_GROUPS[stage]:
            if fid not in seen:
                seen.add(fid)
                out.append(fid)
    return out


def default_enabled_factors(stage: str = "B4") -> List[str]:
    """All factor ids available at or below the given stage."""
    stage = (stage or "B4").upper()
    out: List[str] = []
    for s in FEATURE_STAGES:
        if stage_at_least(stage, s):
            out.extend(STAGE_GROUPS[s])
    return out


def list_demand_factors(stage: str = "B4") -> List[Dict[str, str]]:
    """Plain-language catalog for the interactive planner."""
    ids = default_enabled_factors(stage)
    catalog = []
    for fid in ids:
        meta = FACTOR_META.get(fid, {})
        catalog.append(
            {
                "id": fid,
                "label": meta.get("label", fid.replace("_", " ").title()),
                "group": meta.get("group", "Other"),
                "description": meta.get("description", ""),
                "stage": next(s for s in FEATURE_STAGES if fid in STAGE_GROUPS[s]),
            }
        )
    return catalog


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


def _normalize_enabled(enabled_factors: Optional[Sequence[str]]) -> Optional[Set[str]]:
    if enabled_factors is None:
        return None
    return {str(x).strip() for x in enabled_factors if str(x).strip()}


def _keep(feats: Dict[str, float], enabled: Optional[Set[str]]) -> Dict[str, float]:
    if enabled is None:
        return feats
    return {k: v for k, v in feats.items() if k in enabled}


def community_feature_vector(
    community: CommunityUnit,
    facilities: Sequence[HealthFacility],
    stage: str = "B4",
    enabled_factors: Optional[Sequence[str]] = None,
) -> Dict[str, float]:
    """Build a named feature dict (0–1) using covariates at `stage`, optionally filtered."""
    stage = stage.upper()
    enabled = _normalize_enabled(enabled_factors)
    # When filtering, still compute the full stage vector then keep selected keys
    # so derived features (access_need, arid_terrain) resolve correctly.
    total_chws = max(sum(f.available_chws for f in facilities), 1)
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
                val = _clip01(raw / 100.0)
            elif key in CCRI_FIELDS:
                val = _clip01(raw / 10.0)
            else:
                val = _clip01(raw)
            feats[key] = (1.0 - val) if key in INVERSE_NEED_FIELDS else val

    if stage_at_least(stage, "B4"):
        feats["flood_risk_flag"] = 1.0 if int(_get(community, "flood_risk_flag", 0) or 0) else 0.0
        feats["seasonal_mobility_flag"] = 1.0 if int(_get(community, "seasonal_mobility_flag", 0) or 0) else 0.0
        for key in [
            "ccri_riverine_flood_score",
            "ccri_drought_score",
            "ccri_food_insecurity_score",
            "ccri_risk_index",
        ]:
            raw = _get(community, key, None)
            if raw is not None:
                feats[key] = _clip01(raw / 10.0)
        pov = _get(community, "poverty_overall_pct", None)
        if pov is not None:
            feats["poverty_overall_pct"] = _clip01(pov / 100.0)

    return _keep(feats, enabled)


def composite_demand_score(
    community: CommunityUnit,
    facilities: Sequence[HealthFacility],
    stage: str = "B4",
    enabled_factors: Optional[Sequence[str]] = None,
) -> float:
    """
    Transparent weighted demand in (0, 1].
    Higher = more urgent CHW coverage need.
    """
    feats = community_feature_vector(
        community, facilities, stage, enabled_factors=enabled_factors
    )
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
    enabled_factors: Optional[Sequence[str]] = None,
) -> List[CommunityUnit]:
    updated = []
    for c in communities:
        score = composite_demand_score(
            c, facilities, stage, enabled_factors=enabled_factors
        )
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
