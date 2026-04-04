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
        return [], f"E79 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("lineage", "records", "items", "events", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E79 invalid input: expected list or dict with lineage/records/items/events/entries"


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


def _in_window_violation(row: dict, max_age_minutes: int) -> bool:
    if str(row.get("integrity_breach", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if str(row.get("integrity_status", "")).strip().lower() in {"broken", "mismatch", "tampered", "invalid"}:
        return True

    verified = _time(_pick(row, ("verified_at", "integrity_checked_at", "checked_at")))
    if verified is None:
        return True

    age_minutes = (datetime.now(timezone.utc) - verified).total_seconds() / 60
    return age_minutes > max_age_minutes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lineage", required=True)
    parser.add_argument("--max-integrity-window", type=int, default=0)
    parser.add_argument("--max-age-minutes", type=int, default=120)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.lineage))
    if err:
        print(err, file=sys.stderr)
        return 2

    bad = sorted(
        {
            _pick(row, ("lineage_id", "id", "artifact_id", "name"))
            for row in rows
            if _in_window_violation(row, args.max_age_minutes)
        }
    )
    if len(bad) > args.max_integrity_window:
        print(f"E79 lineage integrity window breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
