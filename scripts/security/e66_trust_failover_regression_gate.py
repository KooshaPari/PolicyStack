#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def _rows(path: pathlib.Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(path.open()))
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("regressions"), list):
            return data["regressions"]
        if isinstance(data.get("checks"), list):
            return data["checks"]
        if isinstance(data.get("signals"), list):
            return data["signals"]
    return []

def _is_regression(r: dict) -> bool:
    if bool(r.get("regression")):
        return True
    status = str(r.get("status", "")).strip().lower()
    if status in {"regressed", "failed", "degraded"}:
        return True
    try:
        if float(r.get("delta", 0)) < 0:
            return True
    except (TypeError, ValueError):
        pass
    return False

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True)
    p.add_argument("--max-regressions", type=int, default=0)
    a = p.parse_args()
    bad = [str(r.get("id") or r.get("check") or r.get("name") or "") for r in _rows(pathlib.Path(a.report)) if _is_regression(r)]
    if len(bad) > a.max_regressions:
        bad.sort()
        print(f"E66 trust failover regressions: {len(bad)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
