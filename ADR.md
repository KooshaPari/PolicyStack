# Architecture Decision Records - policy-contract

## ADR-001: 6-Level Scope Hierarchy
**Status**: Accepted
**Context**: Multi-agent environments need layered policy control.
**Decision**: system > user > repo > harness > task-domain > task-instance scope chain.
**Consequences**: Fine-grained override at each level; deterministic merge order.

## ADR-002: Extension Precedence for Dedup
**Status**: Accepted
**Context**: Same policy stem may exist in multiple formats.
**Decision**: `.yaml` > `.yml` > `.json` precedence; dedup by stem within each scope directory.
**Consequences**: No ambiguity when multiple formats coexist.

## ADR-003: Conditional Rules via Nested all/any Groups
**Status**: Accepted
**Context**: Simple allow/deny is insufficient for git safety checks.
**Decision**: Support nested `all`/`any` condition groups with `required` flags and `on_mismatch` fallback.
**Consequences**: Rich conditional logic; cross-language evaluators consume the same schema.

## ADR-004: Unconditional vs Conditional Split in Host Artifacts
**Status**: Accepted
**Context**: Host configs (Cursor, Claude) have no native conditional evaluation.
**Decision**: Unconditional rules go directly into host fragments; conditional rules route to wrapper payloads.
**Consequences**: Simple rules work natively; complex rules need wrapper dispatch layer.
