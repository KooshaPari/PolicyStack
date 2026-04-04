#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
from datetime import datetime, timezone

def _load_rows(path: pathlib.Path) -> tuple[list[dict], str | None]:
    try:
        if path.suffix.lower() == ".csv":
            return list(csv.DictReader(path.open())), None
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"E74 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("failovers", "items", "checks", "reports", "events"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E74 invalid input: expected list or dict with failovers/items/checks/reports/events"


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _is_breached(row: dict, max_minutes: int) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status in {"breached", "failed", "degraded", "failover_failed", "timed_out"}:
        return True
    if bool(row.get("sla_breached") or row.get("trust_breach") or row.get("breach")):
        return True
    start = _parse_datetime(row.get("started_at") or row.get("failover_started_at") or row.get("detected_at"))
    restored = _parse_datetime(row.get("restored_at") or row.get("recovered_at") or row.get("ended_at"))
    if start is None:
        return False
    if restored is None:
        return True
    return (restored - start).total_seconds() > max_minutes * 60


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--failovers", required=True)
    p.add_argument("--max-sla-breaches", type=int, default=0)
    p.add_argument("--max-sla-minutes", type=int, default=30)
    args = p.parse_args()
    rows, err = _load_rows(pathlib.Path(args.failovers))
    if err:
        print(err, file=sys.stderr)
        return 2
    bad = [str(r.get("id") or r.get("name") or r.get("failover_id") or "") for r in rows if _is_breached(r, args.max_sla_minutes)]
    if len(bad) > args.max_sla_breaches:
        bad.sort()
        print(f"E74 trust failover SLA breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
