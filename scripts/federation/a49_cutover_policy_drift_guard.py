#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib
import sys

def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--policy", required=True)
    p.add_argument("--expected-hash", required=True)
    p.add_argument("--out", default="artifacts/a/a49-cutover-drift-audit.json")
    args = p.parse_args()

    policy = pathlib.Path(args.policy)
    actual = sha256_file(policy)
    status = "pass" if actual == args.expected_hash else "fail"
    out = {
        "task": "A49",
        "policy": str(policy),
        "expected_hash": args.expected_hash,
        "actual_hash": actual,
        "status": status,
    }
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    if status == "fail":
        print("A49 drift detected", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
