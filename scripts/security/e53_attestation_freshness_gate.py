#!/usr/bin/env python3
import argparse
import json
import pathlib
import datetime
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", required=True)
    p.add_argument("--max-age-days", type=int, default=30)
    args = p.parse_args()
    now = datetime.datetime.utcnow().date()
    data = json.loads(pathlib.Path(args.json).read_text())
    stale = []
    for item in data:
        d = datetime.date.fromisoformat(item["verified_on"])
        if (now - d).days > args.max_age_days:
            stale.append(item)
    if stale:
        print(f"E53 stale attestations: {len(stale)}", file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
