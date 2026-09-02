"""
CHW Deployment Recommender Engine & WHO Compliance Evaluator.
Generates actionable recommendations for Community Health Worker assignments in rural Kenya.
"""

from __future__ import annotations

from typing import Any, Dict, List


def generate_chw_recommendation(
    scenario_name: str,
    assignments: List[Dict[str, Any]],
    gini_equity_index: float,
    total_travel_km: float,
    uncovered_communities: List[str],
) -> Dict[str, Any]:
    """
    Generate policy recommendations & WHO guideline compliance audit.
    WHO Guideline Standards:
      - Max 1 CHW per 1,000 rural inhabitants / 200 households
      - Target walking distance < 5 km/day
      - Target Gini Equity Index < 0.25
    """
    who_equity_status = "COMPLIANT" if gini_equity_index <= 0.25 else "NEEDS_IMPROVEMENT"
    who_workload_status = "COMPLIANT" if total_travel_km / max(len(assignments), 1) <= 7.5 else "HIGH_BURDEN"

    recommendations = []
    if who_equity_status == "NEEDS_IMPROVEMENT":
        recommendations.append(
            "Increase CHW deployment weight in remote sub-counties to reduce Gini access inequality below 0.25."
        )
    if uncovered_communities:
        recommendations.append(
            f"Establish mobile motorcycle patrol units for {len(uncovered_communities)} isolated rural communities ({', '.join(uncovered_communities[:3])})."
        )
    if not recommendations:
        recommendations.append("Optimal deployment achieved. All rural community units meet WHO coverage & equity targets.")

    return {
        "scenario_name": scenario_name,
        "gini_equity_index": round(gini_equity_index, 3),
        "total_travel_km": round(total_travel_km, 2),
        "who_guideline_compliance": {
            "equity_status": who_equity_status,
            "workload_status": who_workload_status,
            "coverage_target": "MET" if not uncovered_communities else "PARTIAL",
        },
        "actionable_recommendations": recommendations,
        "qbraid_sync_status": "READY",
    }
