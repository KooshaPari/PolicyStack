#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--max-starved", type=int, default=0)
    args = p.parse_args()
    rows = list(csv.DictReader(pathlib.Path(args.csv).open()))
    starved = [r for r in rows if int(r.get("starved_windows", "0")) > 0]
    if len(starved) > args.max_starved:
        print(f"B53 starvation kill-switch tripped: {len(starved)}", file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
