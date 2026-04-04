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
        if isinstance(data.get("breaches"), list):
            return data["breaches"]
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("custody"), list):
            return data["custody"]
    return []

def _is_open_breach(r: dict) -> bool:
    breached = bool(r.get("sla_breached") or str(r.get("status", "")).lower() == "breached")
    remediated = bool(r.get("remediated") or r.get("resolved") or r.get("waived"))
    return breached and not remediated

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--custody", required=True)
    p.add_argument("--max-open-breaches", type=int, default=0)
    a = p.parse_args()
    open_breaches = [str(r.get("id") or r.get("case_id") or r.get("artifact_id") or "") for r in _rows(pathlib.Path(a.custody)) if _is_open_breach(r)]
    if len(open_breaches) > a.max_open_breaches:
        open_breaches.sort()
        print(f"E68 custody SLA enforcement breach: {len(open_breaches)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
