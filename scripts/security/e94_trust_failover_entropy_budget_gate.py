#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _load_rows(path: pathlib.Path) -> tuple[list[dict], str | None]:
    try:
        if path.suffix.lower() == ".csv":
            return list(csv.DictReader(path.open())), None
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"E94 invalid input: {exc}"

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("failovers", "trust_failovers", "items", "events", "records"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows, None
    return (
        [],
        "E94 invalid input: expected list or dict with "
        "failovers/trust_failovers/items/events/records",
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


def _is_budget_breach(row: dict, min_entropy_budget: float) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status in {"failed", "degraded", "breached", "insufficient"}:
        return True
    if bool(
        row.get("entropy_budget_breach")
        or row.get("entropy_budget_exhausted")
        or row.get("entropy_budget_alert")
    ):
        return True

    budget = _parse_float(
        row.get("entropy_budget")
        or row.get("entropy_budget_remaining")
        or row.get("budget_remaining")
        or row.get("trust_entropy_budget")
    )
    if budget is None:
        return True
    return budget < min_entropy_budget


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failovers", required=True)
    parser.add_argument("--min-entropy-budget", type=float, default=0.25)
    parser.add_argument("--max-budget-breaches", type=int, default=0)
    args = parser.parse_args()

    rows, err = _load_rows(pathlib.Path(args.failovers))
    if err:
        print(err, file=sys.stderr)
        return 2

    breaches = sorted(
        {
            _pick(r, ("failover_id", "id", "event_id", "name"))
            for r in rows
            if _is_budget_breach(r, args.min_entropy_budget)
        }
    )
    if len(breaches) > args.max_budget_breaches:
        print(
            f"E94 trust failover entropy budget breach: {len(breaches)}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
