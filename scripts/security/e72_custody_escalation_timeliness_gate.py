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
        if isinstance(data.get("custody"), list):
            return data["custody"]
        if isinstance(data.get("cases"), list):
            return data["cases"]
        if isinstance(data.get("items"), list):
            return data["items"]
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

def _late(r: dict, max_minutes: int) -> bool:
    needs = bool(r.get("escalation_required") or r.get("sla_breached") or str(r.get("status", "")).strip().lower() in {"breached", "open_breach"})
    if not needs:
        return False
    start = _dt(r.get("breached_at") or r.get("detected_at") or r.get("opened_at") or r.get("created_at"))
    escalated = _dt(r.get("escalated_at") or r.get("escalation_at") or r.get("paged_at"))
    if start is None:
        return False
    if escalated is None:
        return True
    return (escalated - start).total_seconds() > max_minutes * 60

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--custody", required=True)
    p.add_argument("--max-escalation-minutes", type=int, default=60)
    p.add_argument("--max-late-escalations", type=int, default=0)
    a = p.parse_args()
    bad = [str(r.get("id") or r.get("case_id") or r.get("artifact_id") or "") for r in _rows(pathlib.Path(a.custody)) if _late(r, a.max_escalation_minutes)]
    if len(bad) > a.max_late_escalations:
        bad.sort()
        print(f"E72 custody escalation timeliness breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
