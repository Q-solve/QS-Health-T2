# Quantum Advantage Verdict — AfyaDeploy

**Generated:** 2026-09-03 03:59 UTC  
**Primary verdict:** **Verdict A — No Quantum Advantage (Expected Default at NISQ Scale)**

## Demo statement

> Across our instance ladder, classical methods (especially SA/GA/Tabu and MILP on small graphs) matched or beat QAOA on solution quality and dominated on scalable county-sized problems. **We do not claim quantum advantage** for CHW deployment at current problem sizes.

## Rubric (§6)

| Code | Meaning |
| --- | --- |
| A | No Quantum Advantage |
| B | Conditional / Hybrid Value |
| C | Quantum Advantage / Needed (strict bar) |

## Evidence

- Classical suite: 1101 runs (profile=complete_tiers).
- Quantum comparator: 9 QAOA runs (status=complete).
- Comparable shared instances: 7; QAOA strictly better than best classical: 0.
- Scale-skipped quantum (T3+/NISQ ceiling): 2.
- Classical feasible/optimal rows: 1038.
- Hurdle summary keys: ['n_instances', 'hurdle_counts', 'by_tier', 'by_who_capacity_mode', 'quantum_candidate_count', 'quantum_needed_candidate_count', 'interpretation']
- On every comparable T0–T4 instance, best classical among C2–C7 matched or beat QAOA.
- County-scale tiers remain classical-operational; quantum needs decomposition.
- Default NISQ expectation confirmed: No Quantum Advantage for CHW allocation at current sizes.

## QML demand track

```json
{
  "qml_vqc": {
    "mse": 0.006277,
    "rmse": 0.079228,
    "mae": 0.069953,
    "r2": 0.406624,
    "fit_time_ms": 5184.02,
    "model": "3-qubit ZZFeatureMap VQC"
  },
  "random_forest": {
    "mse": 0.000452,
    "rmse": 0.021257,
    "mae": 0.016319,
    "r2": 0.957286
  },
  "ridge": {
    "mse": 0.000451,
    "rmse": 0.021241,
    "mae": 0.016909,
    "r2": 0.95735
  },
  "xgboost": {
    "mse": 0.000565,
    "rmse": 0.023771,
    "mae": 0.016636,
    "r2": 0.946585
  },
  "verdict_note": "QML RMSE relative improvement vs best classical = -273.0% (need >5% for meaningful QML edge; negative means classical better).",
  "qml_beats_classical_by_5pct_rmse": false
}
```

## Data sources

- Classical: `data/classical_suite_results.json`
- Quantum: `data/quantum_benchmark_results.json`

## Honest framing

Beating a weak greedy baseline alone is **not** quantum advantage. Primary rivals are best of C2–C7 under the shared objective H(x).
