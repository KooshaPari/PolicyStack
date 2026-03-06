#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  policy-wrapper-dispatch.sh --bundle <path> --command <text> [--cwd <path>] [--json] [--binary <path>] [--binary-health-check] [--missing-policy-default <allow|request|deny>] [--malformed-bundle-default <allow|request|deny>] [--condition-eval-error-default <allow|request|deny>] [--require-binary]

Decision output:
  allow   : shell/host can continue
  request : shell/host should prompt for manual confirmation
  deny    : shell/host must block

Environment:
  POLICY_WRAPPER_BINARY               Optional explicit wrapper binary path
  POLICY_WRAPPER_CWD                  Default cwd when evaluating git conditions (defaults to pwd)
  POLICY_WRAPPER_MISSING_POLICY_DEFAULT
                                     Fallback decision if wrapper binary is missing/unusable
                                     One of: allow, request, deny (default allow)
  POLICY_WRAPPER_MALFORMED_BUNDLE_DEFAULT
                                     Fallback decision if wrapper/bundle output is malformed
                                     One of: allow, request, deny (default same as missing default)
  POLICY_WRAPPER_CONDITION_EVAL_ERROR_DEFAULT
                                     Fallback decision if wrapper reports condition eval error
                                     One of: allow, request, deny (default request)
  POLICY_WRAPPER_BINARY_CHECK         Set to 1 to validate selected binary via --help before execute
USAGE
}

bundle=""
command_str=""
cwd="${POLICY_WRAPPER_CWD:-$(pwd)}"
json_output=0
binary="${POLICY_WRAPPER_BINARY:-}"
missing_default="${POLICY_WRAPPER_MISSING_POLICY_DEFAULT:-allow}"
malformed_default="${POLICY_WRAPPER_MALFORMED_BUNDLE_DEFAULT:-$missing_default}"
condition_eval_default="${POLICY_WRAPPER_CONDITION_EVAL_ERROR_DEFAULT:-request}"
require_binary=0
binary_health_check="${POLICY_WRAPPER_BINARY_CHECK:-0}"

health_check_binary() {
  local path="$1"
  if [[ ! -x "$path" ]]; then
    echo "binary-not-executable"
    return 1
  fi
  "$path" --help >/dev/null 2>&1
  if [[ $? -ne 0 ]]; then
    echo "binary-health-failed"
    return 1
  fi
  return 0
}

validate_decision() {
  case "$1" in
    allow|request|deny) return 0 ;;
    *) return 1 ;;
  esac
}

trim_output() {
  printf '%s' "$1" | tr -d '\r' | xargs
}

normalize_exit() {
  case "$1" in
    allow) echo 0 ;;
    request) echo 1 ;;
    deny) echo 2 ;;
    *) echo 3 ;;
  esac
}

emit_fallback() {
  local reason="$1"
  local fallback="${2:-$missing_default}"
  if ! validate_decision "$fallback"; then
    fallback="$missing_default"
  fi
  if [[ "$json_output" -eq 1 ]]; then
    python - "$command_str" "$fallback" "$reason" <<'PY'
import json
import sys

print(
    json.dumps(
        {
            "command": sys.argv[1],
            "decision": sys.argv[2],
            "matched": False,
            "fallback": sys.argv[3],
            "fallback_reason": sys.argv[3],
            "condition_passed": False,
            "error": sys.argv[3],
        }
    )
)
PY
  else
    echo "$fallback"
  fi
  exit_code="$(normalize_exit "$fallback")"
  exit "$exit_code"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle)
      bundle="$2"
      shift 2
      ;;
    --command)
      command_str="$2"
      shift 2
      ;;
    --cwd)
      cwd="$2"
      shift 2
      ;;
    --binary)
      binary="$2"
      shift 2
      ;;
    --json)
      json_output=1
      shift
      ;;
    --binary-health-check)
      binary_health_check=1
      shift
      ;;
    --missing-policy-default)
      missing_default="$2"
      if ! validate_decision "$missing_default"; then
        echo "invalid --missing-policy-default '$2': must be allow|request|deny" >&2
        exit 3
      fi
      shift 2
      ;;
    --malformed-bundle-default)
      malformed_default="$2"
      if ! validate_decision "$malformed_default"; then
        echo "invalid --malformed-bundle-default '$2': must be allow|request|deny" >&2
        exit 3
      fi
      shift 2
      ;;
    --condition-eval-error-default)
      condition_eval_default="$2"
      if ! validate_decision "$condition_eval_default"; then
        echo "invalid --condition-eval-error-default '$2': must be allow|request|deny" >&2
        exit 3
      fi
      shift 2
      ;;
    --require-binary)
      require_binary=1
      shift
      ;;
    *)
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$bundle" || -z "$command_str" ]]; then
  usage
  exit 1
fi
if ! validate_decision "$missing_default"; then
  echo "invalid missing default '$missing_default': must be allow|request|deny" >&2
  exit 3
fi
if ! validate_decision "$malformed_default"; then
  echo "invalid malformed default '$malformed_default': must be allow|request|deny" >&2
  exit 3
fi
if ! validate_decision "$condition_eval_default"; then
  echo "invalid condition-eval error default '$condition_eval_default': must be allow|request|deny" >&2
  exit 3
fi

if [[ -z "$binary" ]]; then
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  for candidate in \
    "${script_dir}/go/policy-wrapper" \
    "${script_dir}/rust/target/release/policy-wrapper" \
    "${script_dir}/rust/target/debug/policy-wrapper" \
    "${script_dir}/zig/zig-out/bin/policy-wrapper"
  do
    if [[ -x "$candidate" ]]; then
      if [[ "$binary_health_check" -eq 1 ]]; then
        if ! health_check_binary "$candidate" >/dev/null 2>&1; then
          continue
        fi
      fi
      binary="$candidate"
      break
    fi
  done
fi

if [[ "$binary_health_check" -eq 1 ]] && [[ -n "$binary" ]] && [[ ! -x "$binary" ]]; then
  echo "binary-health-check skipped: selected binary is not executable" >&2
  binary=""
fi
if [[ "$binary_health_check" -eq 1 ]] && [[ -n "$binary" ]] && ! health_check_binary "$binary" >/dev/null 2>&1; then
  echo "binary-health-check failed for $binary" >&2
  if [[ "$require_binary" -eq 1 ]]; then
    echo "required wrapper binary rejected by health check" >&2
    exit 3
  fi
  binary=""
fi

if [[ ! -x "$binary" ]]; then
  if [[ "$require_binary" -eq 1 ]]; then
    echo "required policy wrapper binary not found or unusable" >&2
    echo "binary-health-check: ${binary_health_check}" >&2
    echo "attempted binary: ${binary:-<none>}" >&2
    exit 3
  fi
  emit_fallback "missing-binary" "$missing_default"
fi

if ! [[ -x "$binary" ]]; then
  emit_fallback "binary-not-executable" "$missing_default"
fi

args=(
  --bundle "$bundle"
  --command "$command_str"
  --cwd "$cwd"
)
if [[ "$json_output" -eq 1 ]]; then
  args+=(--json)
fi

stdout_file="$(mktemp)"
stderr_file="$(mktemp)"
cleanup_tmp_files() {
  rm -f "$stdout_file" "$stderr_file"
}
trap cleanup_tmp_files EXIT

set +e
"$binary" "${args[@]}" >"$stdout_file" 2>"$stderr_file"
status=$?
set -e

if [[ -s "$stderr_file" ]]; then
  cat "$stderr_file" >&2
fi
output="$(cat "$stdout_file")"

if [[ "$json_output" -eq 1 ]]; then
  if [[ -n "$output" ]]; then
    parsed=""
    parse_status=0
    parsed=$(python - "$output" "$condition_eval_default" <<'PY'
import json
import sys

raw = sys.argv[1]
condition_eval_default = sys.argv[2]
try:
    data = json.loads(raw)
except Exception as exc:
    raise SystemExit(f"invalid-json:{exc}")
if not isinstance(data, dict) or "decision" not in data:
    raise SystemExit("missing-decision")

decision = str(data["decision"]).strip()
if decision not in {"allow", "request", "deny"}:
    raise SystemExit(f"invalid-decision:{decision}")

condition_passed = bool(data.get("condition_passed", True))
error = str(data.get("error", "")).strip()
if (not condition_passed) and error:
    data["decision"] = condition_eval_default
    data["fallback"] = condition_eval_default
    data["fallback_reason"] = f"wrapper-condition-eval-error:{error}"
    data["matched"] = False
    data["condition_passed"] = False
    decision = str(data["decision"]).strip()

print(f"{decision}\0{json.dumps(data)}")
PY
    ) || parse_status=$?
    if [[ $parse_status -eq 0 ]]; then
      IFS=$'\0' read -r decision parsed_output <<< "$parsed"
      echo "$parsed_output"
      exit_code="$(normalize_exit "$decision")"
      exit "$exit_code"
    fi
    emit_fallback "wrapper-json-parse-failed" "$malformed_default"
  fi
  emit_fallback "wrapper-empty-json-output" "$malformed_default"
fi

output="$(trim_output "$output")"
if [[ "$output" != "allow" && "$output" != "request" && "$output" != "deny" ]]; then
  emit_fallback "wrapper-decision-invalid:$output" "$malformed_default"
fi
if [[ $status -ne 0 ]]; then
  emit_fallback "wrapper-exec-failed:$status" "$malformed_default"
fi

echo "$output"
exit_code="$(normalize_exit "$output")"
exit "$exit_code"
