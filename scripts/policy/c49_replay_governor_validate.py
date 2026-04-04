#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--metrics", required=True)
    p.add_argument("--max-oscillation", type=int, default=5)
    args = p.parse_args()
    m = json.loads(pathlib.Path(args.metrics).read_text())
    osc = m.get("oscillation_events", 0)
    if osc > args.max_oscillation:
        print(f"C49 oscillation too high: {osc}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
