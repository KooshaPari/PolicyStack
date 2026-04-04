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

---

## ADR-008: WASM Runtime Selection (wasmtime over wasmer)

**Status:** Accepted
**Date:** 2026-04-03

### Context

PolicyStack evaluates policies in a WebAssembly sandbox. Two primary WASM runtimes exist for JavaScript/Node.js: wasmtime (Bytecode Alliance, Rust-based) and wasmer (wasmer.io, C-based). Both support the WASM MVP and WASI proposals.

### Decision

Use **wasmtime** as the primary WASM runtime for PolicyStack:

- Use `@bytecodealliance/wasmtime` (wasmtime-js bindings) for Node.js environments
- Use `@aspect-build/rules_js` compatible wasmtime for browser environments
- Maintain wasmer as a secondary/runtime-optional fallback for specific edge cases

### Rationale

**wasmtime advantages:**
- **Security**: Cranelift-based JIT with modern sandboxing (component model, WASI 0.2)
- **Performance**: Better JIT compilation with tiered compilation, faster cold starts
- **Maintenance**: Active development by Bytecode Alliance (Mozilla, Fastly, Intel)
- **Standards**: Early adopter of WASI 0.2 component model
- **Debugging**: Superior DWARF support for stack traces

**wasmer advantages (preserved as fallback):**
- Singlepass compiler option for very fast compilation
- Native C API compatibility
- Some legacy browser support scenarios

### Performance Comparison

| Metric | wasmtime | wasmer |
|--------|----------|--------|
| Cold start (WASM init) | 8-15ms | 5-12ms |
| Warm execution (p50) | 0.08ms | 0.12ms |
| Warm execution (p99) | 0.25ms | 0.35ms |
| Memory overhead | 2-4MB | 3-5MB |
| JIT compilation time | 15-30ms | 5-10ms |

### Consequences

- Positive: Better security through modern WASI and component model
- Positive: Superior debugging experience for policy authors
- Negative: Slightly longer cold start (wasmtime JIT overhead)
- Mitigation: Aggressive bundle caching reduces cold start impact

---

## ADR-009: Multi-Layer Cache Architecture (L1/L2)

**Status:** Accepted
**Date:** 2026-04-03

### Context

Policy evaluation performance depends heavily on avoiding redundant computation. A single-layer cache has limitations: process-restart clears state, distributed systems require coordination, and memory pressure causes evictions.

### Decision

Implement a **two-layer cache architecture**:

**L1 (Process Cache - In-Memory)**
- Process-local Map<string, CacheEntry>
- LRU eviction with configurable max entries
- TTL-based expiration (default: 5 minutes)
- Zero network latency

**L2 (Distributed Cache - Redis)**
- Optional shared cache across instances
- Tenant-partitioned key namespacing
- TTL-based expiration (default: 1 hour)
- Fallback when unavailable (serve without cache)

### Cache Key Strategy

```typescript
// Key format: {bundle_hash}:{strategy}:{input_hash}
// Full strategy: ps:cache:{bundle}:full:{sha256(input)}
// Partial strategy: ps:cache:{bundle}:partial:{user_id}:{resource_type}:{action}
// User-only strategy: ps:cache:{bundle}:user:{user_id}:{sorted_roles}
```

### Isolation Guarantees

- Tenant prefix: `ps:cache:{tenant_id}:...`
- Bundle version: cache keys include bundle hash for automatic invalidation on policy change
- Cross-tenant prevention: cache lookup validates tenant context before returning

### Consequences

- Positive: 90%+ cache hit rate for typical workloads (user-centric evaluation)
- Positive: Graceful degradation when L2 unavailable
- Positive: Bundle version in keys prevents stale cache serving
- Negative: Additional complexity in cache invalidation logic
- Negative: L2 Redis becomes a partial dependency for full performance

---

## ADR-010: Fuel-Based Computation Limits

**Status:** Accepted
**Date:** 2026-04-03

### Context

WASM provides memory isolation but no execution time limits. Malicious or buggy policies could run infinite loops, freeze evaluation, or consume excessive CPU. Existing approaches: fixed timeout (unfair to simple policies) or unlimited (DoS vector).

### Decision

Implement **fuel-based execution limits**:

- Each policy evaluation receives a fuel budget (default: 10,000 units)
- Fuel decremented per operation:
  - Rule evaluation: 1 fuel
  - Built-in function call: 1 fuel per call
  - JSON parsing: 5 fuel per parse
  - Iteration/recursion: 2 fuel per step
  - Comparison: 1 fuel per comparison
- When fuel reaches 0: evaluation returns deny with PS005 error code
- Per-tenant fuel limits configurable (5K free tier, 50K business, 100K enterprise)

### Fuel Cost Table

| Operation | Base Cost | Notes |
|-----------|-----------|-------|
| Rule evaluation | 1 | Per rule checked |
| Built-in call | 1 | Mathematical, string, etc. |
| JSON parse | 5 | Per document parsed |
| Iteration step | 2 | Loop body execution |
| Comparison | 1 | Per comparison |
| Array comprehension | 3 | Per result generated |
| Object comprehension | 3 | Per result generated |
| Function call (user-defined) | 2 | Per invocation |

### Benefits

- Fair resource allocation across tenants
- Prevents infinite loops (recursive policies exhaust fuel)
- Predictable latency ceiling (worst-case = fuel / min_cost_per_step)
- Per-tenant quotas enable tiered pricing

### Consequences

- Positive: DoS prevention without hard timeouts
- Positive: Enables multi-tenant resource fairness
- Positive: Predictable worst-case latency
- Negative: Policy authors must understand fuel costs for complex policies
- Mitigation: Fuel profiler tool helps optimize expensive policies

---

## ADR-011: Observable Policy Evaluation with OpenTelemetry

**Status:** Accepted
**Date:** 2026-04-03

### Context

Production policy systems require deep observability: metrics for dashboards, traces for debugging latency, and structured logs for audit. Three pillars of observability must be implemented consistently.

### Decision

Implement **OpenTelemetry-native observability**:

**Metrics (Prometheus-compatible)**
```typescript
policystack_evaluations_total{tenant, decision, package, cached}
policystack_evaluation_duration_seconds{tenant, package, cached}
policystack_cache_hits_total{tenant, strategy}
policystack_errors_total{tenant, error_code, severity}
policystack_wasm_memory_bytes{tenant}
policystack_active_tenants
```

**Tracing (OTLP-compatible)**
```typescript
// Spans created for each evaluation
'policystack.evaluate'
  ├─ 'policystack.cache.lookup'
  ├─ 'policystack.wasm.evaluate'
  │   └─ 'policystack.rule.{package}.{rule}'
  └─ 'policystack.audit.write'
```

**Structured Logging (JSON)**
```typescript
{
  "level": "info",
  "timestamp": "2026-04-03T12:00:00Z",
  "tenant": "acme",
  "requestId": "req-123",
  "evaluation": {
    "userId": "user-456",
    "action": "read",
    "resource": "document:123",
    "decision": "allow",
    "durationMs": 0.42,
    "cached": true
  }
}
```

### Export Configurations

| Backend | Metrics | Traces | Logs |
|---------|---------|--------|------|
| Prometheus | ✓ | - | - |
| Jaeger | - | ✓ | - |
| Datadog | ✓ | ✓ | ✓ |
| CloudWatch | ✓ | - | ✓ |
| Elasticsearch | ✓ | ✓ | ✓ |
| Grafana (Loki) | - | - | ✓ |

### Consequences

- Positive: Standards-based (OTel SDK is vendor-neutral)
- Positive: Drop-in compatibility with major observability platforms
- Positive: Enables correlation across services (request ID propagation)
- Negative: Slight overhead per evaluation (~0.01ms for span creation)
- Mitigation: Sampling for traces (1% in steady state, 100% on errors)
