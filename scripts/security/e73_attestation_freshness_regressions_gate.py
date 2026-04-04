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
        return [], f"E73 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("attestations", "items", "reports", "rows"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E73 invalid input: expected list or dict with attestations/items/reports/rows"


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


def _is_regression(row: dict, max_age_hours: int) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status in {"regressed", "failed", "degraded", "stale"}:
        return True
    if bool(row.get("regression") or row.get("freshness_regression") or row.get("stale")):
        return True
    age = row.get("age_hours") or row.get("hours_since_refresh") or row.get("staleness_hours")
    if age is not None:
        try:
            if float(age) > float(max_age_hours):
                return True
        except (TypeError, ValueError):
            pass
    observed = _parse_datetime(row.get("observed_at") or row.get("refreshed_at") or row.get("created_at"))
    if observed is not None:
        age_hours = (datetime.now(timezone.utc) - observed).total_seconds() / 3600.0
        return age_hours > max_age_hours
    return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--attestations", required=True)
    p.add_argument("--max-regressions", type=int, default=0)
    p.add_argument("--max-age-hours", type=int, default=24)
    args = p.parse_args()
    rows, err = _load_rows(pathlib.Path(args.attestations))
    if err:
        print(err, file=sys.stderr)
        return 2
    bad = [str(r.get("id") or r.get("attestation_id") or r.get("name") or "") for r in rows if _is_regression(r, args.max_age_hours)]
    if len(bad) > args.max_regressions:
        bad.sort()
        print(f"E73 attestation freshness regressions: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
