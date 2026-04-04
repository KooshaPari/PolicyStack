#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


p = argparse.ArgumentParser()
p.add_argument("--stats", required=True)
p.add_argument("--drift-col", default="capa_drift_count")
p.add_argument("--recovery-col", default="capa_recovery_count")
p.add_argument("--min-recovery-ratio", type=float, default=1.0)
a = p.parse_args()

stats = json.loads(pathlib.Path(a.stats).read_text())
drift = float(stats.get(a.drift_col, 0.0) or 0.0)
recovered = float(stats.get(a.recovery_col, 0.0) or 0.0)
recovery_ratio = (recovered / drift) if drift > 0 else 1.0

if recovery_ratio < a.min_recovery_ratio:
    print("B88 capa drift recovery gate failed", file=sys.stderr)
    raise SystemExit(2)
