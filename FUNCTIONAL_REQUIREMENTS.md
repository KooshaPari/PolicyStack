# Functional Requirements -- policy-contract

**Version:** 1.0
**Status:** Active
**Last Updated:** 2026-03-26

All requirements use RFC 2119 SHALL/SHOULD/MAY language. Each requirement traces to a PRD epic.

---

## FR-RES: Policy Resolution

### FR-RES-001: Scope Discovery

The resolver SHALL discover policy files across the six scope levels (system, user, repo,
harness, task-domain, task-instance) by scanning the `<root>/policy-config/` directory tree
and any additional paths specified via CLI flags.

**Traces to:** PRD E1.1
**Implementation:** `resolve.py`, `policy_lib.py`

### FR-RES-002: Extension Precedence

Within each scope directory, the resolver SHALL deduplicate files with the same stem using
extension precedence: `.yaml` > `.yml` > `.json`. Only the highest-precedence variant is used.

**Traces to:** PRD E1.1
**Implementation:** `policy_lib.py` (stem dedup logic)

### FR-RES-003: Scope Merge Order

The resolver SHALL merge scopes in ascending specificity order: system, user, repo, harness,
task-domain, task-instance. Later scopes override earlier scopes on key collision. The
`command_rules` list is appended (not replaced) with deduplication by rule `id`.

**Traces to:** PRD E1.1
**Implementation:** `resolve.py`, `policy_lib.py`

### FR-RES-004: Policy Hash

Every resolved policy output SHALL include a `policy_hash` field containing the SHA-256 hex
digest of the canonical JSON representation of the final merged `policy` object.

**Traces to:** PRD E1.1
**Implementation:** `resolve.py`

### FR-RES-005: Scopes Chain

Every resolved policy output SHALL include a `scopes` field that lists every scope file
that contributed to the resolution, in merge order, with their file paths.

**Traces to:** PRD E1.1
**Implementation:** `resolve.py`

### FR-RES-006: CLI Parameters

`resolve.py` SHALL accept the following command-line parameters:

| Flag | Required | Description |
|---|---|---|
| `--root <path>` | Yes | Repository root containing `policy-config/` |
| `--harness <name>` | Yes | Harness name (codex, cursor, claude, factory-droid) |
| `--task-domain <name>` | Yes | Task domain (deployment, query, etc.) |
| `--emit <path>` | No | Output path for the resolved policy JSON |
| `--task-instance <path>` | No | Additional task-instance override file |
| `--emit-host-rules` | No | Trigger host artifact generation after resolution |
| `--host-out-dir <path>` | No | Directory for generated host artifacts |
| `--include-conditional` | No | Include conditional rules in host artifacts |
| `--apply-host-rules` | No | Apply artifacts directly to live host config locations |

**Traces to:** PRD E1.2
**Implementation:** `resolve.py` (argparse)

### FR-RES-007: Task-Instance Override

When `--task-instance <path>` is provided, `resolve.py` SHALL merge the specified file as the
highest-precedence scope (overriding all other scopes).

**Traces to:** PRD E1.2
**Implementation:** `resolve.py`

### FR-RES-008: Non-Zero Exit on Error

`resolve.py` SHALL exit with a non-zero status code when any resolution, validation, or I/O
error occurs. All error details SHALL be written to stderr.

**Traces to:** PRD E1.2

---

## FR-COND: Conditional Command Rules

### FR-COND-001: Nested Condition Groups

Command rules SHALL support a `conditions` field containing nested `all` and/or `any` groups
of predicate entries. Nesting SHALL be supported to at least two levels (e.g., `all` containing
an `any` group).

**Traces to:** PRD E2.1
**Implementation:** `policy_lib.py` (condition parsing), `scripts/sync_host_rules.py`

### FR-COND-002: Required Flag

Each condition entry SHALL support an optional `required` flag (boolean, default: `true`).
When `required` is `false` and the condition fails, the group MAY still pass depending on
other entries.

**Traces to:** PRD E2.1
**Implementation:** `policy_lib.py`

### FR-COND-003: On-Mismatch Fallback

Every command rule with a `conditions` block SHALL declare an `on_mismatch` field specifying
the fallback action (`allow`, `deny`, or `request`) to use when the condition evaluation fails.

**Traces to:** PRD E2.1
**Implementation:** `policy_lib.py`, `scripts/sync_host_rules.py`

### FR-COND-004: Built-In Git Predicates

The wrapper bundle SHALL document the following built-in predicates for cross-language
evaluators: `git_is_worktree`, `git_clean_worktree`, `git_synced_to_upstream`.

**Traces to:** PRD E2.1
**Implementation:** `agent-scope/policy_wrapper.schema.json`, `wrappers/`

### FR-COND-005: Unconditional vs Conditional Split

The host artifact generator SHALL separate unconditional rules (no `conditions` block) from
conditional rules. Unconditional rules SHALL be written directly into host config fragments.
Conditional rules SHALL be routed into the `policy_wrapper` bundle.

**Traces to:** PRD E2.2
**Implementation:** `scripts/sync_host_rules.py`

### FR-COND-006: Wrapper Bundle Schema

The `policy-wrapper-rules.json` artifact SHALL conform to `agent-scope/policy_wrapper.schema.json`
and SHALL include: `schema_version` (integer), `required_conditions` (list), and `commands`
(list of entries with `id`, `source`, `action`, `on_mismatch`, `matcher`, `pattern`,
`normalized_pattern`, `conditions`, `platform_action`).

**Traces to:** PRD E2.2
**Implementation:** `scripts/sync_host_rules.py`, `agent-scope/policy_wrapper.schema.json`

### FR-COND-007: Dispatch Manifest

A `policy-wrapper-dispatch.manifest.json` SHALL be generated alongside the wrapper bundle.
It SHALL include: `schema_version`, `bundle_path`, `dispatch_script`, `dispatch_command`
(template with `{command}` and `{cwd}`), `required_conditions`, `wrapper_rule_count`, and
`missing_policy_default`.

**Traces to:** PRD E2.2
**Implementation:** `scripts/sync_host_rules.py`

---

## FR-HOST: Host Rule Sync

### FR-HOST-001: Codex Rules Artifact

`sync_host_rules.py` SHALL generate `codex.rules` containing Codex `prefix_rule(...)` entries
for each unconditional allow/deny rule.

**Traces to:** PRD E3.1
**Implementation:** `scripts/sync_host_rules.py`

### FR-HOST-002: Cursor CLI Config Artifact

`sync_host_rules.py` SHALL generate `cursor.cli-config.json` with `allow` and `deny` shell
rule arrays for Cursor's managed fragment format.

**Traces to:** PRD E3.1
**Implementation:** `scripts/sync_host_rules.py`

### FR-HOST-003: Claude Settings Artifact

`sync_host_rules.py` SHALL generate `claude.settings.json` with `allow`, `deny`, and `ask`
shell rule arrays for Claude's settings format.

**Traces to:** PRD E3.1
**Implementation:** `scripts/sync_host_rules.py`

### FR-HOST-004: Factory-Droid Settings Artifact

`sync_host_rules.py` SHALL generate `factory-droid.settings.json` with `commandAllowlist`,
`commandRequestlist`, and `commandDenylist` arrays. Request-tier rules from the resolved
policy SHALL appear in `commandRequestlist`.

**Traces to:** PRD E3.1, E3.2
**Implementation:** `scripts/sync_host_rules.py`

### FR-HOST-005: Apply Mode

`sync_host_rules.py --apply` SHALL write generated artifacts directly to the default live
host config file locations without requiring a separate copy step.

**Traces to:** PRD E3.1
**Implementation:** `scripts/sync_host_rules.py`

### FR-HOST-006: JSON Output Mode

`sync_host_rules.py --json` SHALL emit a structured JSON payload containing `ok`, `mode`,
`platforms` (with per-platform rule counts and output paths), and a `summary` with total
rule counts.

**Traces to:** PRD E3.1
**Implementation:** `scripts/sync_host_rules.py`

---

## FR-GOV: Governance Validation

### FR-GOV-001: Schema Validation

`scripts/validate_policy_contract.py --root <dir>` SHALL validate all discovered policy scope
files against `agent-scope/policy_contract.schema.json`. It SHALL report each failing file
and the specific violations.

**Traces to:** PRD E4.1
**Implementation:** `scripts/validate_policy_contract.py`

### FR-GOV-002: Schema Validation JSON Mode

`validate_policy_contract.py --json` SHALL emit a JSON payload of the form
`{"type":"status","code":"ok"|"error","message":"..."}` followed by
`{"type":"summary","checked":N,"missing":N,"invalid":N}`.

**Traces to:** PRD E4.1
**Implementation:** `scripts/validate_policy_contract.py`

### FR-GOV-003: Snapshot Drift Detection

`scripts/generate_policy_snapshot.py --check-existing` SHALL resolve the current effective
policy and compare it against the committed canonical snapshot file. It SHALL exit non-zero
and report the diff when the hashes differ.

**Traces to:** PRD E4.2
**Implementation:** `scripts/generate_policy_snapshot.py`

### FR-GOV-004: Snapshot Write and Validate

`generate_policy_snapshot.py --write-canonical` SHALL regenerate all canonical snapshots.
`--validate-canonical` SHALL verify that all canonical snapshots exist and match current
resolution.

**Traces to:** PRD E4.2
**Implementation:** `scripts/generate_policy_snapshot.py`

### FR-GOV-005: Version Governance

`scripts/check_policy_versions.py --root <dir>` SHALL verify that every policy scope file
declares a `version` field whose value is in the `allowed_versions` list. Files with missing
or invalid versions SHALL cause a non-zero exit.

**Traces to:** PRD E4.3
**Implementation:** `scripts/check_policy_versions.py`

### FR-GOV-006: Version Governance JSON Mode

`check_policy_versions.py --json` SHALL emit a JSON payload with `code`, `message`,
`details.allowed_versions`, `details.missing_required`, `details.observed_versions`, and
`details.summary` (checked, missing_required, invalid_versions counts).

**Traces to:** PRD E4.3
**Implementation:** `scripts/check_policy_versions.py`

### FR-GOV-007: Universal Exit-Code Convention

All governance scripts (validate_policy_contract, check_policy_versions,
generate_policy_snapshot, sync_host_rules, resolve) SHALL use exit code 0 for pass/success
and non-zero for any governance failure or invalid invocation.

**Traces to:** PRD E4.1, E4.2, E4.3
**Implementation:** All scripts in `scripts/`

### FR-GOV-008: Smoke Test Coverage

`tests/test_smoke_dispatch_host_hook.py` SHALL verify the end-to-end dispatch flow: resolve
policy, generate wrapper bundle, invoke wrapper dispatch script, and assert correct
allow/deny/request output.

**Traces to:** PRD E2.2
**Implementation:** `tests/test_smoke_dispatch_host_hook.py`, `scripts/smoke_dispatch_host_hook.sh`

---

## FR-SCHEMA: Schema Artifacts

### FR-SCHEMA-001: Policy Contract Schema

`agent-scope/policy_contract.schema.json` SHALL be the canonical JSON Schema for all policy
scope YAML/JSON files. It SHALL define: `version`, `policy.command_rules` (with `id`,
`action`, `match`, `on_mismatch`, `conditions`), and any other top-level policy fields.

**Traces to:** PRD E4.1
**Implementation:** `agent-scope/policy_contract.schema.json`

### FR-SCHEMA-002: Wrapper Schema

`agent-scope/policy_wrapper.schema.json` SHALL be the canonical JSON Schema for the
cross-language wrapper payload. It SHALL define the `commands` array shape and
`required_conditions` field.

**Traces to:** PRD E2.2
**Implementation:** `agent-scope/policy_wrapper.schema.json`
