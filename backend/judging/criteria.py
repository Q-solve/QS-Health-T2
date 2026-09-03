"""
Q-SOLVE Kenya 2026 judging scorecard (JC1–JC7).

Source of truth for docs: docs/judging/Q_SOLVE_JUDGING_CONTEXT.md
"""

from __future__ import annotations

from typing import Any, Dict, List

CRITERIA: Dict[str, Dict[str, Any]] = {
    "JC1": {
        "name": "Problem Understanding and Local Relevance",
        "max_score": 15,
        "focus": "Kenyan CHW deployment across marginalised counties; users, constraints, consequences",
    },
    "JC2": {
        "name": "Quantum Computing Relevance and Necessity",
        "max_score": 20,
        "focus": "Bottleneck identification, classical baselines, no exaggerated advantage claims",
    },
    "JC3": {
        "name": "Technical Correctness and Scientific Integrity",
        "max_score": 15,
        "focus": "Shared H(x), explicit assumptions/limits, reproducible formulation",
    },
    "JC4": {
        "name": "Evidence, Benchmarking and Validation",
        "max_score": 15,
        "focus": "Quantitative multi-county baselines, metrics, robustness/scalability",
    },
    "JC5": {
        "name": "Innovation and Intellectual Contribution",
        "max_score": 12,
        "focus": "Equity metrics suite, classical ladder, honest hybrid quantum path",
    },
    "JC6": {
        "name": "Sustainable Development Impact (SDGs 2, 3 and 8)",
        "max_score": 13,
        "focus": "Primary SDG 3 (Good Health); CHW coverage/equity/workload outcomes",
    },
    "JC7": {
        "name": "Feasibility, Scalability and Adoption",
        "max_score": 10,
        "focus": "Runs on qBraid Small VS Code + free simulator; staged classical→quantum path",
    },
}

EVIDENCE_MULTIPLIERS = {"HIGH": 1.0, "MODERATE": 0.95, "LOW": 0.85}

QUANTUM_WASHING_PENALTIES = {
    "none": 0,
    "weak_justification": -3,
    "unsupported_advantage": -6,
    "promotional_misuse": -10,
}

GUIDANCE = [
    "Run all counties (not one location) for JC1/JC4.",
    "Exhaust classical C1–C7 before any quantum-necessity claim (JC2).",
    "Never claim quantum advantage vs greedy alone (quantum-washing risk).",
    "Keep SDG 3 metrics (coverage, equity, WHO, d_P90) visible (JC6).",
    "Prefer qBraid Small VS Code + free simulator for JC7 realism.",
]


def judging_scorecard_template() -> Dict[str, Any]:
    """Static scorecard context for API / UI."""
    return {
        "source": "Q-SOLVE Kenya 2026 Judging Tool V02",
        "docs": "docs/judging/Q_SOLVE_JUDGING_CONTEXT.md",
        "pdf": "docs/judging/Q-SOLVE_Kenya_2026_Judging_Tool_V02.pdf",
        "criteria": CRITERIA,
        "final_score_formula": "(Raw Score × Evidence Confidence Multiplier) − Quantum-Washing Penalty",
        "evidence_multipliers": EVIDENCE_MULTIPLIERS,
        "quantum_washing_penalties": QUANTUM_WASHING_PENALTIES,
        "focus_sdg": {
            "primary": "SDG 3: Good Health and Well-Being",
            "secondary": [
                "SDG 8: Decent Work (CHW workload protection)",
                "SDG 2: Zero Hunger (nutrition outreach support)",
            ],
        },
        "environment_target": {
            "qbraid_lab_instance": "Small · VS Code",
            "vcpus": 2,
            "ram_gb": 4,
            "classical_target": "local_cpu",
            "quantum_default": "free_simulator",
        },
        "guidance": GUIDANCE,
    }


def _flag(ok: bool) -> str:
    return "PASS" if ok else "GAP"


def build_judging_evidence(
    *,
    counties_covered: int = 0,
    scenarios_run: int = 0,
    classical_methods_run: int = 0,
    has_shared_objective: bool = True,
    has_multi_metric_equity: bool = False,
    classical_bottleneck_detected: bool = False,
    quantum_ran: bool = False,
    quantum_claimed_advantage: bool = False,
    quantum_beats_best_classical: bool = False,
    used_free_simulator_or_local: bool = True,
    sdg3_metrics_present: bool = True,
) -> Dict[str, Any]:
    """
    Auto-checklist + suggested self-score for team steering.
    Official scores are by judges — this is evidence packaging only.
    """
    multi_county = counties_covered >= 10
    local_scope = counties_covered >= 5
    multi_method = classical_methods_run >= 5
    no_exaggeration = not quantum_claimed_advantage or (
        classical_bottleneck_detected and quantum_beats_best_classical
    )
    bottleneck_gate = (not quantum_ran) or classical_bottleneck_detected or (not quantum_claimed_advantage)

    auto_checklist = {
        "JC1": {
            "local_kenya_scope": _flag(local_scope),
            "multi_county_not_single_demo": _flag(multi_county),
            "notes": f"{counties_covered} counties / {scenarios_run} scenarios executed",
        },
        "JC2": {
            "classical_baselines_present": _flag(classical_methods_run >= 1),
            "bottleneck_before_quantum_claim": _flag(bottleneck_gate),
            "no_exaggerated_advantage": _flag(no_exaggeration),
            "notes": "Quantum necessity gated on classical bottlenecks",
        },
        "JC3": {
            "shared_objective_H": _flag(has_shared_objective),
            "reproducible_suite": _flag(classical_methods_run >= 1 or quantum_ran),
        },
        "JC4": {
            "quantitative_multi_location": _flag(multi_county),
            "multi_method_benchmark": _flag(multi_method),
            "equity_beyond_gini": _flag(has_multi_metric_equity),
        },
        "JC5": {
            "classical_suite_plus_honest_quantum_path": _flag(
                classical_methods_run >= 5 or quantum_ran
            ),
        },
        "JC6": {
            "sdg3_health_metrics": _flag(sdg3_metrics_present),
            "focus_sdg": "SDG 3: Good Health and Well-Being",
        },
        "JC7": {
            "runs_on_small_lab_or_free_sim": _flag(used_free_simulator_or_local),
            "qbraid_instance": "Small · VS Code",
        },
    }

    evidence_gaps: List[str] = []
    for jc, block in auto_checklist.items():
        for key, val in block.items():
            if val == "GAP":
                evidence_gaps.append(f"{jc}.{key}")

    # Lightweight self-estimate (team steering only)
    scores = {
        "JC1": 12 if multi_county else (8 if local_scope else 5),
        "JC2": 16 if (classical_methods_run >= 5 and no_exaggeration) else 12,
        "JC3": 13 if has_shared_objective else 8,
        "JC4": 12 if multi_county and multi_method else (8 if multi_method else 6),
        "JC5": 9 if classical_methods_run >= 5 else 6,
        "JC6": 11 if sdg3_metrics_present else 6,
        "JC7": 9 if used_free_simulator_or_local else 5,
    }
    raw = sum(scores.values())
    confidence = "HIGH" if not evidence_gaps else ("MODERATE" if len(evidence_gaps) <= 3 else "LOW")
    multiplier = EVIDENCE_MULTIPLIERS[confidence]
    washing = "unsupported_advantage" if quantum_claimed_advantage and not quantum_beats_best_classical else "none"
    penalty = QUANTUM_WASHING_PENALTIES[washing]

    return {
        "judging_context": judging_scorecard_template(),
        "auto_checklist": auto_checklist,
        "evidence_gaps": evidence_gaps,
        "suggested_self_score": {
            "criterion_scores": scores,
            "raw_score": raw,
            "evidence_confidence": confidence,
            "multiplier": multiplier,
            "quantum_washing": washing,
            "penalty": penalty,
            "final_score_estimate": round(raw * multiplier + penalty, 2),
            "disclaimer": "Self-estimate for team steering only — official scores are by judges.",
        },
        "guidance": GUIDANCE,
    }


def attach_judging_to_report(report: Dict[str, Any], evidence_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Attach q_solve_judging block to any benchmark / compare payload."""
    out = dict(report)
    out["q_solve_judging"] = build_judging_evidence(**evidence_kwargs)
    return out
