#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C113 forensic bundle alert gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forensics", required=True)
    parser.add_argument("--max-critical-alerts", type=int, default=0)
    parser.add_argument("--max-warning-alerts", type=int, default=0)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.forensics).read_text())
    alerts = payload.get("alerts", payload) if isinstance(payload, dict) else payload
    if not isinstance(alerts, list):
        fail("forensics JSON must be a list or contain alerts")

    critical = 0
    warning = 0
    for entry in alerts:
        if not isinstance(entry, dict):
            continue
        severity = str(entry.get("severity", "")).strip().lower()
        if severity == "critical":
            critical += 1
        if severity == "warning":
            warning += 1

    if args.max_critical_alerts and critical > args.max_critical_alerts:
        fail(f"critical_alerts={critical}")

    if args.max_warning_alerts and warning > args.max_warning_alerts:
        fail(f"warning_alerts={warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
