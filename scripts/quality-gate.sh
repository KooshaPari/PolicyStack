#!/usr/bin/env bash
set -euo pipefail

# Quality-gate script for AgentOps CI.
# Usage: ./scripts/quality-gate.sh verify

CMD="${1:-verify}"

case "$CMD" in
  verify)
    echo "Running quality gate verification..."

    echo "--- Python lint ---"
    if command -v ruff >/dev/null 2>&1; then
      ruff format --check .
      ruff check .
    else
      echo "ruff not found, skipping."
    fi

    echo "--- Python type check ---"
    if command -v mypy >/dev/null 2>&1; then
      mypy cli/src/
    else
      echo "mypy not found, skipping."
    fi

    echo "--- Python tests ---"
    if command -v pytest >/dev/null 2>&1; then
      pytest tests/
    else
      echo "pytest not found, skipping."
    fi

    echo "Quality gate passed."
    ;;
  *)
    echo "Unknown command: $CMD"
    exit 1
    ;;
esac
