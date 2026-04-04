#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", required=True)
    p.add_argument("--max-wait", type=int, default=3)
    args = p.parse_args()
    data = json.loads(pathlib.Path(args.snapshot).read_text())
    offenders = [x for x in data.get("lanes", []) if x.get("wait_windows", 0) > args.max_wait]
    if offenders:
        print(f"B49 starvation offenders: {len(offenders)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
