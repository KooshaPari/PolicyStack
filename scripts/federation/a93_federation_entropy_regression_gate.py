#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _load(path: pathlib.Path):
    raw = path.read_text()
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(raw.splitlines()))
    return json.loads(raw)


def _to_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A93 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def _to_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A93 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument("--evidence", required=True)
parser.add_argument("--max-entropy-spikes", type=int, default=0)
parser.add_argument("--max-state-regressions", type=int, default=0)
parser.add_argument("--min-entropy-score", type=float, default=0.0)
args = parser.parse_args()

data = _load(pathlib.Path(args.evidence))

if isinstance(data, dict):
    spike_count = _to_int(data.get("entropy_spikes", data.get("spike_count", 0)), "entropy_spikes")
    regressions = _to_int(data.get("state_regressions", data.get("regressions", 0)), "state_regressions")
    entropy_score = _to_float(
        data.get("entropy_score", data.get("avg_entropy_score", data.get("entropy_mean", 0.0))),
        "entropy_score",
    )
elif isinstance(data, list):
    spike_count = 0
    regressions = 0
    entropy_scores = []
    for row in data:
        if not isinstance(row, dict):
            continue
        spike_count += int(_to_int(row.get("entropy_spike", row.get("spike", 0)), "entropy_spike"))
        if _to_int(row.get("state_regression", row.get("regression", 0)), "state_regression") > 0:
            regressions += 1
        score = row.get("entropy_score")
        if score is not None:
            entropy_scores.append(_to_float(score, "entropy_score"))
    entropy_score = sum(entropy_scores) / len(entropy_scores) if entropy_scores else 1.0
else:
    print("A93 invalid evidence payload", file=sys.stderr)
    raise SystemExit(2)

if (
    spike_count > args.max_entropy_spikes
    or regressions > args.max_state_regressions
    or entropy_score < args.min_entropy_score
):
    print(
        "A93 federation entropy regression gate failed",
        file=sys.stderr,
    )
    raise SystemExit(2)
