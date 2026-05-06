# SPEC-002: Authorization Evaluation

**Version**: 1.0
**Status**: Active
**Created**: 2026-05-06
**Author**: PolicyStack Agent

## Overview

The authorization evaluator checks a resolved policy against a specific action request (exec, write, network) and returns a decision: `allow`, `deny`, or `ask`.

## Evaluation Inputs

| Field | Source | Description |
|-------|--------|-------------|
| `action` | CLI arg | One of `exec`, `write`, `network` |
| `command` | CLI arg | Raw command string |
| `cwd` | CLI arg / env | Working directory |
| `actor` | CLI arg | Actor identifier |
| `target_paths` | CLI arg | List of file paths targeted |
| `policy` | Resolver output | Merged policy document |

## Rule Matching

Each rule has a `match` block with optional patterns:

- `command_patterns`: Glob/regex against the command string
- `target_path_patterns`: Glob/regex against each target path
- `cwd_patterns`: Glob/regex against the working directory

Rule evaluation:
1. Filter rules by matching `actions` array
2. Check each `match` condition; all conditions must pass for a rule to match
3. Select highest-priority matching rule (lowest integer = highest priority)
4. Return rule's `effect` as the policy decision

## Decision Logic

- `allow` → permit the action without prompting
- `deny` → block the action with an error
- `ask` → prompt the user (handled by intercept layer)

## Implementation

- **CLI command**: `policyctl evaluate --harness <h> --domain <d> --action <a> [--command <c>] [--cwd <dir>] [--actor <id>] [--target-path <path>]`
- **Module**: `cli/src/policy_federation/authorization.py`
- **CLI entrypoint**: `cli.py` `evaluate_command`

## Acceptance Criteria

- [ ] Matching rule with `effect: allow` returns `final_decision: allow`
- [ ] Matching rule with `effect: deny` returns `final_decision: deny`
- [ ] No matching rule defaults to `final_decision: ask`
- [ ] Higher priority rules override lower priority
- [ ] Missing `match` block matches all inputs
- [ ] `policy_hash` and `scope_chain` included in response

## Traceability

- FR-COND-001, FR-COND-002, FR-COND-003, FR-COND-004
