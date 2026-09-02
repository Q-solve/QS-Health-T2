"""
Dynamic Scenario Builder for CHW Deployment in Rural Kenya.
Builds custom scenario objects from administrative parameters or KMHFR data queries.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from backend.scenario.models import CHWDeploymentScenario, CommunityUnit, HealthFacility
from backend.scenario.sample_scenarios import SAMPLE_SCENARIOS


def build_custom_chw_scenario(
    name: str,
    county: str,
    num_facilities: int = 2,
    num_communities: int = 3,
    available_chws: int = 5,
) -> CHWDeploymentScenario:
    """Dynamically generate a rural CHW deployment scenario."""
    facilities = [
        HealthFacility(
            id=f"F{i+1}",
            name=f"{county} Dispensary {i+1}",
            county=county,
            lat=-1.0 + i * 0.1,
            lon=36.5 + i * 0.1,
            available_chws=max(1, available_chws // num_facilities),
        )
        for i in range(num_facilities)
    ]
    communities = [
        CommunityUnit(
            id=f"C{j+1}",
            name=f"{county} Community Unit {j+1}",
            county=county,
            lat=-1.05 + j * 0.08,
            lon=36.52 + j * 0.08,
            population=800 + j * 200,
            vulnerability_score=0.6 + (j % 3) * 0.1,
        )
        for j in range(num_communities)
    ]
    return CHWDeploymentScenario(
        name=name,
        title=f"{county} Custom CHW Deployment Plan",
        county=county,
        description=f"Dynamically generated scenario for {county} with {num_communities} community units.",
        num_chws_available=available_chws,
        facilities=facilities,
        communities=communities,
        qubit_count=num_facilities * num_communities,
    )


def get_scenario_by_name(name: str) -> Optional[CHWDeploymentScenario]:
    """Retrieve sample scenario by name."""
    return SAMPLE_SCENARIOS.get(name)
