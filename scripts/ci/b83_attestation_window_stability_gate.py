#!/usr/bin/env python3
import argparse
import csv
from datetime import datetime, timezone
import pathlib
import sys


def parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def parse_csv(path: pathlib.Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text().splitlines()))


p = argparse.ArgumentParser()
p.add_argument("--csv", required=True)
p.add_argument("--start-col", default="window_start")
p.add_argument("--end-col", default="window_end")
p.add_argument("--target-duration-hours", type=float, default=24.0)
p.add_argument("--max-variance-hours", type=float, default=1.0)
p.add_argument("--max-breaches", type=int, default=0)
a = p.parse_args()

rows = parse_csv(pathlib.Path(a.csv))
breaches = 0
for row in rows:
    start_raw = row.get(a.start_col, "")
    end_raw = row.get(a.end_col, "")
    if not start_raw or not end_raw:
        continue
    duration = (parse_ts(end_raw) - parse_ts(start_raw)).total_seconds() / 3600.0
    if abs(duration - a.target_duration_hours) > a.max_variance_hours:
        breaches += 1

if breaches > a.max_breaches:
    print("B83 attestation window stability gate failed", file=sys.stderr)
    raise SystemExit(2)
