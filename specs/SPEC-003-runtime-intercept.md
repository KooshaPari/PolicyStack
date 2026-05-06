# SPEC-003: Runtime Intercept and Guarded Execution

**Version**: 1.0
**Status**: Active
**Created**: 2026-05-06
**Author**: PolicyStack Agent

## Overview

The runtime intercept layer wraps command execution, enforcing policy decisions before, during, and after a subprocess runs. It supports three ask modes: `fail` (block on ask), `allow` (proceed on ask), and `prompt` (interactive prompt on ask).

## Intercept Modes

| Mode | On Ask Decision | On Deny | On Allow |
|------|----------------|---------|----------|
| `fail` | Exit code 1 | Exit code 1 | Execute |
| `allow` | Execute anyway | Exit code 1 | Execute |
| `prompt` | Interactive prompt | Exit code 1 | Execute |

## CLI Commands

- `intercept`: Evaluate a single action with policy and exit
- `exec`: Execute a command through the guard and return subprocess exit code
- `write-check`: Intercept write actions with `ask-mode` enforcement
- `network-check`: Intercept network actions with `ask-mode` enforcement

## Sidecar and Audit Trail

Each intercept/exec records:

```json
{
  "run_id": "<uuid>",
  "policy_hash": "<sha256>",
  "scope_chain": ["global", "harness", ...],
  "decision": "allow|deny|ask",
  "exit_code": 0,
  "command": "<string>",
  "actor": "<string>",
  "cwd": "<path>",
  "timestamp": "<iso8601>"
}
```

## Implementation

- **CLI commands**: `intercept`, `exec`, `write-check`, `network-check`, `review`
- **Module**: `cli/src/policy_federation/interceptor.py`
- **Sidecar builder**: `runtime_artifacts.py` `build_run_sidecar()`
- **Audit recorder**: `runtime_artifacts.py` `append_audit_event()`, `record_audit_event()`

## Acceptance Criteria

- [ ] `intercept` exits with the decision's exit code
- [ ] `exec` runs the subprocess and returns its exit code
- [ ] Sidecar file written at `--sidecar-path` when provided
- [ ] Audit event appended when `--audit-log-path` provided
- [ ] `ask-mode prompt` reads from stdin and respects user answer
- [ ] `--review` mode sets `ask_mode=review` (no blocking, audit only)

## Traceability

- FR-HOST-001, FR-HOST-002, FR-HOST-003, FR-HOST-004
