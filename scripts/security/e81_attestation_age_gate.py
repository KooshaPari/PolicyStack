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
        return [], f"E81 invalid input: {exc}"
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("attestations", "items", "reports", "rows"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E81 invalid input: expected list or dict with attestations/items/reports/rows"


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


def _is_stale(r: dict, max_age_hours: int) -> bool:
    if str(r.get("status", "")).strip().lower() in {"failed", "invalid", "stale"}:
        return True
    ts = (
        r.get("updated_at")
        or r.get("refresh_at")
        or r.get("checked_at")
        or r.get("created_at")
        or r.get("observed_at")
    )
    seen = _parse_datetime(ts)
    if seen is None:
        return True
    return (datetime.now(timezone.utc) - seen).total_seconds() > max_age_hours * 3600


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--attestations", required=True)
    p.add_argument("--max-age-hours", type=int, default=24)
    p.add_argument("--max-stale-attestations", type=int, default=0)
    args = p.parse_args()
    rows, err = _load_rows(pathlib.Path(args.attestations))
    if err:
        print(err, file=sys.stderr)
        return 2
    stale = sorted(
        {
            str(r.get("id") or r.get("attestation_id") or r.get("name") or "")
            for r in rows
            if _is_stale(r, args.max_age_hours)
        }
    )
    if len(stale) > args.max_stale_attestations:
        print(f"E81 attestation age gate breach: {len(stale)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
