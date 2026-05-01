# Product Requirements Document -- policy-contract

**Version:** 1.0
**Status:** Active
**Last Updated:** 2026-03-26

## Overview

policy-contract is the canonical policy scope model and resolver for Phenotype's multi-agent
AgentOps platform. It defines a 6-level hierarchical scope stack (system -> user -> repo ->
harness -> task-domain -> task-instance), a Python resolver that merges scopes into a
deterministic effective policy, host-specific artifact generators for Codex / Cursor / Claude /
Factory-Droid, and governance tooling (schema validation, snapshot drift detection, version
enforcement).

The resolved policy controls which shell commands each AI agent harness may allow, deny, or
request at runtime, and provides conditional rules evaluated by cross-language wrapper
evaluators (Go, Rust, Zig).

## Target Users

| User | Context |
|---|---|
| Multi-agent platform operator | Defines system-wide and user-level hard constraints |
| Repository owner | Maintains `repo.yaml` contract baseline for all agents in the repo |
| Harness integrator (Codex, Cursor, Claude, Factory-Droid) | Consumes generated host artifacts and wrapper bundles |
| CI/CD pipeline | Resolves effective policy on each run, validates schema and snapshots |
| Cross-language evaluator author (Go/Rust/Zig) | Consumes `policy-wrapper-rules.json` for runtime conditional decisions |

---

## Epics

### E1: Policy Scope Stack

#### E1.1: Hierarchical Policy Resolution

As a multi-agent operator, I define policies at system, user, repo, harness, task-domain, and
task-instance scopes, and the resolver merges them with deterministic precedence, so that
more-specific scopes override less-specific ones without ambiguity.

**Acceptance Criteria:**
- Six scope levels are resolved in order: system, user, repo, harness, task-domain,
  task-instance.
- Each scope contributes its `command_rules` and policy fields; later scopes override earlier
  scopes on key collision.
- Within each discovery scope directory, files are deduplicated by stem using extension
  precedence (`.yaml` > `.yml` > `.json`).
- The resolver emits a `policy_hash` (SHA-256 of the final merged policy) for audit trails.
- The `scopes` chain in the output lists every scope file that contributed to the resolution
  in order.

#### E1.2: Policy Resolution CLI

As a CI pipeline, I resolve the effective policy to JSON via `resolve.py` with harness and
task-domain parameters, so that downstream tools and agents receive a stable, auditable
policy artifact.

**Acceptance Criteria:**
- `resolve.py --root <dir> --harness <name> --task-domain <name> --emit <path>` writes a
  JSON file containing `policy_hash`, `scopes`, and `policy`.
- `--task-instance <path>` optionally injects a per-task-instance override file as the
  highest-precedence scope.
- `--emit-host-rules` triggers host artifact generation inline.
- `--include-conditional` includes conditional rule payloads in the output.
- Non-zero exit on any resolution or validation error; error details on stderr.

---

### E2: Conditional Command Rules

#### E2.1: Conditional Predicates

As a policy author, I define command rules with nested `all`/`any` condition groups that gate
allow/deny/request decisions on runtime predicates, so that commands like `git checkout` are
only allowed when workspace safety conditions hold.

**Acceptance Criteria:**
- Command rules support `conditions` with `all` / `any` nested groups.
- Built-in git predicates: `git_is_worktree`, `git_clean_worktree`,
  `git_synced_to_upstream`.
- Each condition entry supports a `required` flag (default: `true`).
- `on_mismatch` specifies the fallback action (`allow`, `deny`, `request`) when conditions
  are not met.
- Rules without conditions are treated as unconditional.

#### E2.2: Wrapper Dispatch Protocol

As a host hook layer, I consume the wrapper bundle for cross-language evaluators (Go/Rust/Zig)
to make runtime conditional decisions, so that hosts without native conditional evaluation
still enforce complex policies.

**Acceptance Criteria:**
- Resolved output includes a `policy_wrapper` block with `schema_version`, required
  conditions, and normalized command entries.
- A `policy-wrapper-dispatch.manifest.json` is generated alongside the wrapper bundle,
  containing the dispatch script path, bundle path, and `required_conditions` list.
- The manifest `dispatch_command` template includes `{command}` and `{cwd}` template variables.
- Evaluators respond with `allow`, `request`, or `deny`; host uses `missing_policy_default`
  for unmatched commands.

---

### E3: Host Rule Sync

#### E3.1: Multi-Host Artifact Generation

As a platform operator, I generate host-specific policy artifacts for Codex, Cursor, Claude,
and Factory-Droid from a single resolved policy, so that each harness enforces the correct
rules without manual configuration.

**Acceptance Criteria:**
- `scripts/sync_host_rules.py --policy-json <path> --out-dir <dir>` generates:
  - `codex.rules` -- Codex `prefix_rule(...)` entries (unconditional rules only).
  - `cursor.cli-config.json` -- Cursor allow/deny shell rules.
  - `claude.settings.json` -- Claude allow/deny/ask shell rules.
  - `factory-droid.settings.json` -- Factory-Droid allow/request/deny command lists.
  - `policy-wrapper-rules.json` -- machine schema for conditional evaluators.
  - `policy-wrapper-dispatch.manifest.json` -- runtime wiring manifest.
- `--apply` writes artifacts directly to live host config file locations.
- `--json` emits structured JSON output with rule counts and output paths.
- Unconditional rules go into host fragments; conditional rules route into wrapper payloads.

#### E3.2: Factory-Droid Request Support

As a Factory-Droid operator, I receive explicit allow/request/deny command lists so that
Factory-Droid can surface user confirmation prompts for request-tier commands.

**Acceptance Criteria:**
- `factory-droid.settings.json` contains `commandAllowlist`, `commandRequestlist`, and
  `commandDenylist` keys.
- Request-action rules from resolved policy are placed in `commandRequestlist`.

---

### E4: Governance Validation

#### E4.1: Schema Validation

As a policy author, I validate all policy scope files against the canonical JSON schema so
that malformed policy files are caught before deployment.

**Acceptance Criteria:**
- `scripts/validate_policy_contract.py --root <dir>` validates all scope files against
  `agent-scope/policy_contract.schema.json`.
- Exit code 0 means all files pass; non-zero means at least one failure.
- `--json` flag emits a structured JSON summary with `checked`, `missing`, `invalid` counts.
- Governance failures list each failing file and the specific schema violations.

#### E4.2: Snapshot Drift Detection

As a CI pipeline, I compare the current resolved policy against a committed canonical snapshot
so that unintended policy changes are detected before merge.

**Acceptance Criteria:**
- `scripts/generate_policy_snapshot.py --check-existing` compares the freshly resolved policy
  against the committed snapshot file; exits non-zero on mismatch.
- `--write-canonical` regenerates and commits all canonical snapshots.
- `--validate-canonical` validates that all canonical snapshots exist and match current
  resolution.
- `--json` emits a structured result with `status`, `policy_hash`, and mismatch details.

#### E4.3: Version Governance

As a governance enforcer, I verify that all policy scope files declare an allowed version so
that version drift is caught early.

**Acceptance Criteria:**
- `scripts/check_policy_versions.py --root <dir>` checks that every scope file has a
  `version` field whose value is in the `allowed_versions` list.
- Exit code 0 means all files pass; non-zero on any missing or invalid version.
- `--json` emits `allowed_versions`, `observed_versions`, and `missing_required` counts.

---

## Non-Goals

- Runtime predicate evaluation in Python (predicates are evaluated by Go/Rust/Zig wrappers
  or host hooks; Python only produces the bundle).
- Policy enforcement for non-agent human operators.
- Network-based policy distribution or remote policy fetch.
- GUI configuration of policy files.
