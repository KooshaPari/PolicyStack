# Functional Requirements - policy-contract

## FR-RES-001: Scope Discovery
The resolver SHALL discover policy files across 6 scope levels with deterministic precedence.

## FR-RES-002: Extension Precedence
Same-stem files SHALL be deduplicated using `.yaml` > `.yml` > `.json` precedence.

## FR-RES-003: Policy Hash
Resolved policy output SHALL include a SHA-256 `policy_hash` for audit trails.

## FR-RES-004: CLI Interface
`resolve.py` SHALL accept `--root`, `--harness`, `--task-domain`, `--emit` parameters.

## FR-COND-001: Nested Condition Groups
Command rules SHALL support nested `all`/`any` condition groups.

## FR-COND-002: Required Flag
Each condition SHALL have an optional `required` flag (default: true).

## FR-COND-003: On-Mismatch Fallback
Rules with conditions SHALL specify `on_mismatch` action (allow/deny/request).

## FR-HOST-001: Multi-Host Artifact Generation
`sync_host_rules.py` SHALL generate Codex, Cursor, Claude, Factory-Droid, and wrapper artifacts.

## FR-HOST-002: Wrapper Payload Schema
Wrapper payloads SHALL conform to `policy_wrapper.schema.json` with schema version, conditions, and patterns.

## FR-GOV-001: Schema Validation
`validate_policy_contract.py` SHALL validate scope files against the contract schema.

## FR-GOV-002: Snapshot Drift Detection
`generate_policy_snapshot.py --check-existing` SHALL detect drift from canonical snapshots.

## FR-GOV-003: Version Governance
`check_policy_versions.py` SHALL enforce allowed policy versions across all scope files.

## FR-GOV-004: JSON Exit-Code Convention
All governance scripts SHALL use exit code 0 for pass, non-zero for failure, with optional JSON output.
