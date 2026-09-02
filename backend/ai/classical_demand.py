"""
Classical Machine Learning Baseline Demand Estimator for Rural Kenya.
Uses Scikit-Learn Random Forest & Ridge Regression models to benchmark against QML predictions.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import numpy as np

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    SKLEARN_AVAILABLE = True
except ImportError:
    RandomForestRegressor = None
    Ridge = None
    SKLEARN_AVAILABLE = False

try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBRegressor = None
    XGBOOST_AVAILABLE = False


try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    joblib = None
    JOBLIB_AVAILABLE = False


class ClassicalDemandEstimator:
    """
    Classical ML model baseline (Random Forest, XGBoost & Ridge Regression) for rural healthcare demand forecasting.
    """

    def __init__(self):
        self.rf_model = None
        self.xgb_model = None
        self.ridge_model = Ridge(alpha=1.0) if SKLEARN_AVAILABLE else None
        self.is_trained = False

        # Attempt to load pre-trained models from models/ directory
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        rf_path = os.path.join(base_dir, "models", "random_forest_model.joblib")
        xgb_path = os.path.join(base_dir, "models", "xgboost_model.joblib")

        loaded_rf = False
        loaded_xgb = False

        if JOBLIB_AVAILABLE:
            if os.path.exists(rf_path):
                try:
                    self.rf_model = joblib.load(rf_path)
                    loaded_rf = True
                except Exception:
                    pass
            if os.path.exists(xgb_path):
                try:
                    self.xgb_model = joblib.load(xgb_path)
                    loaded_xgb = True
                except Exception:
                    pass

        # Fallback to default in-memory fitting if pre-trained models are not found
        if not loaded_rf and SKLEARN_AVAILABLE:
            self.rf_model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
        if not loaded_xgb and XGBOOST_AVAILABLE:
            self.xgb_model = XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)

        if SKLEARN_AVAILABLE:
            X_default = np.array([
                [0.85, 0.40, 0.70, 0.80],
                [0.90, 0.50, 0.80, 0.90],
                [0.65, 0.15, 0.50, 0.50],
                [0.78, 0.30, 0.60, 0.70],
                [0.92, 0.60, 0.88, 0.95],
                [0.55, 0.10, 0.40, 0.40],
            ])
            y_default = np.array([0.82, 0.91, 0.58, 0.74, 0.95, 0.48])
            
            if not loaded_rf and self.rf_model is not None:
                self.rf_model.fit(X_default, y_default)
            if self.ridge_model is not None:
                self.ridge_model.fit(X_default, y_default)
            if not loaded_xgb and XGBOOST_AVAILABLE and self.xgb_model is not None:
                self.xgb_model.fit(X_default, y_default)
            self.is_trained = True


    def estimate_demand(
        self,
        vulnerability_score: float,
        distance_km: float,
        disease_risk: float = 0.5,
        population: int = 15000,
        available_chws: int = 2,
    ) -> Dict[str, Any]:
        """Predict demand score using classical Random Forest & XGBoost models."""
        pop_norm = min(population / 45000.0, 1.0)
        dist_norm = min(distance_km / 30.0, 1.0)
        gap_ratio = min((population / 1000.0) / max(available_chws, 1), 5.0) / 5.0
        
        X_input = np.array([[pop_norm, dist_norm, vulnerability_score, gap_ratio]])

        if SKLEARN_AVAILABLE and self.rf_model is not None and self.is_trained:
            rf_score = float(np.clip(self.rf_model.predict(X_input)[0], 0.1, 1.0))
            ridge_score = float(np.clip(self.ridge_model.predict(X_input)[0], 0.1, 1.0))
            xgb_score = float(np.clip(self.xgb_model.predict(X_input)[0], 0.1, 1.0)) if (XGBOOST_AVAILABLE and self.xgb_model is not None) else rf_score
        else:
            rf_score = float(np.clip(0.40 * vulnerability_score + 0.35 * dist_norm + 0.25 * pop_norm, 0.1, 1.0))
            ridge_score = rf_score
            xgb_score = rf_score

        return {
            "classical_rf_demand_score": round(rf_score, 3),
            "classical_xgb_demand_score": round(xgb_score, 3),
            "classical_ridge_demand_score": round(ridge_score, 3),
            "estimated_weekly_patients": int(xgb_score * 180 + 20),
            "sklearn_available": SKLEARN_AVAILABLE,
            "xgboost_available": XGBOOST_AVAILABLE,
        }

    def compare_with_qml(
        self,
        vulnerability_score: float,
        distance_km: float,
        disease_risk: float,
        qml_score: float,
    ) -> Dict[str, Any]:
        """Compute absolute error and difference between QML and Classical ML predictions."""
        class_res = self.estimate_demand(vulnerability_score, distance_km, disease_risk)
        rf_score = class_res["classical_rf_demand_score"]
        diff = round(abs(qml_score - rf_score), 4)

        return {
            "qml_demand_score": round(qml_score, 3),
            "classical_rf_demand_score": rf_score,
            "classical_ridge_demand_score": class_res["classical_ridge_demand_score"],
            "absolute_difference": diff,
            "parity_status": "CONVERGED" if diff < 0.10 else "DISCREPANCY",
        }


default_classical_estimator = ClassicalDemandEstimator()
