#!/usr/bin/env python3
"""
fetch_quantum_results.py

Re-poll qBraid for jobs listed in data/qbraid_submitted_jobs.json and
refresh measurement counts / best bitstrings. Phase 3 already waits inline;
use this if a job was still RUNNING when the runner exited.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/fetch_quantum_results.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from qbraid import QbraidJob, QbraidProvider

from backend.qbraid_client.manager import QBraidManager

JOBS_JSON = ROOT / "data" / "qbraid_submitted_jobs.json"
RESULTS_JSON = ROOT / "data" / "qbraid_job_results.json"


def main():
    api_key = os.getenv("QBRAID_API_KEY", "").strip()
    if not api_key:
        print("ERROR: QBRAID_API_KEY not set in .env")
        sys.exit(1)

    if not JOBS_JSON.exists():
        print(f"No submitted jobs at {JOBS_JSON}. Run scripts/run_quantum_phase3.py first.")
        sys.exit(1)

    payload = json.loads(JOBS_JSON.read_text())
    provider = QbraidProvider(api_key=api_key)
    print(f"Authenticated with qBraid. Fetching {len(payload.get('jobs', []))} jobs…\n")

    refreshed = []
    for job_record in payload.get("jobs", []):
        job_id = job_record.get("job_id")
        label = job_record.get("cluster") or job_record.get("county") or "?"
        if not job_id or str(job_id).startswith("local_sim_"):
            print(f"[{label}] skipped — no platform job id")
            refreshed.append({**job_record, "fetch_status": "skipped"})
            continue
        try:
            qjob = QbraidJob(job_id=job_id, client=provider.client)
            status = str(qjob.status())
            print(f"[{label}] {job_id} — {status}")
            entry = {**job_record, "fetch_status": status}
            if any(tok in status.upper() for tok in ("COMPLETED", "DONE")):
                result = qjob.result()
                counts = QBraidManager.extract_counts(result)
                best = max(counts, key=counts.get) if counts else None
                top5 = sorted(counts.items(), key=lambda x: -x[1])[:5] if counts else []
                entry["counts"] = counts
                entry["best_raw_bitstring"] = best
                entry["top5_counts"] = top5
                print(f"   best={best} | top5={top5}")
            refreshed.append(entry)
        except Exception as e:
            print(f"[{label}] error: {e}")
            refreshed.append({**job_record, "fetch_status": "error", "error": str(e)})

    RESULTS_JSON.write_text(json.dumps({"jobs": refreshed}, indent=2))
    print(f"\nWrote {RESULTS_JSON}")


if __name__ == "__main__":
    main()
