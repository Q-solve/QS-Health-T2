"""Scenario package for rural Kenya CHW deployment."""

from backend.scenario.models import (
    CHWDeploymentScenario,
    CommunityUnit,
    HealthFacility,
    CHWSolutionResult,
)
from backend.scenario.sample_scenarios import SAMPLE_SCENARIOS
from backend.scenario.loader import list_available_scenarios
from backend.scenario.constraints import (
    CONSTRAINT_PRESETS,
    get_constraint_preset,
    list_constraint_presets,
    resolve_constraints,
)
from backend.scenario.features import list_demand_factors, list_feature_stages, default_enabled_factors
from backend.scenario.ladder import TIER_SPEC, build_ladder_instance, iter_ladder_instances, ladder_catalog

__all__ = [
    "CHWDeploymentScenario",
    "CommunityUnit",
    "HealthFacility",
    "CHWSolutionResult",
    "SAMPLE_SCENARIOS",
    "list_available_scenarios",
    "CONSTRAINT_PRESETS",
    "get_constraint_preset",
    "list_constraint_presets",
    "resolve_constraints",
    "list_feature_stages",
    "list_demand_factors",
    "default_enabled_factors",
    "TIER_SPEC",
    "build_ladder_instance",
    "iter_ladder_instances",
    "ladder_catalog",
]