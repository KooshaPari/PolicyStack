#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
from datetime import datetime, timezone

def _rows(path: pathlib.Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(path.open()))
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("inventory"), list):
            return data["inventory"]
    return []

def _dt(v: object) -> datetime | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--inventory", required=True)
    p.add_argument("--max-age-hours", type=int, default=24)
    a = p.parse_args()
    now = datetime.now(timezone.utc)
    stale = []
    for r in _rows(pathlib.Path(a.inventory)):
        key = str(r.get("attestation_id") or r.get("id") or r.get("asset_id") or "")
        ts = _dt(r.get("updated_at") or r.get("attested_at") or r.get("last_verified"))
        if ts is None or (now - ts).total_seconds() > a.max_age_hours * 3600:
            stale.append(key)
    if stale:
        stale.sort()
        print(f"E65 attestation inventory freshness breach: {len(stale)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
