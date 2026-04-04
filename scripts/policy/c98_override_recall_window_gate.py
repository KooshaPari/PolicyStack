#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
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


def _oid(r):
    return str(r.get("override_id") or r.get("id") or r.get("name") or "?").strip()


def _ts(v):
    s = str(v or "").strip().replace("Z", "+00:00")
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def _days(a, b):
    if a is None or b is None:
        return None
    return (b - a).total_seconds() / 86400.0


def _read_json(path, label):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        print(f"C98 {label} invalid JSON", file=sys.stderr)
        raise SystemExit(2)


def _read_csv(path):
    try:
        rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    except Exception:
        print("C98 override recall window CSV invalid", file=sys.stderr)
        raise SystemExit(2)
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


def _fail(message):
    print(f"C98 override recall window breach: {message}", file=sys.stderr)
    raise SystemExit(2)


p = argparse.ArgumentParser()
p.add_argument("--overrides", required=True)
p.add_argument("--override-csv", required=True)
p.add_argument("--as-of", required=True)
p.add_argument("--max-recall-days", type=float, default=7.0)
p.add_argument("--max-open-recall-windows", type=int, default=0)
p.add_argument("--max-risky-recall-overrides", type=int, default=0)
p.add_argument("--min-recall-confidence", type=float, default=0.6)
a = p.parse_args()

as_of = _ts(a.as_of)
if not as_of:
    _fail("invalid --as-of timestamp")

overrides = _read_json(a.overrides, "overrides")
if isinstance(overrides, dict):
    overrides = overrides.get("overrides", overrides.get("items", []))
if not isinstance(overrides, list):
    _fail("overrides JSON must be a list")

rows = _read_csv(a.override_csv)

def _window_days(item):
    start = _ts(item.get("recall_started_at", item.get("start", item.get("from"))))
    end = _ts(item.get("recall_ended_at", item.get("end", item.get("to"))))
    if not start and not end:
        configured = item.get("recall_window_days")
        if str(configured).strip():
            return _num(configured)
        return None
    if not start or not end:
        return None
    return _days(start, end)


open_windows = 0
risky = 0
missing = []

for item in overrides:
    if not isinstance(item, dict):
        continue
    if not _truthy(item.get("active", True)):
        continue
    oid = _oid(item)
    start = _ts(item.get("recall_started_at", item.get("start", item.get("from"))))
    end = _ts(item.get("recall_ended_at", item.get("end", item.get("to"))))
    confidence = _num(item.get("recall_confidence", item.get("confidence", 0.0)))
    window = _window_days(item)
    if confidence >= a.min_recall_confidence and _truthy(item.get("active", True)):
        if window is None and (not start or not end):
            missing.append(oid)
        if window is not None and window > a.max_recall_days:
            risky += 1
        if start and end and start <= as_of <= end and window and window > a.max_recall_days:
            open_windows += 1

for row in rows:
    if not _truthy(row.get("active", True)):
        continue
    oid = _oid(row)
    start = _ts(row.get("recall_started_at", row.get("start", row.get("from"))))
    end = _ts(row.get("recall_ended_at", row.get("end", row.get("to"))))
    confidence = _num(row.get("recall_confidence", row.get("confidence", 0.0)))
    window = _window_days(row)
    if confidence >= a.min_recall_confidence:
        if window is None and (not start or not end):
            missing.append(oid)
        if window is not None and window > a.max_recall_days:
            risky += 1
        status = str(row.get("status", "")).strip().lower()
        if start and end and start <= as_of <= end and status in {"open", "active", "pending", "running"}:
            open_windows += 1

issues = []
if missing:
    issues.append("missing_recall_windows=" + ",".join(sorted(set(missing))))
if risky > a.max_risky_recall_overrides:
    issues.append(f"risky_recall_overrides={risky}")
if open_windows > a.max_open_recall_windows:
    issues.append(f"open_recall_windows={open_windows}")

if issues:
    _fail("; ".join(issues))
