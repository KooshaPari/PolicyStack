#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: _common_network_guard.sh <harness> <command> [args...]" >&2
  exit 64
fi

HARNESS="$1"
shift

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CLI_SRC="${REPO_ROOT}/cli/src"

DOMAIN="${POLICY_TASK_DOMAIN:-devops}"
REPO_NAME="${POLICY_REPO:-$(basename "$PWD")}"
ASK_MODE="${POLICY_ASK_MODE:-review}"
ACTOR="${POLICY_ACTOR:-}"
AUDIT_LOG_PATH="${POLICY_AUDIT_LOG_PATH:-$HOME/.policy-federation/audit.jsonl}"

export PYTHONPATH="${CLI_SRC}${PYTHONPATH:+:${PYTHONPATH}}"

ARGS=(
  -m policy_federation.cli network-check
  --harness "${HARNESS}"
  --domain "${DOMAIN}"
  --repo "${REPO_NAME}"
  --cwd "$PWD"
  --ask-mode "${ASK_MODE}"
  --command "$*"
)

if [ -n "${ACTOR}" ]; then
  ARGS+=(--actor "${ACTOR}")
fi

if [ -n "${AUDIT_LOG_PATH}" ]; then
  ARGS+=(--audit-log-path "${AUDIT_LOG_PATH}")
fi

exec python "${ARGS[@]}"
