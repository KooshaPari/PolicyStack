#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    args = p.parse_args()
    rows = list(csv.DictReader(pathlib.Path(args.csv).open()))
    missing = [r for r in rows if not r.get("closure_evidence")]
    if missing:
        print(f"F49 missing closure evidence: {len(missing)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
