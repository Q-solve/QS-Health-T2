#!/usr/bin/env python3
"""
submit_quantum_jobs.py

Thin wrapper around Phase 3: submit QAOA jobs for CHW ladder instances
to the free qBraid simulator (QBRAID_API_KEY from .env).

Prefer:
  PYTHONPATH=. .venv/bin/python scripts/run_quantum_phase3.py

This script remains as a short alias for submit-only workflows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend import config
from scripts.run_quantum_phase3 import run_phase3


def main():
    parser = argparse.ArgumentParser(description="Submit AfyaDeploy QAOA jobs to qBraid (Phase 3)")
    parser.add_argument("--profile", choices=["hackathon", "smoke"], default="hackathon")
    parser.add_argument(
        "--backend",
        default=config.QBRAID_DEFAULT_DEVICE or config.QBRAID_FREE_SIMULATOR,
        help="qBraid device id. Default: free simulator from .env",
    )
    parser.add_argument("--shots", type=int, default=config.QAOA_SHOTS)
    args = parser.parse_args()
    run_phase3(args.profile, args.backend, args.shots)


if __name__ == "__main__":
    main()
