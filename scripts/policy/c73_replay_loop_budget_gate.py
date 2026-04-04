#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v):
    return str(v).strip().lower() in {'1', 'true', 't', 'yes', 'y'}


def _num(v, default=0.0):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return float(default)


def _loop_id(r):
    return str(r.get('id') or r.get('loop_id') or r.get('name') or '?').strip()


p = argparse.ArgumentParser()
p.add_argument('--loops-json', required=True)
p.add_argument('--loop-csv', required=True)
p.add_argument('--max-loop-breaches', type=int, default=0)
p.add_argument('--max-loop-budget-ms', type=float, default=5000.0)
a = p.parse_args()

loops = json.loads(pathlib.Path(a.loops_json).read_text())
rows = sorted(
    list(csv.DictReader(pathlib.Path(a.loop_csv).read_text().splitlines())),
    key=lambda r: json.dumps(r, sort_keys=True),
)

if isinstance(loops, dict):
    loops = loops.get('loops', loops.get('items', []))

breaches = []

for item in sorted(loops, key=lambda r: json.dumps(r, sort_keys=True)):
    if not _truthy(item.get('active', True)):
        continue
    if _num(item.get('breach_count', 0)) > a.max_loop_breaches:
        breaches.append(f"loop:{_loop_id(item)}")
    if _num(item.get('budget_ms', item.get('loop_budget_ms', 0.0))) > a.max_loop_budget_ms:
        breaches.append(f"budget:{_loop_id(item)}")

seen = set()
for row in rows:
    if _loop_id(row) in seen:
        breaches.append(f"duplicate:{_loop_id(row)}")
    seen.add(_loop_id(row))
    if _truthy(row.get('breach')) or _num(row.get('budget_ms', 0.0)) > a.max_loop_budget_ms:
        breaches.append(f"row:{_loop_id(row)}")
    if _num(row.get('loop_ms', row.get('duration_ms', 0.0))) > a.max_loop_budget_ms:
        breaches.append(f"duration:{_loop_id(row)}")

if breaches:
    print(
        'C73 replay loop budget breach: '
        + ','.join(sorted(set(breaches))),
        file=sys.stderr,
    )
    raise SystemExit(2)
