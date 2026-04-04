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
        return [], f"E80 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("custody", "chains", "items", "records", "cases"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E80 invalid input: expected list or dict with custody/chains/items/records/cases"


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


def _is_expired(row: dict) -> bool:
    if str(row.get("waived", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return False
    if str(row.get("chain_expired", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if str(row.get("status", "")).strip().lower() in {"expired", "expired_chain", "stale", "invalid"}:
        return True

    expiry = _time(_pick(row, ("chain_expires_at", "expires_at", "expiry_at", "valid_until")))
    if expiry is None:
        return False
    return datetime.now(timezone.utc) > expiry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--custody", required=True)
    parser.add_argument("--max-expired-chains", type=int, default=0)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.custody))
    if err:
        print(err, file=sys.stderr)
        return 2

    bad = sorted(
        {
            _pick(row, ("chain_id", "custody_chain_id", "id", "name"))
            for row in rows
            if _is_expired(row)
        }
    )
    if len(bad) > args.max_expired_chains:
        print(f"E80 custody chain expiry breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
