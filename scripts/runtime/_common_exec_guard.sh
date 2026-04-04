#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: _common_exec_guard.sh <harness> <command> [args...]" >&2
  exit 64
fi

HARNESS="$1"
shift

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CLI_SRC="${REPO_ROOT}/cli/src"

# Validate POLICY_REPO and POLICY_TASK_DOMAIN against path traversal
_validate_policy_var() {
  local name="$1" value="$2"
  if [[ "$value" == *".."* || "$value" == *"/"* || "$value" == *$'\n'* || "$value" == *$'\0'* ]]; then
    echo "ERROR: ${name} contains disallowed characters (path traversal): ${value}" >&2
    exit 78
  fi
}

DOMAIN="${POLICY_TASK_DOMAIN:-devops}"
REPO_NAME="${POLICY_REPO:-$(basename "$PWD")}"
ASK_MODE="${POLICY_ASK_MODE:-review}"
ACTOR="${POLICY_ACTOR:-}"
SIDECAR_PATH="${POLICY_SIDECAR_PATH:-}"
AUDIT_LOG_PATH="${POLICY_AUDIT_LOG_PATH:-$HOME/.policy-federation/audit.jsonl}"

export PYTHONPATH="${CLI_SRC}${PYTHONPATH:+:${PYTHONPATH}}"

ARGS=(
  -m policy_federation.cli exec
  --harness "${HARNESS}"
  --domain "${DOMAIN}"
  --repo "${REPO_NAME}"
  --cwd "$PWD"
  --ask-mode "${ASK_MODE}"
)

if [ -n "${ACTOR}" ]; then
  ARGS+=(--actor "${ACTOR}")
fi

if [ -n "${SIDECAR_PATH}" ]; then
  ARGS+=(--sidecar-path "${SIDECAR_PATH}")
fi

if [ -n "${AUDIT_LOG_PATH}" ]; then
  ARGS+=(--audit-log-path "${AUDIT_LOG_PATH}")
fi

exec python "${ARGS[@]}" -- "$@"
