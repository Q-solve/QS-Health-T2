# AfyaDeploy

Classical-first Community Health Worker (CHW) deployment evaluation for rural Kenya (**SDG 3**).

Seven classical allocation solvers (C1–C7) are the primary suite. QAOA on qBraid is a **secondary NISQ comparator**. We do **not** claim quantum advantage vs greedy alone.

## Honest framing

1. Shared multi-objective H(x) for every solver (coverage, travel, WHO capacity, equity).
2. Instance ladder T0–T6 from the unified 14-county dataset.
3. Explicit §6 verdict in `docs/quantum_advantage_verdict.md` (default expectation: **Verdict A — No Quantum Advantage** at current sizes).



## Architecture

```text
React UI ──HTTP──► FastAPI ──► Classical suite C1–C7 (local CPU)
  (Vite)              │              └── shared H(x) / QUBO builder
                      └── optional QAOA comparator (free qBraid simulator)
```



## Quick start

```bash
# 1) Python env
source .venv/bin/activate
export PYTHONPATH=.

# 2) API
uvicorn backend.main:app --reload --port 8000

# 3) UI — interactive classical / quantum optimize
cd frontend && npm install && npm run dev
```

- UI: [http://localhost:5173](http://localhost:5173) — submit ladder problems, run classical and/or QAOA  
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)  
- Tests: `pytest backend/tests -q`
- Math & method formulations: `[document.md](document.md)`



## Deploy (Render API + Vercel dashboard)



### 1. Backend on Render (Docker)

1. Push this repo to GitHub.
2. In [Render](https://render.com): **New → Blueprint** (uses `render.yaml`) or **New → Web Service** with **Docker**.
3. Dockerfile path: `./Dockerfile`, health check: `/api/health`.
4. Set env vars in the Render dashboard (see `.env.example`), especially:
  - `CORS_ORIGINS` = your Vercel URL (e.g. `https://your-app.vercel.app`)
  - optional: `QBRAID_API_KEY`, `CLAUDE_API_KEY`
5. After deploy, copy the service URL (e.g. `https://afyadeploy-api.onrender.com`).

Local image smoke test:

```bash
docker build -t afyadeploy-api .
docker run --rm -p 8000:8000 -e CORS_ORIGINS=http://localhost:5173 afyadeploy-api
curl http://127.0.0.1:8000/api/health
```



### 2. Dashboard on Vercel

1. In [Vercel](https://vercel.com): import the repo, set **Root Directory** to `frontend`.
2. Framework: Vite (see `frontend/vercel.json`).
3. Add environment variable **before build**:
  - `VITE_API_BASE_URL` = `https://your-service.onrender.com` (no trailing slash)
4. Deploy. The UI calls `${VITE_API_BASE_URL}/api/...`.



### 3. Wire the two together


| Where  | Variable            | Value               |
| ------ | ------------------- | ------------------- |
| Vercel | `VITE_API_BASE_URL` | Render HTTPS origin |
| Render | `CORS_ORIGINS`      | Vercel HTTPS origin |


Redeploy both after changing either URL. Free Render services cold-start; the first API call after idle may take ~30–60s.

## Key data & benchmarks


| Artifact                              | Role                           |
| ------------------------------------- | ------------------------------ |
| `data/unified_chw_dataset.csv`        | 1,260 facilities (14 counties) |
| `data/community_units_kmhfr.csv`      | 764 CHUs (demand nodes)        |
| `data/classical_suite_results.json`   | Classical ladder runs          |
| `data/quantum_benchmark_results.json` | QAOA vs best classical         |
| `docs/quantum_advantage_verdict.md`   | §6 verdict                     |


Join key for fair compare: `(tier, county, seed, constraint_setting, feature_stage)`.

## Scripts

```bash
PYTHONPATH=. python scripts/run_classical_suite.py --profile hackathon
PYTHONPATH=. python scripts/run_quantum_phase3.py
PYTHONPATH=. python scripts/write_advantage_verdict.py
PYTHONPATH=. python scripts/regenerate_plots.py
```



## Docs

- `document.md` — technical details, choices, folder/file map  
- `implementation_plan.md` — full evaluation protocol  
- `data/DATA_SOURCES.md` — verified source provenance  

