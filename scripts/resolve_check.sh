#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = root / 'cli' / 'src'
sys.path.insert(0, str(src))

from policy_federation.validate import validate_policy_file

seen = set()
for policy_file in sorted(root.glob('policies/**/*.yaml')):
    if policy_file in seen:
        continue
    seen.add(policy_file)
    validate_policy_file(policy_file)
print('policy-check: ok')
PY
