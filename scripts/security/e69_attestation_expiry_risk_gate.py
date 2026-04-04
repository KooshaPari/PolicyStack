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
        if isinstance(data.get("attestations"), list):
            return data["attestations"]
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

def _at_risk_expired(r: dict, now: datetime) -> bool:
    expiry = _dt(r.get("expires_at") or r.get("expiry_at") or r.get("valid_until"))
    waived = bool(r.get("waived") or r.get("accepted_risk") or r.get("exception"))
    if expiry is None or waived:
        return False
    return expiry <= now

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--attestations", required=True)
    p.add_argument("--max-expired-at-risk", type=int, default=0)
    a = p.parse_args()
    now = datetime.now(timezone.utc)
    bad = [str(r.get("attestation_id") or r.get("id") or r.get("asset_id") or "") for r in _rows(pathlib.Path(a.attestations)) if _at_risk_expired(r, now)]
    if len(bad) > a.max_expired_at_risk:
        bad.sort()
        print(f"E69 attestation expiry risk breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
