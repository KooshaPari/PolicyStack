#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rules", required=True)
    p.add_argument("--manifest", required=True)
    args = p.parse_args()
    rules = json.loads(pathlib.Path(args.rules).read_text())
    mf = json.loads(pathlib.Path(args.manifest).read_text())
    required = rules.get("required_fields", [])
    miss = [f for f in required if f not in mf]
    if miss:
        print("B50 missing fields: " + ",".join(miss), file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
