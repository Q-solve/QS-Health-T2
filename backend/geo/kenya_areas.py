"""Kenya administrative areas + approximate county centroids for mapping."""

from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any

import httpx

from backend import config

# Public key documented at https://kenyaareadata.vercel.app/
KENYA_AREAS_BASE = "https://kenyaareadata.vercel.app/api/areas"
KENYA_AREAS_API_KEY = getattr(config, "KENYA_AREAS_API_KEY", "") or ""

# Approximate geographic centroids (lat, lon) for Kenya's 47 counties.
# Used because the Areas API returns hierarchy names only, not coordinates.
COUNTY_CENTROIDS: dict[str, tuple[float, float]] = {
    "Mombasa": (-4.0435, 39.6682),
    "Kwale": (-4.1740, 39.4521),
    "Kilifi": (-3.6300, 39.8500),
    "Tana River": (-1.5000, 40.0000),
    "Lamu": (-2.2717, 40.9020),
    "Taita Taveta": (-3.4000, 38.5000),
    "Garissa": (-0.4536, 39.6461),
    "Wajir": (1.7471, 40.0573),
    "Mandera": (3.9373, 41.8569),
    "Marsabit": (2.3340, 37.9900),
    "Isiolo": (0.3556, 37.5833),
    "Meru": (0.0463, 37.6559),
    "Tharaka-Nithi": (-0.3000, 37.9000),
    "Embu": (-0.5390, 37.4580),
    "Kitui": (-1.3750, 38.0100),
    "Machakos": (-1.5177, 37.2634),
    "Makueni": (-1.8030, 37.6240),
    "Nyandarua": (-0.3000, 36.4500),
    "Nyeri": (-0.4167, 36.9500),
    "Kirinyaga": (-0.6590, 37.3830),
    "Murang'a": (-0.7830, 37.0500),
    "Kiambu": (-1.1710, 36.8350),
    "Turkana": (3.3120, 35.5650),
    "West Pokot": (1.6200, 35.3000),
    "Samburu": (1.2000, 36.9500),
    "Trans Nzoia": (1.0500, 34.9500),
    "Uasin Gishu": (0.5200, 35.2700),
    "Elgeyo-Marakwet": (0.8000, 35.5000),
    "Nandi": (0.2000, 35.1000),
    "Baringo": (0.6700, 35.9700),
    "Laikipia": (0.3600, 36.7800),
    "Nakuru": (-0.3031, 36.0800),
    "Narok": (-1.0800, 35.8700),
    "Kajiado": (-1.8500, 36.7800),
    "Kericho": (-0.3690, 35.2830),
    "Bomet": (-0.7800, 35.3400),
    "Kakamega": (0.2827, 34.7519),
    "Vihiga": (0.0800, 34.7200),
    "Bungoma": (0.5700, 34.5600),
    "Busia": (0.4600, 34.1200),
    "Siaya": (0.0600, 34.2900),
    "Kisumu": (-0.0917, 34.7680),
    "Homa Bay": (-0.5300, 34.4600),
    "Migori": (-1.0700, 34.4700),
    "Kisii": (-0.6800, 34.7700),
    "Nyamira": (-0.5700, 34.9400),
    "Nairobi": (-1.2921, 36.8219),
}

# Alias normalizations for common spelling variants from the API.
_COUNTY_ALIASES: dict[str, str] = {
    "Muranga": "Murang'a",
    "Murang’a": "Murang'a",
    "Tharaka Nithi": "Tharaka-Nithi",
    "Elgeyo Marakwet": "Elgeyo-Marakwet",
    "Taita/Taveta": "Taita Taveta",
}


_cache: dict[str, Any] = {"ts": 0.0, "areas": None}
_CACHE_TTL_S = 3600.0


def normalize_county_name(name: str) -> str:
    name = (name or "").strip()
    if name in COUNTY_CENTROIDS:
        return name
    if name in _COUNTY_ALIASES:
        return _COUNTY_ALIASES[name]
    # Case-insensitive match
    lower = {k.lower(): k for k in COUNTY_CENTROIDS}
    if name.lower() in lower:
        return lower[name.lower()]
    return name


def county_centroid(name: str) -> tuple[float, float] | None:
    key = normalize_county_name(name)
    return COUNTY_CENTROIDS.get(key)


def fetch_kenya_areas(*, force: bool = False) -> dict[str, Any]:
    """
    Fetch county → constituency → wards from Kenya Data API.
    Falls back to centroid keys if the network/API is unavailable.
    """
    now = time.time()
    if (
        not force
        and _cache["areas"] is not None
        and now - float(_cache["ts"]) < _CACHE_TTL_S
    ):
        return _cache["areas"]  # type: ignore[return-value]

    url = f"{KENYA_AREAS_BASE}?apiKey={KENYA_AREAS_API_KEY}"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data:
                _cache["areas"] = data
                _cache["ts"] = now
                return data
    except Exception:
        pass

    # Offline fallback: counties only (no constituency detail).
    fallback = {name: {} for name in sorted(COUNTY_CENTROIDS)}
    _cache["areas"] = fallback
    _cache["ts"] = now
    return fallback


def list_counties() -> list[dict[str, Any]]:
    areas = fetch_kenya_areas()
    items: list[dict[str, Any]] = []
    for name in sorted(areas.keys()):
        norm = normalize_county_name(name)
        centroid = county_centroid(norm)
        constituencies = areas[name] if isinstance(areas[name], dict) else {}
        items.append(
            {
                "name": norm,
                "api_name": name,
                "lat": centroid[0] if centroid else None,
                "lon": centroid[1] if centroid else None,
                "num_constituencies": len(constituencies),
                "constituencies": sorted(constituencies.keys()) if constituencies else [],
            }
        )
    # Ensure centroid-only counties missing from a partial API response still appear.
    known = {i["name"] for i in items}
    for name, (lat, lon) in COUNTY_CENTROIDS.items():
        if name not in known:
            items.append(
                {
                    "name": name,
                    "api_name": name,
                    "lat": lat,
                    "lon": lon,
                    "num_constituencies": 0,
                    "constituencies": [],
                }
            )
    items.sort(key=lambda x: x["name"])
    return items


def county_detail(county: str) -> dict[str, Any] | None:
    areas = fetch_kenya_areas()
    target = normalize_county_name(county)
    # Match API key case-insensitively
    api_key = None
    for k in areas:
        if normalize_county_name(k) == target:
            api_key = k
            break
    if api_key is None:
        if target in COUNTY_CENTROIDS:
            lat, lon = COUNTY_CENTROIDS[target]
            return {
                "name": target,
                "lat": lat,
                "lon": lon,
                "constituencies": {},
            }
        return None
    centroid = county_centroid(target)
    return {
        "name": target,
        "lat": centroid[0] if centroid else None,
        "lon": centroid[1] if centroid else None,
        "constituencies": areas[api_key],
    }
