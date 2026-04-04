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
        return [], f"E90 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("failovers", "trust_failovers", "items", "events", "records"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return (
        [],
        "E90 invalid input: expected list or dict with "
        "failovers/trust_failovers/items/events/records",
    )


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


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


def _parse_minutes(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _is_slippage(row: dict, expected_max_slippage_minutes: float) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status in {"failed", "breached", "degraded", "timed_out"}:
        return True
    if bool(
        row.get("slippage")
        or row.get("window_breach")
        or row.get("slo_breach")
        or row.get("trust_window_breach")
    ):
        return True

    start = _parse_datetime(
        row.get("started_at")
        or row.get("failover_started_at")
        or row.get("window_start")
        or row.get("detected_at")
    )
    ended = _parse_datetime(
        row.get("ended_at")
        or row.get("recovered_at")
        or row.get("restored_at")
        or row.get("resolved_at")
    )
    if start is None or ended is None:
        return True
    duration_minutes = (ended - start).total_seconds() / 60.0

    slippage = _parse_minutes(
        row.get("window_slippage_minutes")
        or row.get("slippage_minutes")
        or row.get("extra_minutes")
        or row.get("drift_minutes")
    )
    if slippage is not None:
        return slippage > expected_max_slippage_minutes

    expected_window = _parse_minutes(
        row.get("window_minutes")
        or row.get("expected_window_minutes")
        or row.get("target_window_minutes")
        or row.get("sla_window_minutes")
    )
    if expected_window is None:
        return duration_minutes > expected_max_slippage_minutes

    return max(0.0, duration_minutes - expected_window) > expected_max_slippage_minutes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failovers", required=True)
    parser.add_argument("--max-window-slippage-minutes", type=float, default=0.0)
    parser.add_argument("--max-breached-failovers", type=int, default=0)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.failovers))
    if err:
        print(err, file=sys.stderr)
        return 2

    breached = sorted(
        {
            _pick(r, ("id", "failover_id", "event_id", "name"))
            for r in rows
            if _is_slippage(r, args.max_window_slippage_minutes)
        }
    )
    if len(breached) > args.max_breached_failovers:
        print(
            f"E90 trust failover window slippage breach: {len(breached)}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
