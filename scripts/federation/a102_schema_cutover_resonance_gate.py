#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"A102 schema cutover resonance gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(value: str, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError:
        fail(f"invalid float in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-events", required=True)
    parser.add_argument("--cutover-csv", required=True)
    parser.add_argument("--max-resonance", type=float, default=0.0)
    parser.add_argument("--max-oscillations", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.cutover_csv).read_text().splitlines()))
    if not rows:
        fail("cutover-csv has no rows")

    resonances = []
    oscillations = 0
    for row in rows:
        value = to_float(row.get("resonance", "0.0"), "resonance")
        resonances.append(value)
        if value > args.max_resonance:
            fail(f"resonance breach={value}")
        if row.get("status", "").strip().lower() in {"oscillating", "unstable"}:
            oscillations += 1

    if oscillations > args.max_oscillations:
        fail(f"oscillations={oscillations}")

    peak = max(abs(v) for v in resonances)
    if peak > args.max_resonance:
        fail(f"peak_resonance={peak}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
