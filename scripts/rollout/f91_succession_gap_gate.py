#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def fail(msg: str) -> None:
    print(f'F91 succession gap gate failed: {msg}', file=sys.stderr)
    raise SystemExit(2)

def normalized_csv_rows(path: pathlib.Path, expected: list[str]) -> list[dict]:
    rows = list(csv.DictReader(path.read_text().splitlines()))
    if not rows:
        return []
    if list(rows[0].keys()) != expected:
        fail(f'invalid succession gaps csv header: {list(rows[0].keys())}')
    return sorted(rows, key=lambda row: [row.get(c, '') for c in expected])

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--succession', required=True)
    parser.add_argument('--gaps-csv', required=True)
    parser.add_argument('--max-open-gaps', type=int, default=0)
    parser.add_argument('--max-critical-gap-ratio', type=float, default=0.0)
    args = parser.parse_args()

    try:
        config = json.loads(pathlib.Path(args.succession).read_text())
    except Exception:
        fail('invalid succession json')
    if not isinstance(config, dict) or bool(config.get('succession_gap_tracking_enabled', True)) is not True:
        fail('succession_gap_tracking_enabled != true')

    rows = normalized_csv_rows(
        pathlib.Path(args.gaps_csv),
        ['role_id', 'gap_status', 'criticality', 'owner', 'days_open'],
    )
    open_gaps = [r for r in rows if (r.get('gap_status') or '').strip().lower() != 'filled']
    critical_gaps = [r for r in rows if (r.get('criticality') or '').strip().lower() == 'critical']
    critical_open = [r for r in critical_gaps if (r.get('gap_status') or '').strip().lower() != 'filled']
    ratio = (len(critical_open) / len(critical_gaps)) if critical_gaps else 0.0
    if len(open_gaps) > args.max_open_gaps or ratio > args.max_critical_gap_ratio:
        fail(f'open_gaps={len(open_gaps)} critical_gaps={len(critical_gaps)} '
             f'critical_gap_ratio={ratio:.6f} max_open_gaps={args.max_open_gaps} '
             f'max_critical_gap_ratio={args.max_critical_gap_ratio}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
