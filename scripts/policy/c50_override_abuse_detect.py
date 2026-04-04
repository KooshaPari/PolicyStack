#!/usr/bin/env python3
import argparse
import json
import pathlib

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--events", required=True)
    p.add_argument("--out", default="artifacts/c/c50-override-anomalies.json")
    args = p.parse_args()
    ev = json.loads(pathlib.Path(args.events).read_text())
    anomalies = [e for e in ev if e.get("override_count", 0) > 3]
    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"task":"C50","anomalies":anomalies}, indent=2)+"\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
