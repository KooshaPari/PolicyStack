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
        return [], f"E92 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("custody", "chains", "items", "records", "lineage", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return (
        [],
        "E92 invalid input: expected list or dict with "
        "custody/chains/items/records/lineage/entries",
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


def _parse_seconds(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _is_delay_breach(row: dict, max_delay_minutes: float) -> bool:
    if str(row.get("status", "")).strip().lower() in {"broken", "missing", "invalid", "failed"}:
        return True
    if bool(
        row.get("chain_delay")
        or row.get("delay_breach")
        or row.get("handoff_delay")
        or row.get("handoff_breach")
    ):
        return True

    delay = _parse_seconds(
        row.get("chain_delay_seconds") or row.get("delay_seconds") or row.get("handoff_seconds")
    )
    if delay is not None:
        return delay / 60.0 > max_delay_minutes

    started = _parse_datetime(
        row.get("segment_started_at")
        or row.get("created_at")
        or row.get("observed_at")
        or row.get("handoff_started_at")
    )
    finished = _parse_datetime(
        row.get("segment_ended_at")
        or row.get("updated_at")
        or row.get("handoff_completed_at")
        or row.get("delivered_at")
    )
    if started is None or finished is None:
        return True
    return (finished - started).total_seconds() / 60.0 > max_delay_minutes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--custody", required=True)
    parser.add_argument("--max-delay-minutes", type=float, default=15.0)
    parser.add_argument("--max-delayed-chains", type=int, default=0)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.custody))
    if err:
        print(err, file=sys.stderr)
        return 2

    delayed = sorted(
        {
            _pick(r, ("chain_id", "custody_chain_id", "id", "artifact_id", "name"))
            for r in rows
            if _is_delay_breach(r, args.max_delay_minutes)
        }
    )
    if len(delayed) > args.max_delayed_chains:
        print(f"E92 custody chain delay breach: {len(delayed)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
