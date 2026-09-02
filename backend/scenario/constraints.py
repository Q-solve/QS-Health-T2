"""
Constraint presets (Knob C) for the CHW assignment problem.

Loose / Nominal / Tight change feasibility, not the solver algorithm.
"""

from __future__ import annotations

from typing import Dict

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
