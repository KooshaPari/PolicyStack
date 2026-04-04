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
        if isinstance(data.get("checks"), list):
            return data["checks"]
        if isinstance(data.get("signals"), list):
            return data["signals"]
        if isinstance(data.get("failover"), list):
            return data["failover"]
    return []

def _inconsistent(r: dict) -> bool:
    if bool(r.get("inconsistent") or r.get("trust_mismatch")):
        return True
    p = str(r.get("primary_trust") or r.get("primary_status") or "").strip().lower()
    f = str(r.get("failover_trust") or r.get("failover_status") or "").strip().lower()
    if p and f and p != f:
        return True
    ph = str(r.get("primary_hash") or r.get("primary_digest") or "").strip()
    fh = str(r.get("failover_hash") or r.get("failover_digest") or "").strip()
    return bool(ph and fh and ph != fh)

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True)
    p.add_argument("--max-inconsistencies", type=int, default=0)
    a = p.parse_args()
    bad = [str(r.get("id") or r.get("check") or r.get("region") or r.get("name") or "") for r in _rows(pathlib.Path(a.report)) if _inconsistent(r)]
    if len(bad) > a.max_inconsistencies:
        bad.sort()
        print(f"E70 failover trust consistency breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
