#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys
from datetime import datetime, timezone


def _parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


p = argparse.ArgumentParser()
p.add_argument("--csv", required=True)
p.add_argument("--start-col", default="window_start")
p.add_argument("--end-col", default="window_end")
p.add_argument("--max-gap-hours", type=float, default=0.0)
p.add_argument("--max-breaches", type=int, default=0)
a = p.parse_args()

rows = list(csv.DictReader(pathlib.Path(a.csv).read_text().splitlines()))
breaches = 0
for row in rows:
    start_raw = row.get(a.start_col, "")
    end_raw = row.get(a.end_col, "")
    if not start_raw or not end_raw:
        continue
    gap = _parse_ts(end_raw) - _parse_ts(start_raw)
    if gap.total_seconds() / 3600.0 > a.max_gap_hours:
        breaches += 1

if breaches > a.max_breaches:
    print("B79 attestation window gap gate failed", file=sys.stderr)
    raise SystemExit(2)

