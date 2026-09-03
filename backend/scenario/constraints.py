"""
Constraint presets (Knob C) for the CHW assignment problem.

Loose / Nominal / Tight change feasibility, not the solver algorithm.
Callers may override numeric knobs after resolving a preset.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.scenario.models import ObjectiveWeights

CONSTRAINT_PRESETS: Dict[str, Dict] = {
    "loose": {
        "max_walking_dist_km": 15.0,
        "who_ratio": 1500.0,
        "equity_target": 0.40,
        "lambdas": ObjectiveWeights(
            travel=1.0, assign=40.0, capacity=25.0, equity=2.0, walk_cap=8.0, stipend=0.0
        ),
    },
    "nominal": {
        "max_walking_dist_km": 7.5,
        "who_ratio": 1000.0,
        "equity_target": 0.25,
        "lambdas": ObjectiveWeights(
            travel=1.0, assign=50.0, capacity=50.0, equity=5.0, walk_cap=20.0, stipend=0.0
        ),
    },
    "tight": {
        "max_walking_dist_km": 5.0,
        "who_ratio": 800.0,
        "equity_target": 0.15,
        "lambdas": ObjectiveWeights(
            travel=1.0, assign=60.0, capacity=80.0, equity=12.0, walk_cap=40.0, stipend=0.0
        ),
    },
}

DEFAULT_CONSTRAINT = "nominal"


def get_constraint_preset(name: str) -> Dict:
    key = (name or DEFAULT_CONSTRAINT).strip().lower()
    if key not in CONSTRAINT_PRESETS:
        raise KeyError(f"Unknown constraint preset '{name}'. Choose from: {list(CONSTRAINT_PRESETS)}")
    return CONSTRAINT_PRESETS[key]


def list_constraint_presets() -> list[str]:
    return list(CONSTRAINT_PRESETS.keys())


def resolve_constraints(
    preset_name: str = DEFAULT_CONSTRAINT,
    *,
    max_walking_dist_km: Optional[float] = None,
    who_ratio: Optional[float] = None,
    equity_target: Optional[float] = None,
    lambdas: Optional[ObjectiveWeights] = None,
) -> Dict[str, Any]:
    """
    Start from a named preset, then apply optional numeric overrides.

    Returns a plain dict with max_walking_dist_km, who_ratio, equity_target, lambdas,
    and constraint_setting (the preset name used as the base).
    """
    base = get_constraint_preset(preset_name)
    walk = float(base["max_walking_dist_km"] if max_walking_dist_km is None else max_walking_dist_km)
    who = float(base["who_ratio"] if who_ratio is None else who_ratio)
    equity = float(base["equity_target"] if equity_target is None else equity_target)
    weights = lambdas if lambdas is not None else base["lambdas"]
    if walk <= 0:
        raise ValueError("max_walking_dist_km must be positive")
    if who <= 0:
        raise ValueError("who_ratio must be positive")
    if not (0.0 < equity < 1.0):
        raise ValueError("equity_target must be between 0 and 1 (exclusive)")
    return {
        "constraint_setting": (preset_name or DEFAULT_CONSTRAINT).strip().lower(),
        "max_walking_dist_km": walk,
        "who_ratio": who,
        "equity_target": equity,
        "lambdas": weights,
        "overrides_applied": {
            "max_walking_dist_km": max_walking_dist_km is not None,
            "who_ratio": who_ratio is not None,
            "equity_target": equity_target is not None,
            "lambdas": lambdas is not None,
        },
    }
