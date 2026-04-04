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
        return [], f"E89 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("attestations", "items", "reports", "records", "rows"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return (
        [],
        "E89 invalid input: expected list or dict with attestations/items/reports/records/rows",
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


def _parse_hours(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _is_breached(row: dict, max_ttl_hours: float) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status in {"expired", "invalid", "revoked", "failed"}:
        return True
    if bool(
        row.get("ttl_breach")
        or row.get("expired")
        or row.get("attestation_expired")
        or row.get("revoked")
    ):
        return True

    ttl_value = _parse_hours(
        row.get("ttl_hours")
        or row.get("time_to_live_hours")
        or row.get("lifetime_hours")
        or row.get("remaining_ttl_hours")
    )
    if ttl_value is not None:
        return ttl_value > max_ttl_hours

    started = _parse_datetime(
        row.get("issued_at")
        or row.get("created_at")
        or row.get("observed_at")
        or row.get("generated_at")
    )
    expired = _parse_datetime(
        row.get("expires_at")
        or row.get("expiration")
        or row.get("valid_until")
        or row.get("attestation_expires_at")
    )
    if started is None or expired is None:
        return True
    return (expired - started).total_seconds() / 3600.0 > max_ttl_hours


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestations", required=True)
    parser.add_argument("--max-ttl-hours", type=float, default=12.0)
    parser.add_argument("--max-ttl-violations", type=int, default=0)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.attestations))
    if err:
        print(err, file=sys.stderr)
        return 2

    breached = sorted(
        {
            _pick(r, ("id", "attestation_id", "name", "artifact_id"))
            for r in rows
            if _is_breached(r, args.max_ttl_hours)
        }
    )
    if len(breached) > args.max_ttl_violations:
        print(f"E89 attestation ttl breach: {len(breached)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
