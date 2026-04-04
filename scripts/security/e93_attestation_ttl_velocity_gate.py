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
        return [], f"E93 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("attestations", "items", "records", "events", "rows"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return (
        [],
        "E93 invalid input: expected list or dict with "
        "attestations/items/records/events/rows",
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


def _parse_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _derive_velocity(row: dict) -> float | None:
    for key in (
        "ttl_velocity",
        "ttl_decay_rate",
        "velocity",
        "ttl_rate",
        "consumption_rate",
    ):
        value = _parse_float(row.get(key))
        if value is not None:
            return value

    ttl_hours = _parse_float(
        row.get("ttl_hours")
        or row.get("time_to_live_hours")
        or row.get("lifetime_hours")
    )
    remaining_hours = _parse_float(
        row.get("remaining_ttl_hours")
        or row.get("remaining_ttl")
        or row.get("ttl_remaining_hours")
    )
    started = _parse_datetime(
        row.get("issued_at") or row.get("created_at") or row.get("observed_at")
    )
    now = _parse_datetime(row.get("checked_at") or row.get("evaluated_at"))
    if now is None:
        now = datetime.now(timezone.utc)
    if ttl_hours is None or remaining_hours is None:
        return None
    elapsed_hours = (now - started).total_seconds() / 3600.0 if started else None
    if elapsed_hours is None or elapsed_hours <= 0:
        return None
    return (ttl_hours - remaining_hours) / elapsed_hours


def _is_velocity_breach(row: dict, max_velocity: float) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status in {"expired", "invalid", "revoked", "failed"}:
        return True
    if bool(
        row.get("ttl_velocity_breach")
        or row.get("ttl_breach")
        or row.get("attestation_expired")
    ):
        return True

    velocity = _derive_velocity(row)
    if velocity is None:
        return True
    return velocity > max_velocity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestations", required=True)
    parser.add_argument("--max-ttl-velocity", type=float, default=0.5)
    parser.add_argument("--max-velocity-breaches", type=int, default=0)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.attestations))
    if err:
        print(err, file=sys.stderr)
        return 2

    breaches = sorted(
        {
            _pick(r, ("attestation_id", "id", "name", "artifact_id"))
            for r in rows
            if _is_velocity_breach(r, args.max_ttl_velocity)
        }
    )
    if len(breaches) > args.max_velocity_breaches:
        print(
            f"E93 attestation ttl velocity breach: {len(breaches)}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
