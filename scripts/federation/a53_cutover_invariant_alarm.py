#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--invariants", required=True)
    p.add_argument("--out", default="artifacts/a/a53-invariant-alarm.json")
    args = p.parse_args()
    data = json.loads(pathlib.Path(args.invariants).read_text())
    failed = [x for x in data.get("checks", []) if x.get("status") != "pass"]
    out = {"task":"A53","failed":failed,"count":len(failed)}
    op = pathlib.Path(args.out); op.parent.mkdir(parents=True, exist_ok=True); op.write_text(json.dumps(out, indent=2)+"\n")
    if failed:
        print("A53 invariant failures detected", file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
