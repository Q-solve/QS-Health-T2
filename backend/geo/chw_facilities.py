"""
KMHFR Health Facility & Rural Community Unit distance helpers.

Walking distance is terrain-adjusted using the community's verified covariates:
arid/semi-arid gamma, PHC travel friction, flood isolation, seasonal mobility.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great Circle distance in km between two geo points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def terrain_gamma(terrain_class: str) -> float:
    t = (terrain_class or "arid").lower()
    if t in {"arid"}:
        return 1.40
    if t in {"semi_arid", "semi-arid", "hilly", "coastal"}:
        return 1.30
    return 1.35


def walking_multiplier(
    terrain_class: str = "arid",
    travel_friction: float = 0.0,
    flood_flag: int = 0,
    mobility_flag: int = 0,
) -> float:
    """
    Convert haversine to walking-equivalent km.
    Friction ∈ [0,1] from 1h PHC access gap; flags are 0/1.
    """
    gamma = terrain_gamma(terrain_class)
    friction = max(0.0, min(1.0, float(travel_friction or 0.0)))
    flood = 1.0 if int(flood_flag or 0) else 0.0
    mobility = 1.0 if int(mobility_flag or 0) else 0.0
    return gamma * (1.0 + 0.45 * friction) * (1.0 + 0.20 * flood) * (1.0 + 0.12 * mobility)


def calculate_walking_distance_matrix(
    facilities: List[Dict[str, Any]],
    communities: List[Dict[str, Any]],
    terrain_factor: float = 1.6,
) -> Dict[Tuple[str, str], float]:
    """
    Walking travel matrix (km) between facilities and community units.

    If a community carries terrain/friction/flood/mobility fields those are
    used per pair; otherwise `terrain_factor` is the uniform fallback (legacy).
    """
    matrix = {}
    for f in facilities:
        f_id = f["id"]
        f_lat, f_lon = f["lat"], f["lon"]
        for c in communities:
            c_id = c["id"]
            direct_km = haversine_distance_km(f_lat, f_lon, c["lat"], c["lon"])
            if any(k in c for k in ("terrain_class", "travel_friction_phc_1h", "flood_risk_flag")):
                mult = walking_multiplier(
                    terrain_class=c.get("terrain_class") or f.get("terrain_class") or "arid",
                    travel_friction=c.get("travel_friction_phc_1h", 0.0) or 0.0,
                    flood_flag=int(c.get("flood_risk_flag") or 0),
                    mobility_flag=int(c.get("seasonal_mobility_flag") or 0),
                )
            else:
                mult = terrain_factor
            matrix[(f_id, c_id)] = round(direct_km * mult, 2)
    return matrix
