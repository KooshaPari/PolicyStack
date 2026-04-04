#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--matrix", required=True)
    p.add_argument("--client", required=True)
    p.add_argument("--server", required=True)
    args = p.parse_args()
    m = json.loads(pathlib.Path(args.matrix).read_text())
    key = f"{args.client}:{args.server}"
    allowed = set(m.get("allowed_pairs", []))
    if key not in allowed:
        print(f"A50 incompatible schema pair: {key}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
