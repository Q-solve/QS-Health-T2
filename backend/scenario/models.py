"""
Data models for Community Health Worker (CHW) deployment scenarios and qBraid execution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthFacility(BaseModel):
    id: str
    name: str
    county: str
    lat: float
    lon: float
    available_chws: int = Field(default=5, description="Number of CHWs stationed at facility")
    facility_level: str = "Level 2 Dispensary"
    sub_county: str = ""
    ward: str = ""
    keph_level: str = "Level 2"
    linked_chu_count: int = 0
    distance_to_level3_km: float = 0.0
    terrain_class: str = "arid"
    chw_monthly_stipend_kes: float = 5000.0


class CommunityUnit(BaseModel):
    id: str
    name: str
    county: str
    lat: float
    lon: float
    population: int
    vulnerability_score: float = 0.5
    disease_risk: float = 0.4
    distance_to_facility_km: float = 5.0
    estimated_weekly_demand: int = 50
    sub_county: str = ""
    ward: str = ""
    under5_share: float = 0.15
    demand_score: float = 0.5
    terrain_class: str = "arid"
    phc_access_1h_share: float = 0.7
    travel_friction_phc_1h: float = 0.3
    stunting_u5_pct: Optional[float] = None
    wasting_u5_pct: Optional[float] = None
    underweight_u5_pct: Optional[float] = None
    facility_delivery_pct: Optional[float] = None
    skilled_delivery_pct: Optional[float] = None
    anc4_pct: Optional[float] = None
    maternal_risk_index: Optional[float] = None
    hh_itn_ownership_pct: Optional[float] = None
    malaria_itn_gap_pct: Optional[float] = None
    ccri_malaria_pf_score: Optional[float] = None
    ccri_riverine_flood_score: Optional[float] = None
    ccri_drought_score: Optional[float] = None
    ccri_food_insecurity_score: Optional[float] = None
    ccri_child_nutrition_score: Optional[float] = None
    ccri_maternal_health_score: Optional[float] = None
    ccri_risk_index: Optional[float] = None
    flood_risk_flag: int = 0
    seasonal_mobility_flag: int = 0
    poverty_overall_pct: Optional[float] = None
    distance_to_level3_km: float = 10.0


class ObjectiveWeights(BaseModel):
    """Shared H(x) multipliers — identical for classical and quantum."""

    travel: float = 1.0
    assign: float = 50.0
    capacity: float = 50.0
    equity: float = 5.0
    walk_cap: float = 20.0
    stipend: float = 0.0


class CHWDeploymentScenario(BaseModel):
    name: str
    title: str
    county: str
    description: str
    num_chws_available: int
    max_walking_dist_km: float = 8.0
    facilities: List[HealthFacility]
    communities: List[CommunityUnit]
    qubit_count: int = 6
    who_ratio: float = 1000.0
    equity_target: float = 0.25
    constraint_setting: str = "nominal"
    feature_stage: str = "B4"
    tier: str = "T0"
    seed: int = 42
    lambdas: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    extra: Dict[str, Any] = Field(default_factory=dict)

    @property
    def num_variables(self) -> int:
        return len(self.facilities) * len(self.communities)


class CHWSolutionAssignment(BaseModel):
    facility_id: str
    facility_name: str
    community_id: str
    community_name: str
    assigned_chws: int
    walking_distance_km: float  # d_ij (terrain-adjusted)
    demand_covered: int  # y_j (demand intensity)
    demand_score: Optional[float] = None  # composite urgency in (0,1]
    population: Optional[int] = None  # P_j


class CHWSolutionResult(BaseModel):
    scenario_name: str
    solver_type: str  # qaoa_qbraid, vqe_qbraid, greedy_classical, exact_ilp, c1..c7
    bitstring: str
    population_coverage_pct: float
    total_travel_km: float  # raw Σ d_ij x_ij (km); see demand_weighted_travel for H term
    gini_equity_index: float
    assignments: List[CHWSolutionAssignment]
    execution_time_sec: float
    qbraid_job_id: Optional[str] = None
    qbraid_synced: bool = True
    objective_value: Optional[float] = None  # H(x*) minimized
    # Objective-aligned reporting (same variables as evaluate_H / objective.md)
    demand_weighted_travel: Optional[float] = None  # Σ d_ij y_j x_ij
    objective_terms: Dict[str, float] = Field(default_factory=dict)
    objective_raw: Dict[str, Any] = Field(default_factory=dict)
    objective_inputs: Dict[str, Any] = Field(default_factory=dict)
    status: str = "feasible"  # optimal | feasible | timeout | infeasible | error | bottleneck
    who_compliance_pct: Optional[float] = None
    d_p90_km: Optional[float] = None
    theil_index: Optional[float] = None
    atkinson_index: Optional[float] = None
    bottom_quintile_coverage_pct: Optional[float] = None
    peak_memory_mb: Optional[float] = None
    extra_metrics: Dict[str, Any] = Field(default_factory=dict)
    failure_label: Optional[str] = None
    gap_to_best_classical: Optional[float] = None
    tier: Optional[str] = None
    feature_stage: Optional[str] = None
    constraint_setting: Optional[str] = None
    seed: Optional[int] = None
