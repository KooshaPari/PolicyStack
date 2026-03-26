# Architecture Decision Records -- policy-contract

**Format:** ADR-NNN: Title | Status | Date

---

## ADR-001: Six-Level Scope Hierarchy

**Status:** Accepted
**Date:** 2025-01-01 (initial design; confirmed 2026-03-26)

### Context

Multi-agent environments require layered policy control. A single global policy is too
coarse: different repositories, harnesses, and task domains need different safety constraints.
Operator-level overrides must be separate from per-repo baselines, which must be separate from
task-specific one-offs.

### Decision

Policy is resolved across six scope levels in ascending specificity order:
system > user > repo > harness > task-domain > task-instance.

### Rationale

- Six levels map cleanly to the organizational hierarchy of a multi-tenant AgentOps platform.
- System and user scopes provide hard constraints that repo authors cannot override.
- Harness and task-domain scopes allow different AI agents and task types to have tailored
  rules without forking the entire policy.
- Task-instance is the escape hatch for one-off per-request overrides without polluting
  standing policy.

### Alternatives Considered

- **Flat single file per harness:** Simpler but no inheritance; every harness must duplicate
  shared rules.
- **Three-level (system/repo/task):** Loses harness-level isolation needed when multiple
  agent types (Codex, Claude) share a repo.

### Consequences

- Positive: fine-grained override at each level; deterministic merge order.
- Negative: six levels add cognitive overhead for simple configurations; mitigated by the
  fact that most repos only need `repo.yaml` and one harness file.

---

## ADR-002: Extension Precedence for Format Deduplication

**Status:** Accepted
**Date:** 2025-01-01 (confirmed 2026-03-26)

### Context

Policy authors may write files as YAML or JSON. The same logical policy could exist as
`repo.yaml`, `repo.yml`, and `repo.json` in the same directory, creating ambiguity.

### Decision

Within each scope directory, files with the same stem are deduplicated using extension
precedence: `.yaml` > `.yml` > `.json`. Only the highest-precedence variant is loaded.

### Rationale

- YAML is the preferred authoring format (more readable, supports comments).
- Deterministic precedence eliminates ambiguity without requiring authors to delete old files.
- JSON is kept as a fallback for machine-generated policy files.

### Consequences

- Positive: no ambiguity when multiple formats coexist; YAML authoring is encouraged.
- Negative: a JSON file silently superseded by a YAML file may confuse operators who do not
  know the precedence rule; mitigated by documenting it prominently.

---

## ADR-003: Conditional Rules via Nested all/any Groups with required Flag

**Status:** Accepted
**Date:** 2025-06-01 (confirmed 2026-03-26)

### Context

Simple binary allow/deny rules are insufficient for git safety checks. A `git checkout`
command should be allowed only when the workspace is a worktree AND is clean. Some checks
should be advisory (warn but not block), requiring a `required: false` flag.

### Decision

Command rules support a `conditions` block containing nested `all` and `any` groups. Each
condition entry names a predicate and an optional `required` flag. Rules specify `on_mismatch`
as the fallback action when conditions are not met.

### Rationale

- `all`/`any` mirrors standard boolean logic and is readable by non-expert policy authors.
- `required: false` enables advisory predicates without changing the overall decision unless
  all non-required predicates in an `any` group fail.
- `on_mismatch: request` allows agents to surface a user confirmation prompt instead of
  hard-blocking a command.
- The same condition schema is consumed by Go, Rust, and Zig evaluators, making it
  language-neutral.

### Alternatives Considered

- **CEL/OPA policy language:** Expressive but requires a heavy runtime in each evaluator.
- **Simple AND-only conditions:** Cannot express "clean OR synced" patterns needed for some
  git safety rules.

### Consequences

- Positive: rich conditional logic; consistent schema across Python generator and
  cross-language evaluators.
- Negative: nested groups add schema complexity; mitigated by authoritative YAML snippets in
  CLAUDE.md.

---

## ADR-004: Unconditional vs Conditional Split in Host Artifacts

**Status:** Accepted
**Date:** 2025-06-01 (confirmed 2026-03-26)

### Context

Host configurations (Cursor managed fragments, Claude settings) are static files that support
simple allow/deny arrays with no runtime evaluation capability. Complex conditional rules
cannot be expressed directly in these formats.

### Decision

The host artifact generator splits rules into two categories:
- **Unconditional** (no `conditions` block): written directly into host config fragments.
- **Conditional** (has `conditions` block): routed into `policy-wrapper-rules.json` and the
  dispatch manifest; not written into static host config files.

### Rationale

- Static host fragments are consumed by the harness directly with no evaluation overhead.
- Wrapper bundles are consumed by cross-language evaluator hooks that run before command
  execution and can evaluate predicates at runtime.
- The split is transparent: policy authors write uniform YAML; the generator handles routing.

### Consequences

- Positive: simple rules work natively in all hosts with zero overhead; complex rules get
  full conditional evaluation via wrapper dispatch.
- Negative: Cursor and Claude hosts do not natively support request-tier actions; request
  rules are emitted as `deny` in static fragments and only get full request semantics through
  wrapper dispatch.

---

## ADR-005: SHA-256 Policy Hash for Audit Trails

**Status:** Accepted
**Date:** 2025-01-01 (confirmed 2026-03-26)

### Context

CI pipelines and audit logs need to verify that the effective policy used for a given task
run has not changed between runs. A human-readable diff of YAML files is insufficient for
automated comparison.

### Decision

Every resolved policy output includes a `policy_hash` field containing the SHA-256 hex digest
of the canonical JSON serialization of the final merged `policy` object.

### Rationale

- SHA-256 is deterministic and collision-resistant; equal hashes guarantee policy identity.
- Canonical JSON serialization (sorted keys, no whitespace) ensures the hash is stable across
  formatting changes.
- Snapshot drift detection compares hashes rather than deep-diffing JSON, making the check
  O(1) and suitable for CI.

### Consequences

- Positive: fast, reliable policy identity check in CI and audit logs.
- Negative: hash changes on any policy edit, including comments or key reordering in the
  source YAML; mitigated by the snapshot workflow which explicitly tracks when drift is
  intentional.

---

## ADR-006: Python as the Reference Resolver and Generator

**Status:** Accepted
**Date:** 2025-01-01 (confirmed 2026-03-26)

### Context

The policy resolver, host artifact generator, and governance scripts need to run in CI and
local developer environments. The platform already uses Python for AgentOps tooling. Runtime
evaluators in agents need a faster language.

### Decision

The resolver (`resolve.py`), host artifact generator (`scripts/sync_host_rules.py`), and
all governance scripts are written in Python. Cross-language runtime evaluators (Go, Rust,
Zig) consume the JSON output of the Python generator.

### Rationale

- Python is already in the platform toolchain; no new language runtime for CI.
- YAML/JSON parsing is first-class in Python (PyYAML, json stdlib).
- Runtime evaluators are latency-sensitive; Go/Rust/Zig are appropriate for per-command
  evaluation in agent hooks.
- The Python generator is the single source of truth; evaluators consume its output,
  eliminating divergence risk.

### Consequences

- Positive: single authoritative generator; CI requires only `uv`/`python` with PyYAML.
- Negative: evaluator authors must understand the JSON schema output by the Python generator;
  mitigated by `agent-scope/policy_wrapper.schema.json` and reference implementations in
  `wrappers/`.

---

## ADR-007: Snapshot-Based Drift Detection over Live Diff

**Status:** Accepted
**Date:** 2025-09-01 (confirmed 2026-03-26)

### Context

Policy changes in a PR should be detectable before merge. Options are: (a) re-resolve and
diff against the committed baseline, or (b) run a semantic diff of YAML files.

### Decision

Canonical snapshots are committed to `policy-config/snapshots/` and compared against fresh
resolution on every CI run (`--check-existing`). The comparison uses `policy_hash` for fast
equality and a JSON diff for human-readable mismatch output.

### Rationale

- Hash comparison is O(1) and suitable for pre-merge checks.
- Committed snapshots make policy changes explicit in PRs (the snapshot file diff is visible
  in code review).
- Semantic YAML diff would require parsing both sides and normalizing before comparison;
  hash-based comparison avoids that complexity.

### Consequences

- Positive: policy changes are always visible in PRs; CI detects unintended drift.
- Negative: snapshots must be regenerated (`--write-canonical`) when policy changes are
  intentional; adds a step to the policy change workflow.
