"""Tests for Quantum Machine Learning (QML) Demand Estimator."""

from backend.ai.demand_qml import default_qml_estimator


def test_qml_demand_estimation():
    res = default_qml_estimator.estimate_community_demand(
        vulnerability_score=0.85,
        distance_km=12.0,
        disease_risk=0.70,
    )
    assert "demand_score" in res
    assert 0.0 <= res["demand_score"] <= 1.0
    assert "estimated_weekly_patients" in res
    assert res["estimated_weekly_patients"] > 0
