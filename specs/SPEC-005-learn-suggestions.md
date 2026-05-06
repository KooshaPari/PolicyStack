# SPEC-005: Audit-Driven Policy Learning

**Version**: 1.0
**Status**: Active
**Created**: 2026-05-06
**Author**: PolicyStack Agent

## Overview

The learn system analyzes historical audit log events to automatically suggest new policy rules. It clusters repeated decisions, measures consistency, and emits draft rules with evidence.

## Learning Algorithm

1. **Read** all events (optionally filtered by `--since`)
2. **Filter** to `ask` and `allow` decisions only (deny is intentional)
3. **Cluster** by `(command_prefix, cwd_pattern)`:
   - `command_prefix`: `git <subcmd>`, `<tool> <subcmd>`, or first word
   - `cwd_pattern`: generalized path (worktree-aware)
4. **Score** each cluster:
   - `cluster_size` = number of events
   - `consistency` = dominant_decision_count / total_count
5. **Emit** a `RuleSuggestion` for each cluster where:
   - `cluster_size >= min_cluster_size` (default: 5)
   - `consistency >= min_confidence` (default: 0.8)
6. **Effect**: If dominant decision is `ask`, suggest `allow` (user wants to stop being asked). If dominant is `allow`, suggest `allow`.

## RuleSuggestion Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | `auto-<effect>-<prefix>-NNN` |
| `description` | string | Human-readable summary |
| `effect` | string | `allow` or `deny` |
| `actions` | list | Action types in cluster |
| `command_patterns` | list | Glob patterns for commands |
| `cwd_patterns` | list | Glob patterns for working dirs |
| `confidence` | float | Consistency ratio (0.0–1.0) |
| `evidence_count` | int | Cluster size |
| `sample_commands` | list | Up to 5 example commands |

## Output Format

Suggestions are written as a YAML policy document with `merge.strategy: append_unique` so they are safe to append without overwriting existing rules. A `_generated._evidence` block is embedded for traceability.

## CLI Command

```bash
policyctl learn [--since <time>] [--min-cluster-size <n>] [--min-confidence <f>] [--dry-run] [--audit-log-path <path>] [--repo-root <path>]
```

- `--dry-run`: Print YAML to stdout without writing to disk
- `--since`: ISO 8601 or shorthand (`7d`, `24h`, `30m`)

## Output Location

Non-dry-run writes to `policies/suggestions/auto-<date>.yaml`.

## Implementation

- **CLI command**: `learn`
- **Module**: `cli/src/policy_federation/learner.py`
- **CLI entrypoint**: `cli.py` `learn_command`

## Acceptance Criteria

- [ ] `--dry-run` prints each suggestion with id, description, confidence, and sample commands, then prints full YAML
- [ ] `--since` with shorthand (`7d`) correctly filters to the past 7 days
- [ ] `--since` with ISO 8601 correctly filters by timestamp
- [ ] `--min-cluster-size` excludes clusters below threshold
- [ ] `--min-confidence` excludes clusters below consistency threshold
- [ ] Empty audit log produces no output and exits 0
- [ ] `RuleSuggestion.id` uses `auto-<effect>-<safe-prefix>-NNN` format

## Traceability

- FR-GOV-006, FR-GOV-007, FR-GOV-008
