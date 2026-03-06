#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
SMOKE_STATUS="FAIL"

cleanup() {
  if [[ -d "${TMP_DIR}" ]]; then
    rm -rf "${TMP_DIR}"
  fi
  if [[ "${SMOKE_STATUS}" == "PASS" ]]; then
    echo "[smoke] ===== RESULT: PASS ====="
  else
    echo "[smoke] ===== RESULT: FAIL ====="
  fi
}

trap cleanup EXIT

fail() {
  echo "[smoke] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || fail "missing prerequisite command: ${cmd}"
}

require_file() {
  local path="$1"
  [[ -f "${path}" ]] || fail "missing prerequisite file: ${path}"
}

require_cmd uv
require_cmd python
require_file "${ROOT_DIR}/scripts/generate_policy_snapshot.py"
require_file "${ROOT_DIR}/resolve.py"

echo "[smoke] checking canonical snapshot drift pairs"
for pair in "codex:deployment" "codex:query"; do
  harness="${pair%%:*}"
  task_domain="${pair##*:}"
  uv run --with pyyaml python "${ROOT_DIR}/scripts/generate_policy_snapshot.py" \
    --root "${ROOT_DIR}" \
    --harness "${harness}" \
    --task-domain "${task_domain}" \
    --output "${ROOT_DIR}/policy-config/snapshots/policy_snapshot_${harness}_${task_domain}.json" \
    --check-existing
done

echo "[smoke] emitting policy wrapper bundle for host dispatch"
uv run --with pyyaml python "${ROOT_DIR}/resolve.py" \
  --root "${ROOT_DIR}" \
  --harness codex \
  --task-domain deployment \
  --emit "${TMP_DIR}/effective-policy.json" \
  --emit-host-rules \
  --host-out-dir "${TMP_DIR}/host" \
  --include-conditional

DISPATCH_SCRIPT="${ROOT_DIR}/wrappers/policy-wrapper-dispatch.sh"
if [[ ! -x "${DISPATCH_SCRIPT}" ]]; then
  fail "dispatch script is missing or not executable: ${DISPATCH_SCRIPT}"
fi

require_file "${TMP_DIR}/host/policy-wrapper-rules.json"

echo "[smoke] running wrapper dispatch check"
"${DISPATCH_SCRIPT}" \
  --json \
  --bundle "${TMP_DIR}/host/policy-wrapper-rules.json" \
  --command "git status" \
  --cwd "${ROOT_DIR}" >/dev/null

echo "[smoke] host-hook dispatch smoke passed"
SMOKE_STATUS="PASS"
