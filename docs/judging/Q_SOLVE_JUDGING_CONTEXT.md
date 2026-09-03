# Q-SOLVE Kenya 2026 — Judging Criteria (Team Working Copy)

Source: `docs/judging/Q-SOLVE_Kenya_2026_Judging_Tool_V02.pdf`  
Hackathon: 1–3 September 2026, Strathmore University, Nairobi

This file is **project context for solvers and reports**. Every classical / quantum run should attach a judging-aligned evidence block so we do not optimize for vanity metrics alone.

## Scorecard (100 pts raw)

| Code | Criterion | Max |
| :--- | :--- | ---: |
| **JC1** | Problem Understanding and Local Relevance | 15 |
| **JC2** | Quantum Computing Relevance and Necessity | 20 |
| **JC3** | Technical Correctness and Scientific Integrity | 15 |
| **JC4** | Evidence, Benchmarking and Validation | 15 |
| **JC5** | Innovation and Intellectual Contribution | 12 |
| **JC6** | Sustainable Development Impact (SDGs 2, 3, 8) | 13 |
| **JC7** | Feasibility, Scalability and Adoption | 10 |

> Note: **JC\*** = judging criteria. Classical solvers remain **C1–C7** in code (`c1_brute_force` … `c7_tabu_search`). Do not confuse the two.

## Final score

\[
\text{Final} = (\text{Raw Score} \times \text{Evidence Confidence Multiplier}) - \text{Quantum-Washing Penalty}
\]

### Evidence confidence multiplier

| Level | Multiplier | When |
| :--- | ---: | :--- |
| HIGH | ×1.00 | Claims demonstrated, documented, reproducible |
| MODERATE | ×0.95 | Most claims supported; some assumptions untested |
| LOW | ×0.85 | Projections / mock-ups / unclear evidence |

### Quantum-washing penalty

| Penalty | When |
| ---: | :--- |
| 0 | Quantum role clearly justified and proportional |
| −3 | Quantum weakly justified / easily replaced by classical |
| −6 | Unsupported speed-up / superiority / advantage claims |
| −10 | Quantum terminology promotional or unrelated |

## What this means for AfyaDeploy

1. **JC1 / JC6**: Keep Kenya 14-county CHW / SDG 3 framing; run **all counties**, not one demo.
2. **JC2**: Quantum only after classical bottlenecks are shown; never claim advantage vs greedy alone.
3. **JC3 / JC4**: Shared \(H(x)\), multi-metric equity, multi-county suite, reproducible scripts.
4. **JC5**: Equity suite + classical ladder + honest hybrid path is the contribution story.
5. **JC7**: Target **qBraid Lab Small · VS Code** (2 vCPU / 4 GB) + free simulator — realistic resources.

## Execution environment (qBraid)

| Setting | Value |
| :--- | :--- |
| Lab instance | **Small · VS Code** (2 vCPU, 4 GB RAM) |
| Classical compute | Local CPU inside that Lab instance |
| Quantum comparator | Free qBraid simulator (`qbraid:qbraid:sim:qir-sv`) |
| Emerald QPU | Explicit opt-in only (`ALLOW_QPU_DEFAULT=1`) |
