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
        return [], f"E95 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("lineage", "items", "records", "chains", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return (
        [],
        "E95 invalid input: expected list or dict with lineage/items/records/chains/entries",
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


def _parse_minutes(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _is_convergence_breach(row: dict, max_convergence_minutes: float) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status in {"broken", "missing", "failed", "stalled", "timeout"}:
        return True
    if bool(
        row.get("lineage_gap")
        or row.get("gap")
        or row.get("gap_stalled")
        or row.get("convergence_breach")
    ):
        return True

    convergence = _parse_minutes(
        row.get("convergence_minutes")
        or row.get("gap_convergence_minutes")
        or row.get("repair_minutes")
        or row.get("resolution_minutes")
    )
    if convergence is not None:
        return convergence > max_convergence_minutes

    opened = _parse_datetime(
        row.get("gap_opened_at")
        or row.get("opened_at")
        or row.get("detected_at")
        or row.get("first_seen_at")
    )
    fixed = _parse_datetime(
        row.get("fixed_at")
        or row.get("resolved_at")
        or row.get("closed_at")
        or row.get("observed_at")
    )
    if opened is None or fixed is None:
        return True
    return (fixed - opened).total_seconds() / 60.0 > max_convergence_minutes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lineage", required=True)
    parser.add_argument("--max-gap-convergence-minutes", type=float, default=30.0)
    parser.add_argument("--max-convergence-breaches", type=int, default=0)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.lineage))
    if err:
        print(err, file=sys.stderr)
        return 2

    breaches = sorted(
        {
            _pick(r, ("lineage_id", "artifact_id", "record_id", "id", "name"))
            for r in rows
            if _is_convergence_breach(r, args.max_gap_convergence_minutes)
        }
    )
    if len(breaches) > args.max_convergence_breaches:
        print(
            f"E95 lineage gap convergence breach: {len(breaches)}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
