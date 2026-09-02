"""Tests for Classical Machine Learning Baseline Demand Estimator."""

from backend.ai.classical_demand import default_classical_estimator
from backend.ai.demand_qml import default_qml_estimator


def test_classical_demand_estimation():
    res = default_classical_estimator.estimate_demand(
        vulnerability_score=0.85,
        distance_km=12.0,
        disease_risk=0.70,
    )
    assert "classical_rf_demand_score" in res
    assert "classical_ridge_demand_score" in res
    assert 0.0 <= res["classical_rf_demand_score"] <= 1.0


def test_qml_vs_classical_comparison():
    qml_res = default_qml_estimator.estimate_community_demand(0.85, 12.0, 0.70)
    comp = default_classical_estimator.compare_with_qml(
        vulnerability_score=0.85,
        distance_km=12.0,
        disease_risk=0.70,
        qml_score=qml_res["demand_score"],
    )
    assert "qml_demand_score" in comp
    assert "classical_rf_demand_score" in comp
    assert "parity_status" in comp
