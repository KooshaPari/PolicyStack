#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _num(v, default=0.0):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return float(default)


def _truthy(v):
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}


def _rid(r):
    return str(
        r.get("run_id") or r.get("replay_id") or r.get("playbook_id") or r.get("id") or "?"
    ).strip()


def _read_json(path, label):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        print(f"C97 {label} invalid JSON", file=sys.stderr)
        raise SystemExit(2)


def _read_csv(path):
    try:
        rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    except Exception:
        print("C97 replay resilience CSV invalid", file=sys.stderr)
        raise SystemExit(2)
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


def _fail(message):
    print(f"C97 replay resilience quantile breach: {message}", file=sys.stderr)
    raise SystemExit(2)


p = argparse.ArgumentParser()
p.add_argument("--resilience-metrics", required=True)
p.add_argument("--replay-csv", required=True)
p.add_argument("--max-p95", type=float, default=0.85)
p.add_argument("--max-p99", type=float, default=0.92)
p.add_argument("--max-resilient-failures", type=int, default=0)
p.add_argument("--max-quantile-breaches", type=int, default=0)
a = p.parse_args()

metrics = _read_json(a.resilience_metrics, "resilience metrics")
if not isinstance(metrics, dict):
    _fail("resilience metrics JSON must be an object")

rows = _read_csv(a.replay_csv)

breaches = []
baseline_p95 = _num(metrics.get("replay_resilience_p95", metrics.get("p95", 0.0)))
baseline_p99 = _num(metrics.get("replay_resilience_p99", metrics.get("p99", 0.0)))
baseline_breaches = int(
    _num(metrics.get("resilience_quantile_breaches", metrics.get("quantile_breaches", 0.0)))
)

if baseline_p95 > a.max_p95:
    breaches.append("summary:p95")
if baseline_p99 > a.max_p99:
    breaches.append("summary:p99")
if baseline_breaches > a.max_quantile_breaches:
    breaches.append("summary:quantile_breaches")

failed = 0
for row in rows:
    rid = _rid(row)
    status = str(row.get("status", "")).strip().lower()
    p95 = _num(row.get("resilience_p95", row.get("p95", 0.0)))
    p99 = _num(row.get("resilience_p99", row.get("p99", 0.0)))
    if p95 > a.max_p95:
        breaches.append(f"run:p95:{rid}")
    if p99 > a.max_p99:
        breaches.append(f"run:p99:{rid}")
    if _truthy(row.get("resilience_breach", row.get("breach", False))) or status in {"failed", "breach", "error", "timeout"}:
        failed += 1
        breaches.append(f"run:failed:{rid}")

if failed > a.max_resilient_failures:
    breaches.append(f"failed_count={failed}")

if breaches:
    _fail(",".join(sorted(set(breaches))))
