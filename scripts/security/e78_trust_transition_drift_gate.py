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
        return [], f"E78 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("transitions", "events", "items", "checks", "records"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E78 invalid input: expected list or dict with transitions/events/items/checks/records"


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None or str(value).strip() == "":
            continue
        return str(value).strip()
    return ""


def _time(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _trust_score(value: object) -> int | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    levels = {"critical": 3, "high": 2, "medium": 1, "low": 0, "unknown": -1}
    if raw in levels:
        return levels[raw]
    try:
        return int(float(raw))
    except ValueError:
        return None


def _is_drift(row: dict, max_step: int, max_open_minutes: int) -> bool:
    if str(row.get("drift", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if str(row.get("transition_drift", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return True

    before = _trust_score(_pick(row, ("from_trust", "previous_trust", "source_trust")))
    after = _trust_score(_pick(row, ("to_trust", "new_trust", "target_trust")))
    if before is not None and after is not None and abs(after - before) > max_step:
        return True

    started = _time(_pick(row, ("started_at", "transition_started_at", "created_at")))
    ended = _time(_pick(row, ("ended_at", "completed_at", "transition_ended_at")))
    if started and not ended:
        age_minutes = (datetime.now(timezone.utc) - started).total_seconds() / 60
        return age_minutes > max_open_minutes
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--max-drift", type=int, default=0)
    parser.add_argument("--max-step", type=int, default=1)
    parser.add_argument("--max-open-minutes", type=int, default=180)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.transitions))
    if err:
        print(err, file=sys.stderr)
        return 2

    bad = sorted(
        {
            _pick(row, ("transition_id", "id", "artifact_id", "name"))
            for row in rows
            if _is_drift(row, args.max_step, args.max_open_minutes)
        }
    )
    if len(bad) > args.max_drift:
        print(f"E78 trust transition drift breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
