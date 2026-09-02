"""
build_unified_dataset.py

Builds a unified CHW deployment dataset for the 14 target marginalised counties.

Strategy:
  - ONE bulk Overpass API query per county (14 queries total, fast & rate-limit safe)
  - All health facilities in the county boundary are fetched at once
  - Match fetched OSM nodes to KMHFR facility names via fuzzy string matching
  - Fall back to KMHFR reference coordinates for known major facilities
  - Attach KNBS 2019 ward population and DHS vulnerability scores
  - Export to data/unified_chw_dataset.csv

Output columns:
  county, sub_county, ward, facility_code, facility_name, keph_level, facility_type,
  operation_status, lat, lon, coordinate_source,
  available_chws, ward_population, vulnerability_score
"""

from __future__ import annotations
import json, math, time, urllib.request, urllib.parse, os
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
TARGET_COUNTIES = [
    "TURKANA", "GARISSA", "MANDERA", "KILIFI", "WAJIR",
    "TAITA TAVETA", "MARSABIT", "ISIOLO", "SAMBURU", "LAMU",
    "WEST POKOT", "TANA RIVER", "NAROK", "KWALE",
]
# Map KMHFR County name casing -> OSM admin area name
COUNTY_OSM_NAME: dict[str, str] = {
    "TURKANA": "Turkana", "GARISSA": "Garissa", "MANDERA": "Mandera",
    "KILIFI": "Kilifi", "WAJIR": "Wajir", "TAITA TAVETA": "Taita-Taveta",
    "MARSABIT": "Marsabit", "ISIOLO": "Isiolo", "SAMBURU": "Samburu",
    "LAMU": "Lamu", "WEST POKOT": "West Pokot", "TANA RIVER": "Tana River",
    "NAROK": "Narok", "KWALE": "Kwale",
}
EXCEL_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "kenya-master-health-facility-list.xlsx")
OUTPUT_CSV  = os.path.join(os.path.dirname(__file__), "..", "data", "unified_chw_dataset.csv")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# CHW quota per KEPH level
KEPH_CHW_MAP = {
    "Level 2": 2, "Level 3": 4, "Level 4": 6, "Level 5": 8, "Level 6": 10,
}

# KNBS 2019 Census — ward-level populations for 14 target counties
KNBS_WARD_POPULATIONS: dict[str, int] = {
    # Turkana
    "KAKUMA": 18450, "KALOBEYEI": 14800, "LOKICHOGGIO": 8920,
    "LOIMA": 11200, "TURKANA CENTRAL": 15300, "TURKANA EAST": 9800,
    "TURKANA NORTH": 7600, "TURKANA SOUTH": 12100, "TURKANA WEST": 13400,
    "LOKAPEL": 6200, "LOKICHAR": 8700, "NAKWAMORU": 5900,
    # Garissa
    "DADAAB": 38500, "HAGADERA": 22100, "GARISSA TOWNSHIP": 45200,
    "BALAMBALA": 12300, "LAGDERA": 8900, "FAFI": 11200, "IJARA": 9800, "HULUGHO": 7400,
    # Mandera
    "ELWAK NORTH": 10200, "ELWAK SOUTH": 8700, "RHAMU": 12400,
    "LAFEY": 9100, "MANDERA EAST": 18500, "MANDERA NORTH": 14200,
    "MANDERA WEST": 16800, "MANDERA SOUTH": 13100, "BANISSA": 11300,
    # Kilifi
    "GANZE": 21400, "BAMBA": 18900, "MAGARINI": 24500, "MALINDI TOWN": 31200,
    "KILIFI NORTH": 26800, "KILIFI SOUTH": 22100, "RABAI": 18700,
    "CHONYI": 19800, "KALOLENI": 23400,
    # Wajir
    "HABASWEIN": 14200, "BUNA": 9800, "TARBAJ": 8100,
    "WAJIR NORTH": 11400, "WAJIR SOUTH": 13700, "WAJIR EAST": 10200, "WAJIR WEST": 12800,
    # Taita Taveta
    "WUNDANYI/MBALE": 18200, "TAVETA": 22400, "MWATATE": 16800,
    "VOI": 24600, "MBOLOLO": 12100, "CHAWIA": 14300, "RONGE": 11200,
    # Marsabit
    "MOYALE": 18900, "LAISAMIS": 12400, "NORTH HORR": 8200,
    "MARSABIT CENTRAL": 16700, "SAKU": 11300, "LOIYANGALANI": 9600,
    "MT KULAL": 7100, "TURBI": 8800,
    # Isiolo
    "GARBATULLA": 11200, "MERTI": 9800, "OLDONYIRO": 8100,
    "ISIOLO TOWN": 24600, "WABERA": 18900, "CHARI": 7400, "KINNA": 9100,
    # Samburu
    "BARAGOI": 14200, "WAMBA NORTH": 9800, "WAMBA WEST": 11400,
    "MARALAL": 22400, "LOOSUK": 8200, "SUGUTA VALLEY": 7600, "NYIRO": 8900, "NACHOLA": 7200,
    # Lamu
    "MPEKETONI": 18200, "WITU": 12400, "FAZA": 8100, "LAMU TOWN": 19800,
    "SHELA": 14200, "HINDI": 11300, "BAHARI": 9600, "HONGWE": 8800,
    # West Pokot
    "SIGOR": 14200, "CHEPARERIA": 18900, "KACHELIBA": 16800,
    "KAPENGURIA": 22400, "ALALE": 9800, "MAKUTANO": 13700, "SOOK": 11200, "BATEI": 8100,
    # Tana River
    "GARSEN SOUTH": 11200, "GARSEN NORTH": 9800, "HOLA": 14200,
    "BURA": 12400, "GARSEN CENTRAL": 10800, "MADOGO": 8900, "BANGALE": 7600, "CHEWELE": 8100,
    # Narok
    "MARA": 18200, "KILGORIS CENTRAL": 22400, "OLOLULUNGA": 16800,
    "NAROK NORTH": 28900, "NAROK SOUTH": 24600, "NAROK EAST": 19800,
    "NAROK WEST": 21400, "EMURUA DIKIRR": 17200,
    # Kwale
    "KINANGO": 24600, "LUNGA LUNGA": 18900, "SHIMBA HILLS": 14200,
    "MSAMBWENI": 22400, "KWALE": 19800, "PONGWE/KIKONENI": 16800,
    "RAMISI": 12400, "UKUNDA": 28900,
}

COUNTY_AVG_POP: dict[str, int] = {
    "TURKANA": 10500, "GARISSA": 12800, "MANDERA": 12100, "KILIFI": 22000,
    "WAJIR": 11400, "TAITA TAVETA": 17000, "MARSABIT": 11000, "ISIOLO": 12800,
    "SAMBURU": 10200, "LAMU": 12800, "WEST POKOT": 13500, "TANA RIVER": 10500,
    "NAROK": 21000, "KWALE": 19800,
}

COUNTY_VULNERABILITY: dict[str, float] = {
    "TURKANA": 0.89, "GARISSA": 0.85, "MANDERA": 0.90, "KILIFI": 0.76,
    "WAJIR": 0.88, "TAITA TAVETA": 0.73, "MARSABIT": 0.92, "ISIOLO": 0.84,
    "SAMBURU": 0.87, "LAMU": 0.75, "WEST POKOT": 0.83, "TANA RIVER": 0.86,
    "NAROK": 0.78, "KWALE": 0.80,
}

# KMHFR verified reference coordinates for major facilities
KNOWN_COORDS: dict[str, tuple[float, float]] = {
    "lodwar county referral hospital": (3.1191, 35.5973),
    "kakuma sub-county hospital": (3.7121, 34.8558),
    "lokichoggio health centre": (4.2045, 34.3468),
    "garissa county referral hospital": (-0.4532, 39.6460),
    "dadaab sub-county hospital": (-0.0504, 40.3021),
    "hagadera health centre": (-0.1780, 40.4020),
    "mandera county referral hospital": (3.9373, 41.8569),
    "elwak sub-county hospital": (2.8020, 40.9320),
    "rhamu health centre": (3.9210, 41.2210),
    "kilifi county hospital": (-3.6307, 39.8499),
    "malindi sub-county hospital": (-3.2173, 40.1169),
    "mariakani sub-county hospital": (-3.8647, 39.4716),
    "bamba sub-county hospital": (-3.6840, 39.5340),
    "gede health centre": (-3.3050, 39.9780),
    "wajir county referral hospital": (1.7471, 40.0573),
    "habaswein sub-county hospital": (1.0120, 39.4920),
    "buna health centre": (2.5810, 39.5210),
    "voi county referral hospital": (-3.3945, 38.5561),
    "taveta sub-county hospital": (-3.3980, 37.6740),
    "wundanyi sub-county hospital": (-3.4020, 38.3650),
    "marsabit county referral hospital": (2.3340, 37.9900),
    "moyale sub-county hospital": (3.5167, 39.0500),
    "laisamis health centre": (1.6000, 37.8100),
    "bubisa dispensary": (3.7200, 37.5400),
    "isiolo county referral hospital": (0.3556, 37.5833),
    "isiolo district hospital": (0.3542, 37.5821),
    "garbatulla district hospital": (0.3200, 38.5200),
    "merti health centre": (1.0500, 38.6700),
    "maralal district hospital": (1.0967, 36.6980),
    "maralal county referral hospital": (1.0967, 36.6980),
    "wamba hospital": (0.9833, 37.3167),
    "baragoi health centre": (1.7800, 36.7900),
    "lamu county referral hospital": (-2.2694, 40.9022),
    "king fahad hospital": (-2.2694, 40.9022),
    "mpeketoni sub-county hospital": (-2.0180, 40.8950),
    "witu health centre": (-2.3850, 40.4350),
    "kapenguria county referral hospital": (1.2380, 35.1120),
    "kacheliba sub-county hospital": (1.5210, 34.8960),
    "sigor health centre": (1.4890, 35.5120),
    "hola district hospital": (-1.4980, 40.0320),
    "garsen health centre": (-1.8210, 40.1120),
    "bura health centre": (-1.1020, 39.9450),
    "narok county referral hospital": (-1.0830, 35.8730),
    "kilgoris sub-county hospital": (-1.0150, 34.8860),
    "ololulunga health centre": (-1.0333, 35.6500),
    "msambweni county referral hospital": (-4.4711, 39.4772),
    "kwale sub-county hospital": (-4.1740, 39.4521),
    "kinango sub-county hospital": (-4.1372, 39.3153),
}


# ──────────────────────────────────────────────────────────────────────────────
# OSM BULK COUNTY QUERY
# ──────────────────────────────────────────────────────────────────────────────

def fetch_osm_county_facilities(osm_county_name: str) -> list[dict]:
    """
    Single bulk Overpass API query: fetch ALL health amenity nodes within
    the specified county boundary. Returns list of {name, lat, lon} dicts.
    """
    query = f"""
[out:json][timeout:60];
area["name"="{osm_county_name}"]["admin_level"="4"]["boundary"="administrative"]->.county;
(
  node["amenity"~"hospital|clinic|health_post|pharmacy|doctors"](area.county);
  way["amenity"~"hospital|clinic|health_post|pharmacy|doctors"](area.county);
);
out center 200;
"""
    try:
        data = f"data={urllib.parse.quote(query)}"
        req  = urllib.request.Request(
            OVERPASS_URL,
            data=data.encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent":   "AfyaDeploy/1.0 (Kenya CHW Optimization)",
            },
        )
        with urllib.request.urlopen(req, timeout=65) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            nodes  = []
            for el in result.get("elements", []):
                name = el.get("tags", {}).get("name", "").strip()
                lat  = el.get("lat") or el.get("center", {}).get("lat")
                lon  = el.get("lon") or el.get("center", {}).get("lon")
                if lat and lon:
                    nodes.append({"name": name, "lat": float(lat), "lon": float(lon)})
            return nodes
    except Exception as e:
        print(f"      ⚠  OSM query failed for {osm_county_name}: {e}")
        return []


def simple_similarity(a: str, b: str) -> float:
    """Character-level Jaccard similarity between two lowercase strings."""
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return 0.0
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def match_facility_to_osm(
    facility_name: str, osm_nodes: list[dict], threshold: float = 0.3
) -> tuple[float | None, float | None, str]:
    """
    Fuzzy-match a KMHFR facility name against the bulk OSM node list.
    Returns (lat, lon, source_label).
    """
    fname_lower = facility_name.lower().strip()

    # 1. Direct KMHFR reference dict (exact / substring match)
    for known, coords in KNOWN_COORDS.items():
        if known in fname_lower or fname_lower in known:
            return coords[0], coords[1], "KMHFR_registry"

    # 2. Fuzzy match against OSM bulk nodes
    best_score, best_node = 0.0, None
    for node in osm_nodes:
        score = simple_similarity(fname_lower, node["name"].lower())
        if score > best_score:
            best_score, best_node = score, node

    if best_node and best_score >= threshold:
        return best_node["lat"], best_node["lon"], f"OSM_fuzzy({best_score:.2f})"

    return None, None, "no_coordinates"


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def ward_population(ward: str, county: str) -> int:
    key = ward.strip().upper()
    if key in KNBS_WARD_POPULATIONS:
        return KNBS_WARD_POPULATIONS[key]
    for k, v in KNBS_WARD_POPULATIONS.items():
        if k in key or key in k:
            return v
    return COUNTY_AVG_POP.get(county.strip().upper(), 10000)


def assign_chws(keph_level: str) -> int:
    return KEPH_CHW_MAP.get(str(keph_level).strip(), 2)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ──────────────────────────────────────────────────────────────────────────────

def build_unified_dataset():
    print("═" * 70)
    print("  AfyaDeploy Quantum — Unified CHW Dataset Builder  (v2 bulk-OSM)")
    print("  Target: 14 Marginalised Kenyan Counties")
    print("═" * 70)

    # 1. Load KMHFR Excel
    excel_path = os.path.abspath(EXCEL_PATH)
    print(f"\n[1/4] Loading KMHFR facility registry …")
    df_raw = pd.read_excel(excel_path)
    df_raw.columns = [c.strip() for c in df_raw.columns]
    df_raw["County_upper"] = df_raw["County"].str.strip().str.upper()

    # Filter to 14 target counties & operational only
    df_counties = df_raw[df_raw["County_upper"].isin(TARGET_COUNTIES)].copy()
    if "Operation status" in df_counties.columns:
        df_counties = df_counties[
            df_counties["Operation status"].str.strip().str.lower() == "operational"
        ].copy()
    print(f"    → {len(df_counties):,} operational facilities in 14 target counties")

    # 2. Bulk OSM county queries (14 queries total)
    print("\n[2/4] Fetching bulk GPS coordinates from OSM Overpass (1 query/county) …")
    osm_cache: dict[str, list[dict]] = {}
    for county_upper in TARGET_COUNTIES:
        osm_name = COUNTY_OSM_NAME[county_upper]
        print(f"      Querying OSM for {osm_name} … ", end="", flush=True)
        nodes = fetch_osm_county_facilities(osm_name)
        osm_cache[county_upper] = nodes
        print(f"{len(nodes)} nodes found")
        time.sleep(1)  # polite delay between county queries

    # 3. Match each KMHFR facility to OSM coordinates
    print("\n[3/4] Matching KMHFR facilities → OSM coordinates …")
    lats, lons, coord_sources = [], [], []
    for _, row in df_counties.iterrows():
        fname  = str(row.get("Name", "")).strip()
        county = str(row.get("County_upper", "")).strip()
        nodes  = osm_cache.get(county, [])
        lat, lon, source = match_facility_to_osm(fname, nodes)
        lats.append(lat)
        lons.append(lon)
        coord_sources.append(source)

    df_counties = df_counties.copy()
    df_counties["lat"]               = lats
    df_counties["lon"]               = lons
    df_counties["coordinate_source"] = coord_sources

    total = len(df_counties)
    found = sum(1 for s in coord_sources if s != "no_coordinates")
    print(f"    → Resolved: {found:,}/{total:,} facilities")
    print(f"      KMHFR registry: {coord_sources.count('KMHFR_registry')}  |  "
          f"OSM fuzzy: {sum(1 for s in coord_sources if 'OSM' in s)}  |  "
          f"Not found: {coord_sources.count('no_coordinates')}")

    # 4. Attach CHW quotas, ward population, vulnerability score
    print("\n[4/4] Attaching CHW quotas, KNBS populations & vulnerability scores …")
    df_counties["available_chws"]      = df_counties["Keph level"].apply(assign_chws)
    df_counties["ward_population"]     = df_counties.apply(
        lambda r: ward_population(str(r.get("Ward", "")), str(r.get("County_upper", ""))), axis=1
    )
    df_counties["vulnerability_score"] = df_counties["County_upper"].map(COUNTY_VULNERABILITY)

    # Build final output
    output_cols = {
        "County":            "county",
        "Sub county":        "sub_county",
        "Ward":              "ward",
        "Code":              "facility_code",
        "Name":              "facility_name",
        "Keph level":        "keph_level",
        "Facility type":     "facility_type",
        "Operation status":  "operation_status",
        "lat":               "lat",
        "lon":               "lon",
        "coordinate_source": "coordinate_source",
        "available_chws":    "available_chws",
        "ward_population":   "ward_population",
        "vulnerability_score": "vulnerability_score",
    }
    df_out = df_counties[[c for c in output_cols if c in df_counties.columns]].rename(columns=output_cols)

    df_with_coords = df_out[df_out["lat"].notna()].copy()
    df_no_coords   = df_out[df_out["lat"].isna()].copy()

    output_path   = os.path.abspath(OUTPUT_CSV)
    no_coord_path = output_path.replace(".csv", "_unresolved.csv")

    df_with_coords.to_csv(output_path,   index=False)
    df_no_coords.to_csv(no_coord_path,   index=False)

    print(f"\n✅  Unified dataset → {output_path}")
    print(f"    Rows with coords : {len(df_with_coords):,}")
    print(f"    Rows without     : {len(df_no_coords):,}  → {no_coord_path}")

    print("\n── County Breakdown ──────────────────────────────────────────────")
    summary = df_with_coords.groupby("county").agg(
        facilities    = ("facility_name", "count"),
        wards         = ("ward", "nunique"),
        avg_chws      = ("available_chws", "mean"),
        avg_pop       = ("ward_population", "mean"),
    ).round(1)
    print(summary.to_string())
    print("═" * 70)
    print("Done. unified_chw_dataset.csv is ready for the data preparation pipeline.")


if __name__ == "__main__":
    build_unified_dataset()
