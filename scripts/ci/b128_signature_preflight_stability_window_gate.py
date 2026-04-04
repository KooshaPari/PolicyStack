#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E128 [lane B] signature preflight stability window gate failed: {message}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


def parse_int(value, field):
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid integer value for {field}: {value!r}")


def infer_format(path: pathlib.Path, explicit_format: str) -> str:
    if explicit_format != "auto":
        return explicit_format
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    fail(f"cannot infer input format from suffix={path.suffix!r}; use --format")
    return "json"


def load_records(path: pathlib.Path, fmt: str, records_key: str) -> list[dict]:
    if fmt == "csv":
        try:
            rows = list(csv.DictReader(path.read_text().splitlines()))
        except Exception as exc:
            fail(f"invalid csv input: {exc}")
        if not rows:
            fail("input csv is empty")
        return rows

    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"invalid json input: {exc}")

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        candidate = payload.get(records_key)
        if isinstance(candidate, list):
            rows = candidate
        else:
            rows = [payload]
    else:
        fail("json input must be an object or array")
        rows = []

    if not rows:
        fail("input json resolved to zero records")
    if not all(isinstance(row, dict) for row in rows):
        fail("all records must be JSON objects")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=["auto", "csv", "json"], default="auto")
    parser.add_argument("--records-key", default="records")
    parser.add_argument("--window-key", default="window")
    parser.add_argument("--stability-score-key", default="stability_score")
    parser.add_argument("--instability-events-key", default="instability_events")
    parser.add_argument("--min-average-stability-score", type=float, default=0.0)
    parser.add_argument("--min-window-average-stability-score", type=float, default=0.0)
    parser.add_argument("--max-instability-events", type=int, default=0)
    parser.add_argument("--max-window-instability-events", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    stability_total = 0.0
    instability_events_total = 0
    window_stability_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}
    window_instability_events: dict[str, int] = {}

    for row in records:
        stability_score = parse_float(row.get(args.stability_score_key), args.stability_score_key)
        instability_events = parse_int(
            row.get(args.instability_events_key, 0),
            args.instability_events_key,
        )
        if instability_events < 0:
            fail(
                f"instability events for {args.instability_events_key} must be >= 0; got "
                f"{instability_events}"
            )

        stability_total += stability_score
        instability_events_total += instability_events

        window = str(row.get(args.window_key, "default"))
        window_stability_totals[window] = window_stability_totals.get(window, 0.0) + stability_score
        window_counts[window] = window_counts.get(window, 0) + 1
        window_instability_events[window] = (
            window_instability_events.get(window, 0) + instability_events
        )

    average_stability_score = stability_total / len(records)
    if average_stability_score < args.min_average_stability_score:
        fail(
            f"average_stability_score={average_stability_score} < min_average_stability_score="
            f"{args.min_average_stability_score}"
        )

    if instability_events_total > args.max_instability_events:
        fail(
            f"instability_events={instability_events_total} > max_instability_events="
            f"{args.max_instability_events}"
        )

    for window, count in sorted(window_counts.items()):
        window_average_stability = window_stability_totals[window] / count
        if window_average_stability < args.min_window_average_stability_score:
            fail(
                f"window={window} average_stability_score={window_average_stability} < "
                f"min_window_average_stability_score={args.min_window_average_stability_score}"
            )

        window_events = window_instability_events[window]
        if window_events > args.max_window_instability_events:
            fail(
                f"window={window} instability_events={window_events} > "
                f"max_window_instability_events={args.max_window_instability_events}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
