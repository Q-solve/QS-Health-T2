"""Scenario package for rural Kenya CHW deployment."""

from backend.scenario.models import (
    CHWDeploymentScenario,
    CommunityUnit,
    HealthFacility,
    CHWSolutionResult,
)
from backend.scenario.sample_scenarios import SAMPLE_SCENARIOS
from backend.scenario.loader import list_available_scenarios
from backend.scenario.constraints import CONSTRAINT_PRESETS, get_constraint_preset, list_constraint_presets
from backend.scenario.features import list_feature_stages
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
    "list_feature_stages",
    "TIER_SPEC",
    "build_ladder_instance",
    "iter_ladder_instances",
    "ladder_catalog",
]