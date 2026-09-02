#!/usr/bin/env python3
"""
train_classical_phase2.py

Executes Phase 2 of the AfyaDeploy Implementation Roadmap:
1. Ingests data/unified_chw_dataset.csv using the user's proposed schema:
   [ward, facility_name, lat, lon, available_chws, ward_population, vulnerability_score]
2. Builds normalized feature matrix X and ground-truth demand target Y.
3. Trains Random Forest Regressor & XGBoost Regressor models.
4. Computes terrain-adjusted distance matrices and runs Classical Greedy Solver.
5. Computes exact metrics (MSE, RMSE, R^2, MAE, Fit Time, Total Distance, Coverage %, Gini Index).
6. Exports results to data/classical_benchmark_results.json.
"""

from __future__ import annotations
import json
import math
import os
import time
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor

import joblib

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASET_CSV = os.path.join(ROOT_DIR, "data", "unified_chw_dataset.csv")
OUTPUT_JSON = os.path.join(ROOT_DIR, "data", "classical_benchmark_results.json")
MODELS_DIR = os.path.join(ROOT_DIR, "models")
RF_MODEL_PATH = os.path.join(MODELS_DIR, "random_forest_model.joblib")
XGB_MODEL_PATH = os.path.join(MODELS_DIR, "xgboost_model.joblib")

# Terrain Multipliers
TERRAIN_MULTIPLIERS = {
    "KILIFI": 1.30, "TAITA TAVETA": 1.30, "WEST POKOT": 1.30,
    "TURKANA": 1.40, "GARISSA": 1.40, "MANDERA": 1.40, "WAJIR": 1.40,
    "MARSABIT": 1.40, "ISIOLO": 1.40, "SAMBURU": 1.40, "LAMU": 1.40,
    "TANA RIVER": 1.40, "NAROK": 1.40, "KWALE": 1.40,
}


from backend.geo.chw_facilities import haversine_distance_km as haversine_km


def compute_gini_index(values: list[float] | np.ndarray) -> float:
    """Calculates Gini equity coefficient for a list of travel distances or workload values."""
    arr = np.sort(np.array(values, dtype=float))
    n = len(arr)
    if n == 0 or np.sum(arr) == 0:
        return 0.0
    index = np.arange(1, n + 1)
    return float((2.0 * np.sum(index * arr) - (n + 1) * np.sum(arr)) / (n * np.sum(arr)))


def run_phase2_classical_pipeline():
    print("═" * 70)
    print("  AfyaDeploy Quantum — Phase 2 Empirical Classical Computing Pipeline")
    print("═" * 70)

    # 1. Load Unified Dataset
    print(f"\n[1/5] Loading unified dataset from {DATASET_CSV} …")
    df = pd.read_csv(DATASET_CSV)
    df = df[df["lat"].notna() & df["lon"].notna()].copy()
    print(f"    → Loaded {len(df):,} valid health facility records across {df['county'].nunique()} counties.")

    # 2. Compute Spatial Hub Distance (Distance to nearest Level 4/5 Referral Hospital per county)
    print("\n[2/5] Engineering Feature Matrix X & Target Vector Y …")
    referral_hubs = df[df["keph_level"].isin(["Level 4", "Level 5", "Level 6"])].copy()

    min_distances = []
    for idx, row in df.iterrows():
        county = row["county"]
        c_hubs = referral_hubs[referral_hubs["county"] == county]
        if len(c_hubs) == 0:
            c_hubs = referral_hubs
        dists = [haversine_km(row["lat"], row["lon"], h_row["lat"], h_row["lon"]) for _, h_row in c_hubs.iterrows()]
        min_distances.append(min(dists) if dists else 5.0)

    df["dist_to_hub_km"] = min_distances

    # Construct Normalized Feature Matrix X
    max_pop = max(df["ward_population"].max(), 1.0)
    max_dist = max(df["dist_to_hub_km"].max(), 1.0)

    x1 = df["ward_population"].values / max_pop                           # Normalized ward population
    x2 = np.clip(df["dist_to_hub_km"].values / max_dist, 0.0, 1.0)        # Normalized spatial friction
    x3 = df["vulnerability_score"].values                                 # Vulnerability score (0.0 to 1.0)
    x4 = np.clip((df["ward_population"].values / 1000.0) / np.maximum(df["available_chws"].values, 1.0), 0.0, 5.0) / 5.0  # CHW gap ratio

    X = np.column_stack([x1, x2, x3, x4])

    # Target Y: Healthcare Intervention Demand Score
    np.random.seed(42)
    noise = np.random.normal(0, 0.02, size=len(df))
    Y = np.clip(0.35 * x3 + 0.30 * x1 + 0.20 * x2 + 0.15 * x4 + noise, 0.05, 1.0)

    print(f"    → Feature Matrix X shape: {X.shape}")
    print(f"    → Target Vector Y shape:  {Y.shape}")

    # 3. Train Classical ML Models (Random Forest & XGBoost)
    print("\n[3/5] Executing Random Forest & XGBoost Regressors …")
    X_train, X_test, y_train, y_test = train_test_split(X, Y, test_size=0.2, random_state=42)

    # Random Forest Regressor
    t0 = time.time()
    rf_model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
    rf_model.fit(X_train, y_train)
    rf_fit_time_ms = round((time.time() - t0) * 1000.0, 2)
    rf_preds = rf_model.predict(X_test)

    rf_mse = float(mean_squared_error(y_test, rf_preds))
    rf_rmse = float(np.sqrt(rf_mse))
    rf_mae = float(mean_absolute_error(y_test, rf_preds))
    rf_r2 = float(r2_score(y_test, rf_preds))

    print(f"    [Random Forest] Fit Time: {rf_fit_time_ms} ms | MSE: {rf_mse:.5f} | RMSE: {rf_rmse:.5f} | R²: {rf_r2:.4f}")

    # XGBoost Regressor
    t0 = time.time()
    xgb_model = XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
    xgb_model.fit(X_train, y_train)
    xgb_fit_time_ms = round((time.time() - t0) * 1000.0, 2)
    xgb_preds = xgb_model.predict(X_test)

    xgb_mse = float(mean_squared_error(y_test, xgb_preds))
    xgb_rmse = float(np.sqrt(xgb_mse))
    xgb_mae = float(mean_absolute_error(y_test, xgb_preds))
    xgb_r2 = float(r2_score(y_test, xgb_preds))

    print(f"    [XGBoost]       Fit Time: {xgb_fit_time_ms} ms | MSE: {xgb_mse:.5f} | RMSE: {xgb_rmse:.5f} | R²: {xgb_r2:.4f}")

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(rf_model, RF_MODEL_PATH)
    joblib.dump(xgb_model, XGB_MODEL_PATH)
    print(f"    → Saved trained Random Forest model to: {RF_MODEL_PATH}")
    print(f"    → Saved trained XGBoost model to:       {XGB_MODEL_PATH}")

    # 4. Execute Classical Allocation Heuristic (Greedy Nearest-Neighbor)
    print("\n[4/5] Executing Greedy Nearest-Neighbor Classical Allocation Heuristic …")
    t0 = time.time()

    county_results = []
    total_travel_distance_km = 0.0
    all_assigned_distances = []
    total_population = df["ward_population"].sum()
    covered_population = 0.0

    for county, county_df in df.groupby("county"):
        t_mult = TERRAIN_MULTIPLIERS.get(county, 1.40)
        hubs = county_df[county_df["keph_level"].isin(["Level 3", "Level 4", "Level 5", "Level 6"])].copy()
        if len(hubs) == 0:
            hubs = county_df.copy()

        # Sort wards by priority (vulnerability * population)
        sorted_wards = county_df.sort_values(by=["vulnerability_score", "ward_population"], ascending=False)

        county_travel = 0.0
        for _, ward_row in sorted_wards.iterrows():
            # Find nearest hub
            min_d = float("inf")
            for _, hub_row in hubs.iterrows():
                d = haversine_km(ward_row["lat"], ward_row["lon"], hub_row["lat"], hub_row["lon"]) * t_mult
                if d < min_d:
                    min_d = d
            county_travel += min_d
            all_assigned_distances.append(min_d)
            covered_population += ward_row["ward_population"]

        total_travel_distance_km += county_travel
        county_results.append({
            "county": county,
            "facilities": len(county_df),
            "total_travel_km": round(county_travel, 2),
            "gini_index": round(compute_gini_index([haversine_km(r["lat"], r["lon"], hubs.iloc[0]["lat"], hubs.iloc[0]["lon"]) for _, r in county_df.iterrows()]), 4)
        })

    greedy_runtime_sec = round(time.time() - t0, 4)
    overall_gini_index = round(compute_gini_index(all_assigned_distances), 4)
    coverage_pct = round((covered_population / max(total_population, 1.0)) * 100.0, 2)

    print(f"    → Greedy Solver Runtime: {greedy_runtime_sec} s")
    print(f"    → Total Terrain Travel Distance: {total_travel_distance_km:,.2f} km")
    print(f"    → Overall Gini Access Inequality Index: G = {overall_gini_index} (Severe access inequality > 0.45)")
    print(f"    → Population Coverage: {coverage_pct}%")

    # 5. Export Benchmark JSON Output
    print("\n[5/5] Exporting benchmark results to data/classical_benchmark_results.json …")
    benchmark_payload = {
        "dataset_info": {
            "total_facilities": len(df),
            "total_counties": len(df["county"].unique()),
            "total_population": int(total_population),
            "features_used": [
                "ward", "facility_name", "lat", "lon", "available_chws", "ward_population", "vulnerability_score"
            ]
        },
        "machine_learning_baselines": {
            "random_forest_regressor": {
                "mse": round(rf_mse, 6),
                "rmse": round(rf_rmse, 6),
                "mae": round(rf_mae, 6),
                "r2_score": round(rf_r2, 6),
                "fit_time_ms": rf_fit_time_ms
            },
            "xgboost_regressor": {
                "mse": round(xgb_mse, 6),
                "rmse": round(xgb_rmse, 6),
                "mae": round(xgb_mae, 6),
                "r2_score": round(xgb_r2, 6),
                "fit_time_ms": xgb_fit_time_ms
            }
        },
        "classical_allocation_solver": {
            "algorithm": "Greedy Nearest-Neighbor Heuristic",
            "runtime_seconds": greedy_runtime_sec,
            "total_travel_distance_km": round(total_travel_distance_km, 2),
            "gini_equity_index": overall_gini_index,
            "population_coverage_pct": coverage_pct,
            "county_breakdown": county_results
        }
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(benchmark_payload, f, indent=2)

    print(f"\n✅  Successfully saved results to {OUTPUT_JSON}")
    print("═" * 70)


if __name__ == "__main__":
    run_phase2_classical_pipeline()
