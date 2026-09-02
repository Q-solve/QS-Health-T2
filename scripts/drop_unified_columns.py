#!/usr/bin/env python3
"""Remove unused / provenance columns from data/unified_chw_dataset.csv."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "unified_chw_dataset.csv"

DROP_COLS = [
    "facility_type",
    "coordinate_source",
    "anc_skilled_pct",
    "poverty_overall_pct",
    "linked_chu_count",
    "real_chw_headcount",
    "adm2_match_level",
    "adm2_pcode",
    "adm2_name",
]


def main() -> None:
    df = pd.read_csv(CSV_PATH)
    present = [c for c in DROP_COLS if c in df.columns]
    missing = [c for c in DROP_COLS if c not in df.columns]
    if missing:
        print(f"Already absent (skipped): {missing}")
    out = df.drop(columns=present)
    out.to_csv(CSV_PATH, index=False)
    print(f"Removed {len(present)} columns: {present}")
    print(f"Wrote {CSV_PATH} with {len(out)} rows × {len(out.columns)} cols")


if __name__ == "__main__":
    main()
