#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--items", required=True)
    args = p.parse_args()
    items = json.loads(pathlib.Path(args.items).read_text())
    missing = [i for i in items if not i.get("closure_evidence") or not i.get("owner")]
    if missing:
        print(f"F53 incomplete KPI closures: {len(missing)}", file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
