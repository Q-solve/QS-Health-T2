"""AI & QML package for CHW deployment in rural Kenya."""

from backend.ai.demand_qml import QMLDemandEstimator, default_qml_estimator
from backend.ai.classical_demand import ClassicalDemandEstimator, default_classical_estimator
from backend.ai.recommender import generate_chw_recommendation

__all__ = [
    "QMLDemandEstimator",
    "default_qml_estimator",
    "ClassicalDemandEstimator",
    "default_classical_estimator",
    "generate_chw_recommendation",
]
