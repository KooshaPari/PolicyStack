# PRD - policy-contract

## E1: Policy Scope Stack

### E1.1: Hierarchical Policy Resolution
As a multi-agent operator, I define policies at system/user/repo/harness/task-domain/task-instance scopes, and the resolver merges them with deterministic precedence.

**Acceptance**: 6-level scope hierarchy; extension precedence (yaml > yml > json); dedup by stem.

### E1.2: Policy Resolution CLI
As a CI pipeline, I resolve effective policy to JSON via CLI with harness and task-domain parameters.

**Acceptance**: `resolve.py` emits JSON with `policy_hash`, `scopes` chain, and final `policy`.

## E2: Conditional Command Rules

### E2.1: Conditional Predicates
As a policy author, I define command rules with nested `all`/`any` condition groups that gate allow/deny/request decisions.

**Acceptance**: Git predicates (`git_is_worktree`, `git_clean_worktree`, `git_synced_to_upstream`); `on_mismatch` fallback; `required` flag.

## E3: Host Rule Sync

### E3.1: Multi-Host Artifact Generation
As a platform operator, I generate host-specific policy artifacts for Codex, Cursor, Claude, and Factory-Droid from a single resolved policy.

**Acceptance**: Codex rules, Cursor CLI config, Claude settings, Factory-Droid command lists, policy-wrapper bundles.

### E3.2: Wrapper Dispatch
As a host hook layer, I consume wrapper payloads for Go/Rust/Zig evaluators to make runtime conditional decisions.

**Acceptance**: `policy-wrapper-rules.json` with schema version, conditions, and normalized patterns.

## E4: Governance Validation

### E4.1: Schema Validation
Policy scope files SHALL be validated against `policy_contract.schema.json`.

### E4.2: Snapshot Drift Detection
Canonical snapshots SHALL be compared against current resolution to detect drift.

### E4.3: Version Governance
All policy files SHALL declare allowed versions; missing or invalid versions are governance failures.
