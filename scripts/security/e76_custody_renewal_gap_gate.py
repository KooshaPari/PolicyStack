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
        return [], f"E76 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("custody", "cases", "items", "records"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return [], "E76 invalid input: expected list or dict with custody/cases/items/records"


def _parse_datetime(v: object) -> datetime | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _is_renewal_gap(r: dict, max_gap_days: int) -> bool:
    if bool(r.get("renewal_complete") or r.get("renewed") or r.get("active")):
        return False
    due = _parse_datetime(r.get("renewal_due") or r.get("expires_at") or r.get("valid_until"))
    if due is None:
        status = str(r.get("status", "")).strip().lower()
        return status in {"renewal_overdue", "overdue", "expired", "open"}
    now = datetime.now(timezone.utc)
    if now <= due:
        return False
    gap_seconds = (now - due).total_seconds()
    return gap_seconds > max_gap_days * 86400


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--custody", required=True)
    p.add_argument("--max-gap-days", type=int, default=0)
    p.add_argument("--max-renewal-gaps", type=int, default=0)
    args = p.parse_args()
    rows, err = _load_rows(pathlib.Path(args.custody))
    if err:
        print(err, file=sys.stderr)
        return 2
    bad = [str(r.get("id") or r.get("custody_id") or r.get("case_id") or "") for r in rows if _is_renewal_gap(r, args.max_gap_days)]
    if len(bad) > args.max_renewal_gaps:
        bad.sort()
        print(f"E76 custody renewal gap breach: {len(bad)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
