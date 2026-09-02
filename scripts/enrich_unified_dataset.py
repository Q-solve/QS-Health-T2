#!/usr/bin/env python3
"""
enrich_unified_dataset.py

Enrich data/unified_chw_dataset.csv with verified public-source covariates only.
No synthetic / random fills: missing values stay empty (NaN).

Sources (see data/DATA_SOURCES.md):
  - KDHS 2022 county crosstab (Africa Data Hub / KNBS / DHS Program)
  - UNICEF CCRI-DRM Kenya v2.3 (HDX)
  - HeiGIT / HDX ADM2 demographics, flood exposure, PHC access
  - OCHA COD-AB Kenya admin boundaries (HDX)
  - KMHFR Community Health Units extract 2020 (openAFRICA)
  - State Department for ASALs aridity class
  - KNBS Kenya Poverty Report 2022 (published county rates only)
  - Primary Health Care Act 2023 + MoH CHP stipend policy
  - Derived: haversine distance to nearest Level-3+ facility in-county
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXT = DATA / "external_sources"
IN_CSV = DATA / "unified_chw_dataset.csv"
OUT_CSV = DATA / "unified_chw_dataset.csv"
OUT_CHU = DATA / "community_units_kmhfr.csv"
OUT_COUNTY = DATA / "county_verified_indicators.csv"
OUT_SOURCES = DATA / "DATA_SOURCES.md"

TARGET_COUNTIES = [
    "TURKANA", "GARISSA", "MANDERA", "KILIFI", "WAJIR",
    "TAITA TAVETA", "MARSABIT", "ISIOLO", "SAMBURU", "LAMU",
    "WEST POKOT", "TANA RIVER", "NAROK", "KWALE",
]

# Official ASAL aridity class (State Department for ASALs / MoALF ASAL list)
TERRAIN_CLASS = {
    "TURKANA": "arid", "GARISSA": "arid", "MANDERA": "arid", "WAJIR": "arid",
    "MARSABIT": "arid", "ISIOLO": "arid", "SAMBURU": "arid", "TANA RIVER": "arid",
    "WEST POKOT": "semi_arid", "KILIFI": "semi_arid", "KWALE": "semi_arid",
    "LAMU": "semi_arid", "NAROK": "semi_arid", "TAITA TAVETA": "semi_arid",
}
# Pastoral seasonal mobility common in arid ASAL counties
MOBILITY_FLAG = {c: (1 if TERRAIN_CLASS[c] == "arid" else 0) for c in TARGET_COUNTIES}

# KNBS Kenya Poverty Report 2022 — overall poverty headcount % (individuals).
# Only counties with an explicitly published rate are filled; others left blank.
POVERTY_OVERALL_PCT = {
    "TURKANA": 82.7, "MANDERA": 72.9, "SAMBURU": 71.9, "GARISSA": 67.8,
    "TANA RIVER": 66.7, "MARSABIT": 66.1, "WAJIR": 64.7, "NAROK": 26.2,
}

# Official CHP stipend (KES/month). National + county 50/50 co-finance under PHC Act 2023.
# Commonly reported total: 5,000. Leave as a constant national policy variable.
CHW_MONTHLY_STIPEND_KES = 5000

KDHS_NAME_TO_KEY = {
    "Turkana": "TURKANA", "Garissa": "GARISSA", "Mandera": "MANDERA",
    "Kilifi": "KILIFI", "Wajir": "WAJIR", "Taita/Taveta": "TAITA TAVETA",
    "Marsabit": "MARSABIT", "Isiolo": "ISIOLO", "Samburu": "SAMBURU",
    "Lamu": "LAMU", "West Pokot": "WEST POKOT", "Tana River": "TANA RIVER",
    "Narok": "NAROK", "Kwale": "KWALE",
}


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


def norm_admin(x: str) -> str:
    s = str(x or "").upper().replace("-", " ").replace("/", " ").replace("'", "")
    return re.sub(r"\s+", " ", s).strip()


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def extract_kdhs_county_table() -> pd.DataFrame:
    path = EXT / "kdhscountycrosstab.xlsx"
    raw = pd.read_excel(path)
    raw["Characteristics"] = raw["Characteristics"].astype(str).str.strip()

    specs = [
        ("10C", "Percentage of live births in the 2 years preceding the survey delivered in a health facility", "facility_delivery_pct"),
        ("10C", "Percentage of live births in the 2 years preceding the survey delivered by a skilled provider", "skilled_delivery_pct"),
        ("10C", "Percentage of women aged 15-49 who had a live birth in the 2 years preceding the survey receiving antenatal care from skilled provider", "anc_skilled_pct"),
        ("10C", "Percentage of women aged 15-49 who had a live birth in the 2 years preceding the survey with 4+ ANC visits", "anc4_pct"),
        ("14C", "Percentage of children under age 5 with Height-for-age below −2 SD", "stunting_u5_pct"),
        ("14C", "Percentage of children under age 5 with Weight-for-height  below −2 SD", "wasting_u5_pct"),
        ("14C", "Percentage of children under age 5 with Weight-for-age  below −2 SD", "underweight_u5_pct"),
        ("18C", "Percentage of households with at least one ITN", "hh_itn_ownership_pct"),
    ]

    out = {k: {} for k in TARGET_COUNTIES}
    for table, respondent, col in specs:
        sub = raw[
            (raw["Table Number"].astype(str) == table)
            & (raw["Respondents"].astype(str).str.strip() == respondent)
        ]
        for _, row in sub.iterrows():
            key = KDHS_NAME_TO_KEY.get(row["Characteristics"])
            if not key:
                continue
            try:
                out[key][col] = float(row["Number"])
            except (TypeError, ValueError):
                pass

    # Maternal risk proxy: complement of facility delivery (higher = worse access risk)
    rows = []
    for county in TARGET_COUNTIES:
        d = out[county]
        fac = d.get("facility_delivery_pct")
        d["maternal_risk_index"] = round(100.0 - fac, 2) if fac is not None else np.nan
        # Malaria exposure proxy at county: ITN ownership gap (100 - ownership)
        itn = d.get("hh_itn_ownership_pct")
        d["malaria_itn_gap_pct"] = round(100.0 - itn, 2) if itn is not None else np.nan
        rows.append({"county": county, **d})
    return pd.DataFrame(rows)


def extract_ccri() -> pd.DataFrame:
    ccri = pd.read_excel(EXT / "Kenya_CCRIDRM_Model_v2.3.xlsx", sheet_name="Kenya CCRI-DRM")
    ccri = ccri.dropna(subset=["County Name"]).copy()
    ccri["county"] = ccri["County Name"].map(norm_county)
    rename = {
        "Malaria PF": "ccri_malaria_pf_score",
        "Riverine floods": "ccri_riverine_flood_score",
        "At least moderate drought": "ccri_drought_score",
        "Acute food insecurity": "ccri_food_insecurity_score",
        "Child nutrition": "ccri_child_nutrition_score",
        "Maternal health": "ccri_maternal_health_score",
        "Children's Climate and Disaster Risk Index": "ccri_risk_index",
    }
    frame = ccri.copy()
    frame["county"] = frame["County Name"].map(norm_county)
    present = [k for k in rename if k in frame.columns]
    frame = frame[["county"] + present].rename(columns={k: rename[k] for k in present})
    frame = frame[frame["county"].isin(TARGET_COUNTIES)].drop_duplicates("county")
    return frame


def build_adm2_join() -> pd.DataFrame:
    admin2 = pd.read_excel(EXT / "cod_ken_admin_boundaries.xlsx", sheet_name="ken_admin2")
    admin2["county"] = admin2["adm1_name"].map(norm_county)
    admin2["subcounty_key"] = admin2["adm2_name"].map(norm_admin)
    admin2 = admin2[admin2["county"].isin(TARGET_COUNTIES)][
        ["adm2_pcode", "adm2_name", "county", "subcounty_key", "area_sqkm"]
    ].copy()

    demo = pd.read_csv(EXT / "KEN_ADM2_demographics.csv")
    flood = pd.read_csv(EXT / "KEN_ADM2_flood_exposure.csv")
    access_path = next(EXT.glob("*access*.csv*"))
    access = pd.read_csv(access_path)

    demo = demo.rename(columns={"ADM2_PCODE": "adm2_pcode"})
    flood = flood.rename(columns={"ADM2_PCODE": "adm2_pcode"})
    access = access.rename(columns={"ADM2_PCODE": "adm2_pcode"})

    # Prefer RP100 flood columns if present, else RP10
    flood_child_col = next(
        (c for c in ["RP100_children_u5_30cm", "RP10_children_u5_30cm"] if c in flood.columns),
        None,
    )
    flood_keep = ["adm2_pcode"]
    if flood_child_col:
        flood_keep.append(flood_child_col)

    m = admin2.merge(demo, on="adm2_pcode", how="left")
    m = m.merge(flood[flood_keep], on="adm2_pcode", how="left")
    m = m.merge(
        access[["adm2_pcode", "access_pop_primary_healthcare_1h", "access_pop_hospitals_1h"]],
        on="adm2_pcode",
        how="left",
    )

    m["under5_share"] = m["children_u5"] / m["total_pop"]
    if flood_child_col:
        m["flood_u5_exposed"] = m[flood_child_col]
        m["flood_risk_flag"] = (m["flood_u5_exposed"].fillna(0) > 0).astype(int)
    else:
        m["flood_u5_exposed"] = np.nan
        m["flood_risk_flag"] = np.nan

    # Travel friction proxy: share of population NOT within 1h of PHC (HDX/ORS)
    m["travel_friction_phc_1h"] = 1.0 - (m["access_pop_primary_healthcare_1h"] / m["total_pop"]).clip(0, 1)
    # Road/access density proxy: PHC access share within 1h
    m["phc_access_1h_share"] = (m["access_pop_primary_healthcare_1h"] / m["total_pop"]).clip(0, 1)
    return m


def match_adm2(fac: pd.DataFrame, adm2: pd.DataFrame) -> pd.DataFrame:
    """Attach ADM2 covariates by normalized sub_county name within county."""
    fac = fac.copy()
    # Re-enrichment: drop previous ADM2 columns so merges don't suffix-clash
    drop_prior = [
        "under5_share", "flood_risk_flag", "flood_u5_exposed", "travel_friction_phc_1h",
        "phc_access_1h_share", "adm2_match_level", "adm2_pcode", "adm2_name",
        "children_u5", "total_pop", "area_sqkm", "county_key", "subcounty_key",
    ]
    fac = fac.drop(columns=[c for c in drop_prior if c in fac.columns], errors="ignore")
    fac["county_key"] = fac["county"].map(norm_county)
    fac["subcounty_key"] = fac["sub_county"].map(norm_admin)

    # exact match
    adm2_join = adm2.rename(columns={"county": "county_key"})[[
        "county_key", "subcounty_key", "under5_share", "children_u5", "total_pop",
        "flood_risk_flag", "flood_u5_exposed", "travel_friction_phc_1h",
        "phc_access_1h_share", "area_sqkm", "adm2_pcode", "adm2_name",
    ]]
    exact = fac.merge(adm2_join, on=["county_key", "subcounty_key"], how="left")
    # county-mean fallback for unmatched rows only
    county_mean = (
        adm2.groupby("county", as_index=False)
        .agg(
            under5_share=("under5_share", "mean"),
            flood_risk_flag=("flood_risk_flag", "max"),
            travel_friction_phc_1h=("travel_friction_phc_1h", "mean"),
            phc_access_1h_share=("phc_access_1h_share", "mean"),
        )
        .rename(columns={"county": "county_key"})
    )
    miss = exact["under5_share"].isna()
    exact["adm2_match_level"] = np.where(miss, "county_mean", "subcounty_exact")
    if miss.any():
        fb = exact.loc[miss, ["county_key"]].merge(county_mean, on="county_key", how="left")
        for c in ["under5_share", "flood_risk_flag", "travel_friction_phc_1h", "phc_access_1h_share"]:
            exact.loc[miss, c] = fb[c].values
    return exact


def add_distance_to_level3(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    level3 = df[df["keph_level"].isin(["Level 3", "Level 4", "Level 5", "Level 6"])].copy()
    dists = []
    for _, row in df.iterrows():
        lat, lon = row["lat"], row["lon"]
        if pd.isna(lat) or pd.isna(lon):
            dists.append(np.nan)
            continue
        cand = level3[level3["county"] == row["county"]]
        if cand.empty:
            cand = level3
        if cand.empty:
            dists.append(np.nan)
            continue
        best = min(
            haversine_km(lat, lon, float(r.lat), float(r.lon))
            for r in cand.itertuples()
        )
        dists.append(round(best, 3))
    df["distance_to_level3_km"] = dists
    return df


def export_community_units() -> pd.DataFrame:
    chu = pd.read_csv(EXT / "kenya_community_health_units_2020.csv")
    chu["county"] = chu["Facility_county"].map(norm_county)
    chu = chu[chu["county"].isin(TARGET_COUNTIES)].copy()
    chu = chu.rename(columns={
        "Name": "community_unit_name",
        "Code": "community_unit_code",
        "Status": "chu_status",
        "Facility": "linked_facility_name",
        "Facility_ward": "ward",
        "Facility_subcounty": "sub_county",
        "Facility_constituency": "constituency",
        "Date_established": "date_established_excel",
    })
    chu = chu[[
        "county", "sub_county", "constituency", "ward",
        "community_unit_name", "community_unit_code", "chu_status",
        "linked_facility_name", "date_established_excel",
    ]]
    chu["source"] = "KMHFR via openAFRICA (2020 extract)"
    chu.to_csv(OUT_CHU, index=False)
    return chu


def attach_chu_counts(fac: pd.DataFrame, chu: pd.DataFrame) -> pd.DataFrame:
    """Count verified CHUs linked to each facility by fuzzy-normalized name within county."""
    fac = fac.copy()

    def fac_key(name: str) -> str:
        s = norm_admin(name)
        for tok in ["DISPENSARY", "HEALTH CENTRE", "HEALTH CENTER", "HOSPITAL",
                    "MEDICAL CLINIC", "CLINIC", "MEDICAL CENTER", "MEDICAL CENTRE"]:
            s = s.replace(tok, "")
        return re.sub(r"\s+", " ", s).strip()

    chu = chu.copy()
    chu["link_key"] = chu["linked_facility_name"].map(fac_key)
    counts = (
        chu.groupby(["county", "link_key"], as_index=False)
        .size()
        .rename(columns={"size": "linked_chu_count"})
    )
    fac["link_key"] = fac["facility_name"].map(fac_key)
    fac = fac.merge(counts, on=["county", "link_key"], how="left")
    fac["linked_chu_count"] = fac["linked_chu_count"].fillna(0).astype(int)
    fac = fac.drop(columns=["link_key"])
    return fac


def write_sources_md(n_fac: int, n_chu: int, county_df: pd.DataFrame) -> None:
    text = f"""# Verified data sources for dataset enrichment

Generated by `scripts/enrich_unified_dataset.py`.
**Policy: only verified public values are written. Missing values are left blank (never imputed with random/fake numbers).**

## Outputs

| File | Rows | Role |
|------|------|------|
| `data/unified_chw_dataset.csv` | {n_fac} facilities | Enriched facility matrix |
| `data/community_units_kmhfr.csv` | {n_chu} CHUs | Explicit community units (problem-size expansion) |
| `data/county_verified_indicators.csv` | {len(county_df)} counties | County-level KDHS/CCRI/poverty lookup |

## Variables added to `unified_chw_dataset.csv`

| Variable | Grain | Source | Notes |
|----------|-------|--------|-------|
| `under5_share` | sub-county (ADM2), county-mean fallback | HeiGIT HDX `KEN_ADM2_demographics` + WorldPop | children_u5 / total_pop |
| `distance_to_level3_km` | facility | Derived from this dataset (KMHFR/OSM facilities) | Haversine to nearest Level 3+ in county |
| `terrain_class` | county | State Department for ASALs / MoALF ASAL list | `arid` or `semi_arid` |
| `phc_access_1h_share` | sub-county | HDX risk-assessment access (openrouteservice) | Share of pop within 1h of PHC |
| `travel_friction_phc_1h` | sub-county | Derived = 1 − phc_access_1h_share | Travel-friction proxy (not raw OSM km/km²) |
| `stunting_u5_pct` | county | KDHS 2022 Table 14C | Height-for-age < −2 SD |
| `wasting_u5_pct` | county | KDHS 2022 Table 14C | Weight-for-height < −2 SD |
| `underweight_u5_pct` | county | KDHS 2022 Table 14C | Weight-for-age < −2 SD |
| `facility_delivery_pct` | county | KDHS 2022 Table 10C | Maternal access |
| `skilled_delivery_pct` | county | KDHS 2022 Table 10C | Maternal access |
| `anc_skilled_pct` / `anc4_pct` | county | KDHS 2022 Table 10C | Antenatal care |
| `maternal_risk_index` | county | Derived = 100 − facility_delivery_pct | Higher = worse facility delivery |
| `hh_itn_ownership_pct` | county | KDHS 2022 Table 18C | Malaria prevention coverage |
| `malaria_itn_gap_pct` | county | Derived = 100 − ITN ownership | Malaria protection gap |
| `ccri_malaria_pf_score` | county | UNICEF CCRI-DRM Kenya v2.3 (HDX) | PF malaria child exposure score |
| `ccri_riverine_flood_score` | county | UNICEF CCRI-DRM Kenya v2.3 | Flood hazard score |
| `flood_risk_flag` | sub-county | HDX `KEN_ADM2_flood_exposure` | 1 if any U5 exposed at 30 cm flood depth |
| `seasonal_mobility_flag` | county | ASAL arid pastoral classification | 1 for arid pastoral counties |
| `poverty_overall_pct` | county | KNBS Kenya Poverty Report 2022 | **Only published county rates**; blanks where unpublished |
| `chw_monthly_stipend_kes` | national constant | PHC Act 2023 + MoH CHP stipend policy | 5000 KES/month (50/50 national–county) |
| `linked_chu_count` | facility | KMHFR CHU extract 2020 (openAFRICA) | Count of CHUs naming this facility |
| `real_chw_headcount` | — | **Not publicly available at facility/ward grain** | Left blank (national total 107,831 CHPs is documented, not allocated) |

## Explicit community units

`community_units_kmhfr.csv` lists **{n_chu}** Community Health Units in the 14 target counties from the Kenya Master Health Facility Registry (2020 open extract). Use these rows as demand nodes (C) to expand N = F × C for classical stress tests.

Live registry (browse only; API timed out from this environment): https://kmhfr.health.go.ke/public/chu (~11,680 CHUs nationally).

## Source URLs

1. KDHS 2022 county crosstab — https://ckan.africadatahub.org/dataset/kenya-demographic-and-health-survey-2022  
2. KDHS county fact sheets — https://www.dhsprogram.com/publications/publication-GF57-General-Fact-Sheets.cfm  
3. UNICEF CCRI-DRM Kenya — https://data.humdata.org/dataset/kenya-children-s-climate-risk-index-disaster-risk-model-ccri-drm-subnational-risk-assessment  
4. HDX risk assessment indicators (demographics / flood / access) — https://data.humdata.org/dataset/kenya---risk-assessment-indicators  
5. OCHA COD-AB Kenya — https://data.humdata.org/dataset/cod-ab-ken  
6. KMHFR CHUs (openAFRICA 2020) — https://open.africa/dataset/kenya-master-health-facility-list-2020  
7. KNBS Poverty Report 2022 — https://www.knbs.or.ke/reports/kenya-poverty-report-2022/  
8. Primary Health Care Act, 2023 (stipend mandate) — https://www.pck.go.ke/sites/default/files/PCK/Resouces/The%20Primary%20Health%20Act%2C%202023.pdf  

## Intentionally NOT fabricated

- Ward-level DHS malaria/nutrition/maternal rates (KDHS is county-representative only)
- Per-facility or per-county CHP payroll headcounts (MoH eCHIS registry is not an open bulk dump)
- Raw OSM road-km density (not downloaded here); use `travel_friction_phc_1h` / `phc_access_1h_share` instead
- Poverty rates for counties not listed with an explicit figure in the KNBS 2022 release summary
"""
    OUT_SOURCES.write_text(text)


def main() -> None:
    assert IN_CSV.exists(), f"Missing {IN_CSV}"
    fac = pd.read_csv(IN_CSV)
    base_cols = list(fac.columns)

    kdhs = extract_kdhs_county_table()
    ccri = extract_ccri()
    county = kdhs.merge(ccri, on="county", how="left")
    county["terrain_class"] = county["county"].map(TERRAIN_CLASS)
    county["seasonal_mobility_flag"] = county["county"].map(MOBILITY_FLAG)
    county["poverty_overall_pct"] = county["county"].map(POVERTY_OVERALL_PCT)
    county["chw_monthly_stipend_kes"] = CHW_MONTHLY_STIPEND_KES
    county["real_chw_headcount"] = np.nan  # not available at county open-data grain
    county.to_csv(OUT_COUNTY, index=False)

    adm2 = build_adm2_join()
    fac = match_adm2(fac, adm2)
    fac = add_distance_to_level3(fac)

    # Merge county indicators (avoid duplicate county column)
    if "county_key" not in fac.columns:
        fac["county_key"] = fac["county"].map(norm_county)
    county_join = county.rename(columns={"county": "county_key"})
    fac = fac.merge(county_join, on="county_key", how="left", suffixes=("", "_dup"))
    dup_cols = [c for c in fac.columns if c.endswith("_dup")]
    if dup_cols:
        fac = fac.drop(columns=dup_cols)
    fac["chw_monthly_stipend_kes"] = CHW_MONTHLY_STIPEND_KES
    fac["real_chw_headcount"] = np.nan
    fac["terrain_class"] = fac["county_key"].map(TERRAIN_CLASS)
    fac["seasonal_mobility_flag"] = fac["county_key"].map(MOBILITY_FLAG)

    chu = export_community_units()
    fac = attach_chu_counts(fac, chu)

    # Column order: original + new enrichment fields
    new_cols = [
        "under5_share", "distance_to_level3_km", "terrain_class",
        "phc_access_1h_share", "travel_friction_phc_1h",
        "stunting_u5_pct", "wasting_u5_pct", "underweight_u5_pct",
        "facility_delivery_pct", "skilled_delivery_pct", "anc_skilled_pct", "anc4_pct",
        "maternal_risk_index", "hh_itn_ownership_pct", "malaria_itn_gap_pct",
        "ccri_malaria_pf_score", "ccri_riverine_flood_score", "ccri_drought_score",
        "ccri_food_insecurity_score", "ccri_child_nutrition_score",
        "ccri_maternal_health_score", "ccri_risk_index",
        "flood_risk_flag", "seasonal_mobility_flag",
        "poverty_overall_pct", "chw_monthly_stipend_kes",
        "linked_chu_count", "real_chw_headcount",
        "adm2_match_level", "adm2_pcode", "adm2_name",
    ]
    # Keep first occurrence of base cols
    keep = []
    seen = set()
    for c in base_cols + new_cols:
        if c in fac.columns and c not in seen:
            keep.append(c)
            seen.add(c)
    fac_out = fac[keep]
    fac_out.to_csv(OUT_CSV, index=False)

    write_sources_md(len(fac_out), len(chu), county)

    matched = (fac_out.get("adm2_match_level") == "subcounty_exact").sum()
    print(f"Facilities enriched: {len(fac_out)}")
    print(f"ADM2 exact matches: {matched} / {len(fac_out)}")
    print(f"Community units exported: {len(chu)}")
    print(f"County indicator rows: {len(county)}")
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_CHU}")
    print(f"Wrote {OUT_COUNTY}")
    print(f"Wrote {OUT_SOURCES}")
    print("Non-null rates for key new columns:")
    for c in ["under5_share", "distance_to_level3_km", "stunting_u5_pct",
              "ccri_malaria_pf_score", "poverty_overall_pct", "linked_chu_count",
              "real_chw_headcount", "flood_risk_flag"]:
        if c in fac_out.columns:
            nn = fac_out[c].notna().mean() * 100
            print(f"  {c}: {nn:.1f}% non-null")


if __name__ == "__main__":
    main()
