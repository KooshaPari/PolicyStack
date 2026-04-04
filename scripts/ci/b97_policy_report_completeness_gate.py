#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B97 policy report completeness gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--metric-key", default="policy_score")
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--max-score", type=float, default=0.0)
    parser.add_argument("--required-sections", default="")
    args = parser.parse_args()

    try:
        report = json.loads(pathlib.Path(args.report).read_text())
    except Exception as exc:
        fail(f"invalid report json: {exc}")
    if not isinstance(report, dict):
        fail("report must be a JSON object")

    required_sections = [item.strip() for item in args.required_sections.split(",") if item.strip()]
    for section in sorted(required_sections):
        if section not in report:
            fail(f"missing required section: {section}")

    score = parse_float(report.get(args.metric_key), args.metric_key)
    if score < args.min_score or score > args.max_score:
        fail(f"policy_score={score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
