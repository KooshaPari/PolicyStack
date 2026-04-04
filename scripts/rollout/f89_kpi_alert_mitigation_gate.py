#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def fail(msg: str) -> None:
    print(f'F89 KPI alert mitigation gate failed: {msg}', file=sys.stderr)
    raise SystemExit(2)

def to_int(value: str, field: str) -> int:
    try:
        return int((value or '').strip())
    except ValueError:
        fail(f'invalid integer in {field}: {value!r}')

def normalized_csv_rows(path: pathlib.Path, expected: list[str]) -> list[dict]:
    rows = list(csv.DictReader(path.read_text().splitlines()))
    if not rows:
        return []
    if list(rows[0].keys()) != expected:
        fail(f'invalid alerts csv header: {list(rows[0].keys())}')
    for row in rows:
        row['days_open'] = to_int(row.get('days_open'), 'days_open')
    return sorted(rows, key=lambda row: [row.get(c, '') for c in expected])

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--kpi', required=True)
    parser.add_argument('--alerts-csv', required=True)
    parser.add_argument('--max-unmitigated-alerts', type=int, default=0)
    parser.add_argument('--max-overdue-alert-days', type=int, default=14)
    args = parser.parse_args()
    try:
        config = json.loads(pathlib.Path(args.kpi).read_text())
    except Exception:
        fail('invalid kpi json')
    if not isinstance(config, dict) or bool(config.get('alert_mitigation_enabled', True)) is not True:
        fail('alert_mitigation_enabled != true')

    rows = normalized_csv_rows(
        pathlib.Path(args.alerts_csv),
        ['alert_id', 'metric_id', 'status', 'mitigation_status', 'days_open'],
    )
    unmitigated = [r for r in rows if (r.get('status') or '').strip().lower() != 'closed'
                   and (r.get('mitigation_status') or '').strip().lower() != 'mitigated']
    overdue = [r for r in unmitigated if r['days_open'] > args.max_overdue_alert_days]
    if len(unmitigated) > args.max_unmitigated_alerts or overdue:
        fail(f'unmitigated_alerts={len(unmitigated)} overdue_alerts={len(overdue)} '
             f'max_unmitigated_alerts={args.max_unmitigated_alerts} max_overdue_alert_days={args.max_overdue_alert_days}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
