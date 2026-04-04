#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v):
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}


def _pid(r):
    return str(r.get("playbook_id") or r.get("id") or r.get("name") or "?").strip()


def _sid(r):
    return str(r.get("step_id") or r.get("step") or r.get("id") or "?").strip()


def _read_json(path, label):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        print(f"C99 {label} invalid JSON", file=sys.stderr)
        raise SystemExit(2)


def _read_csv(path):
    try:
        rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    except Exception:
        print("C99 playbook consistency CSV invalid", file=sys.stderr)
        raise SystemExit(2)
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


def _fail(message):
    print(f"C99 playbook consistency breach: {message}", file=sys.stderr)
    raise SystemExit(2)


p = argparse.ArgumentParser()
p.add_argument("--playbooks", required=True)
p.add_argument("--consistency-csv", required=True)
p.add_argument("--max-missing-steps", type=int, default=0)
p.add_argument("--max-orphan-steps", type=int, default=0)
p.add_argument("--max-inconsistent-playbooks", type=int, default=0)
p.add_argument("--max-inconsistent-exits", type=int, default=0)
a = p.parse_args()

defs = _read_json(a.playbooks, "playbooks")
rows = _read_csv(a.consistency_csv)

playbooks = []
if isinstance(defs, dict):
    playbooks = defs.get("playbooks", defs.get("items", []))
elif isinstance(defs, list):
    playbooks = defs
else:
    _fail("playbooks JSON must be a list or object with playbooks/items")

expected_steps = set()
required_by_playbook = {}
required_exit = set()
for p in playbooks:
    if not isinstance(p, dict):
        continue
    pid = _pid(p)
    if not pid:
        continue
    steps = p.get("steps", [])
    if isinstance(steps, dict):
        step_ids = {str(k).strip() for k, v in steps.items() if str(k).strip()}
    elif isinstance(steps, list):
        step_ids = {str(s.get("id", s)).strip() for s in steps if str(s).strip()}
    else:
        step_ids = set()
    required_by_playbook[pid] = step_ids
    expected_steps.update({f"{pid}::{step}" for step in step_ids})
    for step in p.get("exits", []):
        if not isinstance(step, dict):
            continue
        if not _truthy(step.get("required", True)):
            continue
        source = str(step.get("from", "")).strip()
        target = str(step.get("to", "")).strip()
        if source and target:
            required_exit.add(f"{pid}::{source}->{target}")

seen_steps = set()
seen_exits = set()
orphans = set()
bad = set()
inconsistent = set()

for row in rows:
    pid = _pid(row)
    sid = _sid(row)
    if not pid or not sid:
        continue
    pair = f"{pid}::{sid}"
    if pair in seen_steps:
        orphans.add(pair)
    seen_steps.add(pair)
    status = str(row.get("status", "")).strip().lower()
    if status in {"failed", "error", "invalid", "inconsistent"}:
        bad.add(pair)
    source = str(row.get("from_step", row.get("source_step", "")).strip())
    target = str(row.get("to_step", row.get("target_step", "")).strip())
    if source and target:
        seen_exits.add(f"{pid}::{source}->{target}")

missing_steps = sorted(expected_steps - seen_steps)
missing_exits = sorted(required_exit - seen_exits)
if missing_exits:
    inconsistent.add("missing_exits=" + ",".join(missing_exits))

inconsistent_playbooks = 0
for pbid, expected in required_by_playbook.items():
    present = {_sid(r) for r in rows if _pid(r) == pbid}
    if expected and expected - present:
        inconsistent_playbooks += 1

issues = []
if missing_steps:
    issues.append("missing_steps=" + ",".join(missing_steps))
if orphans:
    issues.append("orphan_steps=" + ",".join(sorted(orphans)))
if inconsistent:
    issues.extend(sorted(inconsistent))
if len(bad) > a.max_inconsistent_exits:
    issues.append(f"inconsistent_steps={len(bad)}")
if len(missing_steps) > a.max_missing_steps:
    issues.append(f"missing_step_count={len(missing_steps)}")
if len(orphans) > a.max_orphan_steps:
    issues.append(f"orphan_step_count={len(orphans)}")
if inconsistent_playbooks > a.max_inconsistent_playbooks:
    issues.append(f"inconsistent_playbooks={inconsistent_playbooks}")

if issues:
    _fail("; ".join(sorted(set(issues))))
