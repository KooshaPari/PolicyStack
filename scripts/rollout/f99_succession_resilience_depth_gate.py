#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(msg: str) -> None:
    print(f'F99 succession resilience depth gate failed: {msg}', file=sys.stderr)
    raise SystemExit(2)


def to_int(value: str, field: str) -> int:
    try:
        return int((value or '').strip())
    except ValueError:
        fail(f'invalid integer in {field}: {value!r}')


def to_float(value: str, field: str) -> float:
    try:
        return float((value or '').strip())
    except ValueError:
        fail(f'invalid float in {field}: {value!r}')


def normalized_csv_rows(path: pathlib.Path, expected: list[str]) -> list[dict]:
    rows = list(csv.DictReader(path.read_text().splitlines()))
    if not rows:
        return []
    if list(rows[0].keys()) != expected:
        fail(f'invalid resilience csv header: {list(rows[0].keys())}')
    for row in rows:
        row['resilience_depth'] = to_int(row.get('resilience_depth'), 'resilience_depth')
        row['resilience_score'] = to_float(row.get('resilience_score'), 'resilience_score')
    return sorted(rows, key=lambda row: [row.get(c, '') for c in expected])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--succession', required=True)
    parser.add_argument('--resilience-csv', required=True)
    parser.add_argument('--min-avg-resilience-score', type=float, default=0.0)
    parser.add_argument('--max-low-depth-count', type=int, default=0)
    parser.add_argument('--min-resilience-depth', type=int, default=2)
    parser.add_argument('--max-critical-low-depth-ratio', type=float, default=0.0)
    args = parser.parse_args()

    try:
        config = json.loads(pathlib.Path(args.succession).read_text())
    except Exception:
        fail('invalid succession json')
    if not isinstance(config, dict) or bool(config.get('succession_resilience_tracking_enabled', True)) is not True:
        fail('succession_resilience_tracking_enabled != true')

    rows = normalized_csv_rows(
        pathlib.Path(args.resilience_csv),
        ['role_id', 'resilience_depth', 'resilience_score', 'criticality', 'status'],
    )
    if not rows:
        return 0

    active = [
        row for row in rows
        if (row.get('status') or '').strip().lower() not in {'retired', 'covered', 'complete'}
    ]
    low_depth = [row for row in active if row['resilience_depth'] < args.min_resilience_depth]
    low_depth_critical = [
        row for row in low_depth
        if (row.get('criticality') or '').strip().lower() == 'critical'
    ]
    critical = [row for row in active if (row.get('criticality') or '').strip().lower() == 'critical']
    avg_score = sum(row['resilience_score'] for row in active) / len(active) if active else 0.0
    low_ratio = (len(low_depth_critical) / len(critical)) if critical else 0.0

    if (
        avg_score < args.min_avg_resilience_score
        or len(low_depth) > args.max_low_depth_count
        or low_ratio > args.max_critical_low_depth_ratio
    ):
        fail(
            f'active_roles={len(active)} low_depth_roles={len(low_depth)} '
            f'max_low_depth_count={args.max_low_depth_count} '
            f'low_depth_critical_ratio={low_ratio:.6f} '
            f'max_critical_low_depth_ratio={args.max_critical_low_depth_ratio} '
            f'avg_resilience_score={avg_score:.6f} '
            f'min_avg_resilience_score={args.min_avg_resilience_score}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
