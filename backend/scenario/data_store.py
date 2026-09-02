"""
Load the unified 14-county facility matrix and KMHFR community units.

CHUs have no native lat/lon; they inherit coordinates from the linked
facility (fuzzy name match within county) plus a tiny deterministic offset
so demand nodes are not stacked on the hub.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from backend.scenario.models import CommunityUnit, HealthFacility

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
FACILITY_CSV = DATA / "unified_chw_dataset.csv"
CHU_CSV = DATA / "community_units_kmhfr.csv"
COUNTY_CSV = DATA / "county_verified_indicators.csv"

TARGET_COUNTIES = [
    "TURKANA", "GARISSA", "MANDERA", "KILIFI", "WAJIR",
    "TAITA TAVETA", "MARSABIT", "ISIOLO", "SAMBURU", "LAMU",
    "WEST POKOT", "TANA RIVER", "NAROK", "KWALE",
]

TERRAIN_GAMMA = {"arid": 1.40, "semi_arid": 1.30, "hilly": 1.30, "coastal": 1.30}

COVARIATE_COLS = [
    "under5_share", "distance_to_level3_km", "terrain_class",
    "phc_access_1h_share", "travel_friction_phc_1h",
    "stunting_u5_pct", "wasting_u5_pct", "underweight_u5_pct",
    "facility_delivery_pct", "skilled_delivery_pct", "anc4_pct",
    "maternal_risk_index", "hh_itn_ownership_pct", "malaria_itn_gap_pct",
    "ccri_malaria_pf_score", "ccri_riverine_flood_score", "ccri_drought_score",
    "ccri_food_insecurity_score", "ccri_child_nutrition_score",
    "ccri_maternal_health_score", "ccri_risk_index",
    "flood_risk_flag", "seasonal_mobility_flag", "poverty_overall_pct",
    "chw_monthly_stipend_kes", "linked_chu_count",
]


def norm_county(x: str) -> str:
    s = str(x or "").upper().replace("-", " ").replace("/", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+COUNTY$", "", s)
    if "TAITA" in s:
        return "TAITA TAVETA"
    if "POKOT" in s:
        return "WEST POKOT"
    if s.startswith("TANA"):
        return "TANA RIVER"
    return s


def _fac_key(name: str) -> str:
    s = str(name or "").upper().replace("-", " ").replace("/", " ").replace("'", "")
    for tok in [
        "DISPENSARY", "HEALTH CENTRE", "HEALTH CENTER", "HOSPITAL",
        "MEDICAL CLINIC", "CLINIC", "MEDICAL CENTER", "MEDICAL CENTRE",
        "SUB COUNTY", "SUBCOUNTY", "DISTRICT", "COUNTY REFERRAL", "REFERRAL",
    ]:
        s = s.replace(tok, "")
    return re.sub(r"\s+", " ", s).strip()


def _offset_latlon(lat: float, lon: float, key: str) -> Tuple[float, float]:
    """~0.5–2.5 km deterministic offset from a hash (CHUs sit near the linked hub)."""
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    a = int(h[:8], 16) / 0xFFFFFFFF
    b = int(h[8:16], 16) / 0xFFFFFFFF
    bearing = a * 2 * math.pi
    dist_deg = 0.004 + 0.018 * b  # roughly 0.4–2.4 km
    dlat = dist_deg * math.cos(bearing)
    dlon = dist_deg * math.sin(bearing) / max(math.cos(math.radians(lat)), 0.2)
    return lat + dlat, lon + dlon


@lru_cache(maxsize=1)
def load_facility_frame() -> pd.DataFrame:
    df = pd.read_csv(FACILITY_CSV)
    df["county"] = df["county"].map(norm_county)
    df = df[df["lat"].notna() & df["lon"].notna()].copy()
    return df


@lru_cache(maxsize=1)
def load_chu_frame() -> pd.DataFrame:
    df = pd.read_csv(CHU_CSV)
    df["county"] = df["county"].map(norm_county)
    return df


@lru_cache(maxsize=1)
def load_county_indicators() -> pd.DataFrame:
    if not COUNTY_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(COUNTY_CSV)
    df["county"] = df["county"].map(norm_county)
    return df


def list_counties() -> List[str]:
    fac = set(load_facility_frame()["county"].unique())
    chu = set(load_chu_frame()["county"].unique())
    ordered = [c for c in TARGET_COUNTIES if c in fac or c in chu]
    for c in sorted(fac | chu):
        if c not in ordered:
            ordered.append(c)
    return ordered


def _row_covariates(row: pd.Series) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for col in COVARIATE_COLS:
        if col not in row.index:
            continue
        val = row[col]
        if pd.isna(val):
            continue
        out[col] = val
    return out


def county_facilities(county: str) -> pd.DataFrame:
    key = norm_county(county)
    return load_facility_frame()[load_facility_frame()["county"] == key].copy()


def _safe_int_id(val: Any, fallback: int) -> int:
    if val is None:
        return int(fallback)
    try:
        if pd.isna(val):
            return int(fallback)
    except Exception:
        pass
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return int(fallback)


def build_health_facilities(frame: pd.DataFrame) -> List[HealthFacility]:
    facilities: List[HealthFacility] = []
    for idx, row in frame.reset_index(drop=True).iterrows():
        keph = str(row.get("keph_level") or "Level 2")
        cov = _row_covariates(row)
        facilities.append(
            HealthFacility(
                id=f"F_{idx}_{_safe_int_id(row.get('facility_code'), idx)}",
                name=str(row.get("facility_name") or f"Facility {idx}"),
                county=str(row["county"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                available_chws=int(row.get("available_chws") or 2),
                facility_level=keph,
                keph_level=keph,
                sub_county=str(row.get("sub_county") or ""),
                ward=str(row.get("ward") or ""),
                linked_chu_count=int(cov.get("linked_chu_count") or 0),
                distance_to_level3_km=float(cov.get("distance_to_level3_km") or 0.0),
                terrain_class=str(cov.get("terrain_class") or "arid"),
                chw_monthly_stipend_kes=float(cov.get("chw_monthly_stipend_kes") or 5000.0),
            )
        )
    return facilities


def _attach_chu_coords(chu: pd.DataFrame, fac: pd.DataFrame) -> pd.DataFrame:
    chu = chu.copy()
    fac = fac.copy()
    fac["link_key"] = fac["facility_name"].map(_fac_key)
    chu["link_key"] = chu["linked_facility_name"].map(_fac_key)

    # county centroids as last-resort placement
    centroids = fac.groupby("county")[["lat", "lon"]].mean()

    lats, lons, matched = [], [], []
    fac_by_county: Dict[str, pd.DataFrame] = {c: g for c, g in fac.groupby("county")}
    for _, row in chu.iterrows():
        county = row["county"]
        key = row["link_key"]
        pool = fac_by_county.get(county)
        lat = lon = None
        how = "none"
        if pool is not None and len(pool):
            exact = pool[pool["link_key"] == key]
            if len(exact):
                hit = exact.iloc[0]
                lat, lon = float(hit["lat"]), float(hit["lon"])
                how = "linked_facility"
            else:
                # token overlap fallback
                best_score, best = 0.0, None
                tokens = set(key.split()) if key else set()
                for _, frow in pool.iterrows():
                    ft = set(str(frow["link_key"]).split())
                    if not tokens or not ft:
                        continue
                    score = len(tokens & ft) / len(tokens | ft)
                    if score > best_score:
                        best_score, best = score, frow
                if best is not None and best_score >= 0.3:
                    lat, lon = float(best["lat"]), float(best["lon"])
                    how = f"fuzzy_{best_score:.2f}"
        if lat is None:
            if county in centroids.index:
                lat, lon = float(centroids.loc[county, "lat"]), float(centroids.loc[county, "lon"])
                how = "county_centroid"
            elif len(fac):
                lat, lon = float(fac.iloc[0]["lat"]), float(fac.iloc[0]["lon"])
                how = "global_fallback"
            else:
                lat, lon = 0.0, 37.0
                how = "zero"
        olat, olon = _offset_latlon(lat, lon, str(row.get("community_unit_name") or key))
        lats.append(olat)
        lons.append(olon)
        matched.append(how)
    chu["lat"] = lats
    chu["lon"] = lons
    chu["coord_match"] = matched
    return chu


def _merge_covariates_onto_chus(chu: pd.DataFrame, fac: pd.DataFrame) -> pd.DataFrame:
    """Copy county/sub-county covariates from a representative facility row."""
    chu = chu.copy()
    county_ind = load_county_indicators()
    # Prefer facility row in same sub_county, else county mean
    fac_cov = fac.copy()
    keep = [c for c in COVARIATE_COLS + ["county", "sub_county", "ward", "ward_population", "vulnerability_score"] if c in fac_cov.columns]
    fac_cov = fac_cov[keep]
    # county-level fill
    if len(county_ind):
        chu = chu.merge(county_ind, on="county", how="left", suffixes=("", "_ind"))
    # subcounty facility snapshot
    sub_cols = [c for c in ["county", "sub_county", "under5_share", "phc_access_1h_share",
                            "travel_friction_phc_1h", "flood_risk_flag", "distance_to_level3_km",
                            "ward_population", "vulnerability_score"] if c in fac_cov.columns]
    sub = (
        fac_cov[sub_cols]
        .groupby(["county", "sub_county"], as_index=False)
        .mean(numeric_only=True)
    )
    chu["sub_county_key"] = chu["sub_county"].astype(str).str.upper()
    sub["sub_county_key"] = sub["sub_county"].astype(str).str.upper()
    chu = chu.merge(
        sub.drop(columns=["sub_county"]),
        on=["county", "sub_county_key"],
        how="left",
        suffixes=("", "_sub"),
    )
    # fill blanks from subcounty snapshot
    for col in ["under5_share", "phc_access_1h_share", "travel_friction_phc_1h",
                "flood_risk_flag", "distance_to_level3_km", "ward_population", "vulnerability_score"]:
        src = f"{col}_sub"
        if src in chu.columns:
            if col not in chu.columns:
                chu[col] = chu[src]
            else:
                chu[col] = chu[col].fillna(chu[src])
    county_mean = fac_cov.groupby("county", as_index=False).mean(numeric_only=True)
    chu = chu.merge(county_mean, on="county", how="left", suffixes=("", "_cm"))
    for col in ["under5_share", "phc_access_1h_share", "travel_friction_phc_1h",
                "flood_risk_flag", "distance_to_level3_km", "ward_population", "vulnerability_score"]:
        src = f"{col}_cm"
        if src in chu.columns:
            if col not in chu.columns:
                chu[col] = chu[src]
            else:
                chu[col] = chu[col].fillna(chu[src])
    return chu


def county_community_units(county: str) -> pd.DataFrame:
    key = norm_county(county)
    chu = load_chu_frame()
    chu = chu[chu["county"] == key].copy()
    fac = county_facilities(key)
    if chu.empty:
        # Fall back: treat wards as demand nodes
        if fac.empty:
            return chu
        fake = fac.groupby("ward", as_index=False).first()
        fake = fake.rename(columns={"facility_name": "linked_facility_name"})
        fake["community_unit_name"] = fake["ward"].astype(str) + " Community Unit"
        fake["community_unit_code"] = fake.get("facility_code", range(len(fake)))
        chu = fake[["county", "sub_county", "ward", "community_unit_name",
                    "community_unit_code", "linked_facility_name"]].copy() if "sub_county" in fake.columns else fake
    chu = _attach_chu_coords(chu, fac)
    chu = _merge_covariates_onto_chus(chu, fac)
    return chu


def build_community_units(frame: pd.DataFrame) -> List[CommunityUnit]:
    units: List[CommunityUnit] = []
    for idx, row in frame.reset_index(drop=True).iterrows():
        cov = _row_covariates(row)
        pop = row.get("ward_population")
        if pd.isna(pop) or pop is None:
            pop = 8000
        vuln = row.get("vulnerability_score")
        if pd.isna(vuln) or vuln is None:
            vuln = 0.7
        terrain = str(cov.get("terrain_class") or row.get("terrain_class") or "arid")
        units.append(
            CommunityUnit(
                id=f"CU_{idx}_{_safe_int_id(row.get('community_unit_code'), idx)}",
                name=str(row.get("community_unit_name") or f"CU {idx}"),
                county=str(row["county"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                population=int(pop),
                vulnerability_score=float(vuln),
                sub_county=str(row.get("sub_county") or ""),
                ward=str(row.get("ward") or ""),
                under5_share=float(cov.get("under5_share") or 0.15),
                terrain_class=terrain,
                phc_access_1h_share=float(cov.get("phc_access_1h_share") or 0.7),
                travel_friction_phc_1h=float(cov.get("travel_friction_phc_1h") or 0.3),
                stunting_u5_pct=_opt(cov.get("stunting_u5_pct")),
                wasting_u5_pct=_opt(cov.get("wasting_u5_pct")),
                underweight_u5_pct=_opt(cov.get("underweight_u5_pct")),
                facility_delivery_pct=_opt(cov.get("facility_delivery_pct")),
                skilled_delivery_pct=_opt(cov.get("skilled_delivery_pct")),
                anc4_pct=_opt(cov.get("anc4_pct")),
                maternal_risk_index=_opt(cov.get("maternal_risk_index")),
                hh_itn_ownership_pct=_opt(cov.get("hh_itn_ownership_pct")),
                malaria_itn_gap_pct=_opt(cov.get("malaria_itn_gap_pct")),
                ccri_malaria_pf_score=_opt(cov.get("ccri_malaria_pf_score")),
                ccri_riverine_flood_score=_opt(cov.get("ccri_riverine_flood_score")),
                ccri_drought_score=_opt(cov.get("ccri_drought_score")),
                ccri_food_insecurity_score=_opt(cov.get("ccri_food_insecurity_score")),
                ccri_child_nutrition_score=_opt(cov.get("ccri_child_nutrition_score")),
                ccri_maternal_health_score=_opt(cov.get("ccri_maternal_health_score")),
                ccri_risk_index=_opt(cov.get("ccri_risk_index")),
                flood_risk_flag=int(cov.get("flood_risk_flag") or 0),
                seasonal_mobility_flag=int(cov.get("seasonal_mobility_flag") or 0),
                poverty_overall_pct=_opt(cov.get("poverty_overall_pct")),
                distance_to_level3_km=float(cov.get("distance_to_level3_km") or 10.0),
            )
        )
    return units


def _opt(val: Any) -> Optional[float]:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def terrain_gamma(terrain_class: str) -> float:
    return TERRAIN_GAMMA.get((terrain_class or "arid").lower(), 1.35)
