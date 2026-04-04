#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        _fail(f"D83 missing {label} file: {path}")


def _load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        _fail(f"D83 invalid JSON {path}: {exc}")
    if not isinstance(data, dict):
        _fail(f"D83 JSON must be an object: {path}")
    return data


def _load_csv(path: pathlib.Path, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required_headers - set(reader.fieldnames or []))
            if missing:
                _fail(f"D83 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        _fail(f"D83 invalid CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        _fail(f"D83 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--window-csv", required=True)
    parser.add_argument("--max-window-variance", type=float, default=0.0)
    parser.add_argument("--max-window-worsen-count", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.window_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "window")

    report = _load_json(report_path)
    rows = _load_csv(csv_path, {"window_start", "open_escalations"})
    if not rows:
        _fail("D83 escalation window gate failed: empty window csv")

    windows = sorted(rows, key=lambda row: (row.get("window_start") or "").strip())
    values = [
        _to_float(r.get("open_escalations", ""), csv_path, "open_escalations")
        for r in windows
    ]

    variance = 0.0
    worsening = 0
    for previous, current in zip(values, values[1:]):
        step = current - previous
        variance = max(variance, step)
        if current > previous:
            worsening += 1

    effective_variance = max(
        variance,
        float(report.get("escalation_window_variance", 0.0)),
    )
    effective_worsening = max(
        worsening,
        int(report.get("escalation_window_worsening", 0)),
    )

    if effective_variance > args.max_window_variance:
        _fail(
            f"D83 escalation window gate failed: max_window_variance={effective_variance}"
        )
    if effective_worsening > args.max_window_worsen_count:
        _fail(
            f"D83 escalation window gate failed: worsening_windows={effective_worsening}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
