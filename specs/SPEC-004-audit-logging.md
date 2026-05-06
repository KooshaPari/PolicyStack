# SPEC-004: Audit Logging and Chain Integrity

**Version**: 1.0
**Status**: Active
**Created**: 2026-05-06
**Author**: PolicyStack Agent

## Overview

All policy decisions and executions are recorded as JSONL events in an append-only audit log. The system supports filtering, chain verification, and compliance reporting.

## Event Schema

Each audit event is a JSON object written as one line:

```jsonl
{"timestamp": "2026-05-06T10:00:00Z", "run_id": "...", "action": "exec", "final_decision": "allow", ...}
```

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | string | Unique run identifier |
| `action` | string | `exec`, `write`, or `network` |
| `final_decision` | string | `allow`, `deny`, or `ask` |
| `timestamp` | string | ISO 8601 datetime |
| `policy_hash` | string | SHA of resolved policy |
| `scope_chain` | array | List of scope tags |

## Optional Fields

- `command`: Raw command string
- `actor`: Actor identifier
- `cwd`: Working directory
- `target_paths`: List of targeted file paths
- `exit_code`: Subprocess exit code (for exec)
- `event_type`: `permission_decision` (default) or custom

## Chain Integrity

`verify_audit_chain(events)` checks:
1. All events have required fields (`run_id`, `action`, `final_decision`)
2. Events are in chronological order (optional)
3. No gaps in `run_id` sequence (optional)

## CLI Commands

- `audit --log-path <path> [--since <iso>] [--until <iso>] [--action <a>] [--decision <d>] [--actor <pattern>] [--summary] [--verify-chain]`

## Filter Criteria

- `since` / `until`: ISO 8601 datetime bounds
- `action`: exact match on `action` field
- `decision`: exact match on `final_decision` field
- `actor`: regex or substring match on `actor` field

## Implementation

- **CLI command**: `audit`
- **Module**: `cli/src/policy_federation/runtime_artifacts.py`
- **CLI entrypoint**: `cli.py` `audit_command`

## Acceptance Criteria

- [ ] `--summary` returns counts by decision and by action
- [ ] `--verify-chain` exits 1 if any event is missing required fields
- [ ] `--since` / `--until` correctly bound events by timestamp
- [ ] `--actor` supports both regex and substring modes
- [ ] Empty log file returns empty results, not an error

## Traceability

- FR-GOV-001, FR-GOV-002, FR-GOV-003, FR-GOV-004, FR-GOV-005
