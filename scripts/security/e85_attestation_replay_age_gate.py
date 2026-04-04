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
        return [], f"E85 invalid input: {exc}"
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("attestations", "replays", "events", "items", "rows"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E85 invalid input: expected list or dict with attestations/replays/events/items/rows"


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _parse_time(v: object) -> datetime | None:
    if v is None:
        return None
    text = str(v).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _is_replay(row: dict) -> bool:
    for key in ("is_replay", "replayed", "replay", "is_replayed"):
        text = str(row.get(key, "")).strip().lower()
        if text in {"1", "true", "yes", "on", "y"}:
            return True
    return False


def _is_stale(row: dict, max_age_hours: int) -> bool:
    if str(row.get("status", "")).strip().lower() in {"failed", "invalid", "stale", "timed_out"}:
        return True

    ts = (
        row.get("replayed_at")
        or row.get("replay_at")
        or row.get("observed_at")
        or row.get("verified_at")
        or row.get("checked_at")
        or row.get("created_at")
    )
    observed = _parse_time(ts)
    if observed is None:
        return True
    return (datetime.now(timezone.utc) - observed).total_seconds() > max_age_hours * 3600


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--attestations", required=True)
    p.add_argument("--max-stale-replays", type=int, default=0)
    p.add_argument("--max-age-hours", type=int, default=48)
    args = p.parse_args()

    rows, err = _load_rows(pathlib.Path(args.attestations))
    if err:
        print(err, file=sys.stderr)
        return 2

    stale = sorted(
        {
            _pick(r, ("attestation_id", "id", "event_id", "name"))
            for r in rows
            if _is_replay(r) and _is_stale(r, args.max_age_hours)
        }
    )
    if len(stale) > args.max_stale_replays:
        print(f"E85 attestation replay age breach: {len(stale)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
