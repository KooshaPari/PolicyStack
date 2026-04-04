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
        return [], f"E82 invalid input: {exc}"
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("failovers", "trust_failovers", "items", "events", "records"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E82 invalid input: expected list or dict with failovers/trust_failovers/items/events/records"


def _parse_datetime(v: object) -> datetime | None:
    if v is None:
        return None
    text = str(v).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _is_breached(r: dict, max_minutes: int) -> bool:
    if str(r.get("status", "")).strip().lower() in {"failed", "breached", "degraded", "timed_out"}:
        return True
    if bool(r.get("breach") or r.get("window_breach")):
        return True
    start = _parse_datetime(r.get("started_at") or r.get("failover_started_at") or r.get("detected_at"))
    end = _parse_datetime(r.get("ended_at") or r.get("resolved_at") or r.get("recovered_at"))
    if start is None:
        return True
    if end is None:
        return True
    return (end - start).total_seconds() > max_minutes * 60


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--failovers", required=True)
    p.add_argument("--max-open-failovers", type=int, default=0)
    p.add_argument("--max-window-minutes", type=int, default=30)
    args = p.parse_args()
    rows, err = _load_rows(pathlib.Path(args.failovers))
    if err:
        print(err, file=sys.stderr)
        return 2
    bad = sorted(
        {
            str(r.get("id") or r.get("failover_id") or r.get("name") or "")
            for r in rows
            if _is_breached(r, args.max_window_minutes)
        }
    )
    if len(bad) > args.max_open_failovers:
        print(f"E82 trust failover window breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
