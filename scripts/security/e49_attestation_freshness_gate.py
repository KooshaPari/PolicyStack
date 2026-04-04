#!/usr/bin/env python3
import argparse
import csv
import datetime
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--max-age-days", type=int, default=30)
    args = p.parse_args()
    now = datetime.datetime.utcnow().date()
    rows = list(csv.DictReader(pathlib.Path(args.csv).open()))
    stale = []
    for r in rows:
        d = datetime.date.fromisoformat(r["last_verified"])
        if (now - d).days > args.max_age_days:
            stale.append(r)
    if stale:
        print(f"E49 stale attestations: {len(stale)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
