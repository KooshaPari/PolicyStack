#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E144 succession transition window stability gate failed: {message}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def to_float(value: object, field: str, index: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float in {field} at index {index}: {value!r}")


def to_int(value: object, field: str, index: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field} at index {index}: {value!r}")


def load_records(path: pathlib.Path) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            fail("invalid succession csv")
        if not rows:
            fail("succession csv must contain at least one row")
        return [dict(row) for row in rows]

    try:
        payload = json.loads(path.read_text())
    except Exception:
        fail("invalid succession json")

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return list(payload)
    fail("succession payload must be a JSON object or non-empty list of objects")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--succession", required=True)
    parser.add_argument(
        "--transition-window-stability-score-field",
        default="transition_window_stability_score",
    )
    parser.add_argument("--min-transition-window-stability-score", type=float, default=1.0)
    parser.add_argument(
        "--unstable-transition-window-count-field",
        default="unstable_transition_window_count",
    )
    parser.add_argument("--max-unstable-transition-window-count", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.succession))
    for index, record in enumerate(records):
        transition_window_stability_score = to_float(
            record.get(args.transition_window_stability_score_field),
            args.transition_window_stability_score_field,
            index,
        )
        if transition_window_stability_score < args.min_transition_window_stability_score:
            fail(
                f"{args.transition_window_stability_score_field}="
                f"{transition_window_stability_score} < "
                f"{args.min_transition_window_stability_score} at index {index}"
            )

        unstable_transition_window_count = to_int(
            record.get(args.unstable_transition_window_count_field),
            args.unstable_transition_window_count_field,
            index,
        )
        if unstable_transition_window_count > args.max_unstable_transition_window_count:
            fail(
                f"{args.unstable_transition_window_count_field}="
                f"{unstable_transition_window_count} > "
                f"{args.max_unstable_transition_window_count} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
