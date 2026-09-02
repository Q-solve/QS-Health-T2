"""Scenario loader module."""

from backend.scenario.sample_scenarios import SAMPLE_SCENARIOS
from backend.scenario.models import CHWDeploymentScenario


def list_available_scenarios() -> list[dict]:
    return [
        {
            "name": name,
            "title": s.title,
            "county": s.county,
            "num_chws": s.num_chws_available,
            "facilities": len(s.facilities),
            "communities": len(s.communities),
            "qubit_count": s.qubit_count,
        }
        for name, s in SAMPLE_SCENARIOS.items()
    ]
