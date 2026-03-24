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
require_cmd git
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

ALLOW_REPO="${TMP_DIR}/allow-repo"
BLOCKED_REPO="${TMP_DIR}/blocked-repo"
mkdir -p "${ALLOW_REPO}" "${BLOCKED_REPO}"
git -C "${ALLOW_REPO}" init -q
git -C "${BLOCKED_REPO}" init -q
touch "${BLOCKED_REPO}/dirty.txt"

cat > "${TMP_DIR}/host/policy-wrapper-rules.json" <<'JSON'
{
  "schema_version": 1,
  "required_conditions": ["git_clean_worktree"],
  "commands": [
    {
      "id": "smoke-allow",
      "source": "smoke",
      "action": "allow",
      "matcher": "exact",
      "pattern": "git smoke-allow",
      "normalized_pattern": "git smoke-allow",
      "conditions": {
        "mode": "all",
        "conditions": ["git_clean_worktree"]
      },
      "platform_action": "allow",
      "shell_entry": "Shell(git smoke-allow)",
      "bash_entry": "Bash(git smoke-allow)"
    },
    {
      "id": "smoke-block",
      "source": "smoke",
      "action": "allow",
      "on_mismatch": "deny",
      "matcher": "exact",
      "pattern": "git smoke-block",
      "normalized_pattern": "git smoke-block",
      "conditions": {
        "mode": "all",
        "conditions": ["git_clean_worktree"]
      },
      "platform_action": "allow",
      "shell_entry": "Shell(git smoke-block)",
      "bash_entry": "Bash(git smoke-block)"
    }
  ]
}
JSON

echo "[smoke] running allow dispatch check"
set +e
allow_output="$("${DISPATCH_SCRIPT}" \
  --json \
  --bundle "${TMP_DIR}/host/policy-wrapper-rules.json" \
  --command "git smoke-allow" \
  --cwd "${ALLOW_REPO}")"
allow_rc=$?
set -e
if [ "$allow_rc" -ne 0 ]; then
  echo "[smoke] ERROR: allow-path dispatch command returned ${allow_rc}: ${allow_output}" >&2
  exit 1
fi

set +e
allow_info="$(ALLOW_OUTPUT="$allow_output" python - <<'PY'
import json
import os

raw = os.environ["ALLOW_OUTPUT"]
try:
  payload = json.loads(raw)
except json.JSONDecodeError as exc:
  raise SystemExit(f"invalid json for allow output: {exc}")
print(payload["decision"])
print(payload["condition_passed"])
print(payload["matched"])
PY
)"
allow_parse_rc=$?
set -e
if [ "$allow_parse_rc" -ne 0 ]; then
  echo "[smoke] ERROR: allow-path output was not valid JSON: ${allow_output}" >&2
  exit 1
fi
allow_decision="$(printf '%s\n' "$allow_info" | sed -n '1p')"
allow_condition_passed="$(printf '%s\n' "$allow_info" | sed -n '2p')"
allow_matched="$(printf '%s\n' "$allow_info" | sed -n '3p')"
if [ "$allow_decision" != "allow" ] || [ "${allow_condition_passed}" != "True" ] || [ "${allow_matched}" != "True" ]; then
  echo "[smoke] ERROR: allow-path dispatch decision was not allow: ${allow_decision}" >&2
  exit 1
fi
echo "[smoke] allow dispatch decision: ${allow_decision} (rc=${allow_rc})"
echo "[smoke] allow dispatch condition_passed=${allow_condition_passed} matched=${allow_matched}"

echo "[smoke] running blocked dispatch check"
set +e
blocked_output="$("${DISPATCH_SCRIPT}" \
  --json \
  --bundle "${TMP_DIR}/host/policy-wrapper-rules.json" \
  --command "git smoke-block" \
  --cwd "${BLOCKED_REPO}")"
blocked_rc=$?
set -e
if [ "$blocked_rc" -eq 0 ]; then
  echo "[smoke] ERROR: blocked-path dispatch command unexpectedly allowed: ${blocked_output}" >&2
  exit 1
fi

set +e
blocked_info="$(BLOCKED_OUTPUT="$blocked_output" python - <<'PY'
import json
import os

raw = os.environ["BLOCKED_OUTPUT"]
try:
  payload = json.loads(raw)
except json.JSONDecodeError as exc:
  raise SystemExit(f"invalid json for blocked output: {exc}")
print(payload["decision"])
print(payload["condition_passed"])
print(payload["matched"])
PY
)"
blocked_parse_rc=$?
set -e
if [ "$blocked_parse_rc" -ne 0 ]; then
  echo "[smoke] ERROR: blocked-path output was not valid JSON: ${blocked_output}" >&2
  exit 1
fi
blocked_decision="$(printf '%s\n' "$blocked_info" | sed -n '1p')"
blocked_condition_passed="$(printf '%s\n' "$blocked_info" | sed -n '2p')"
blocked_matched="$(printf '%s\n' "$blocked_info" | sed -n '3p')"
if [ "${blocked_decision}" != "deny" ]; then
  echo "[smoke] ERROR: blocked-path decision was not deny: ${blocked_decision}" >&2
  exit 1
fi
if [ "${blocked_condition_passed}" != "False" ]; then
  echo "[smoke] ERROR: blocked-path condition should be false: ${blocked_condition_passed}" >&2
  exit 1
fi
if [ "${blocked_matched}" != "True" ]; then
  echo "[smoke] ERROR: blocked-path rule was not matched: ${blocked_matched}" >&2
  exit 1
fi
echo "[smoke] blocked dispatch decision: ${blocked_decision} (rc=${blocked_rc})"
echo "[smoke] blocked dispatch condition_passed=${blocked_condition_passed} matched=${blocked_matched}"

echo "[smoke] host-hook dispatch smoke passed"
SMOKE_STATUS="PASS"
