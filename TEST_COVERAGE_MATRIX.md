# Test Coverage Matrix

**Project**: PolicyStack
**Document Version**: 2.0
**Last Updated**: 2026-05-05

---

## Coverage Summary

| Metric | Value |
|--------|-------|
| Total Test Files | 40 |
| Total Test Functions | 526 |
| Coverage Target | 80% |
| Current Coverage | Pending measurement (run `pytest --cov`) |

---

## Test Inventory

### Top-Level Test Suite (19 files, 224 tests)

| Test File | Test Count | Purpose |
|-----------|------------|---------|
| `test_config_loader.py` | 25 | Config loading, env overrides, merge logic |
| `test_delegation.py` | 22 | Delegation chains, cache, harness fallback |
| `test_integration.py` | 18 | Cross-component integration |
| `test_performance.py` | 10 | Performance benchmarks |
| `test_platform_wrappers.py` | 23 | Cross-platform wrapper dispatch |
| `test_policy_common.py` | 4 | Policy path discovery, dedup, normalization |
| `test_policy_contract.py` | 67 | Policy contract validation and schema |
| `test_policy_contract_governance_workflow.py` | 5 | Contract governance workflow |
| `test_policy_contract_stack_audit.py` | 5 | Contract stack audit |
| `test_policy_contract_validation_governance.py` | 13 | Validation governance checks |
| `test_policy_snapshot_governance.py` | 8 | Snapshot governance |
| `test_policy_version_governance.py` | 8 | Version governance |
| `test_pyo3_integration.py` | 12 | Python/Rust (PyO3) integration |
| `test_resolve_cli_governance.py` | 10 | CLI resolve command governance |
| `test_risk_tiers.py` | 12 | Risk tier assessment |
| `test_smoke.py` | 1 | Top-level smoke test |
| `test_smoke_dispatch_host_hook.py` | 4 | Host hook smoke tests |
| `test_sync_host_rules_governance.py` | 21 | Host rules sync governance |

### Unit Tests (20 files, 288 tests)

| Test File | Test Count | Module Under Test |
|-----------|------------|-----------------|
| `unit/test_audit.py` | 20 | `runtime_artifacts` |
| `unit/test_authorization.py` | 16 | `authorization` |
| `unit/test_authorization_repo_operations.py` | 9 | `authorization` (repo ops) |
| `unit/test_claude_hooks.py` | 61 | `claude_hooks` |
| `unit/test_cli_parsers.py` | 2 | `cli` argument parsing |
| `unit/test_cli_review.py` | 1 | `cli` review command |
| `unit/test_compiler.py` | 6 | `compiler` |
| `unit/test_delegate.py` | 9 | `delegate` |
| `unit/test_gap_detector.py` | 4 | `gap_detector` |
| `unit/test_headless_review.py` | 3 | `headless_review` |
| `unit/test_interceptor.py` | 15 | `interceptor` |
| `unit/test_learner.py` | 8 | `learner` |
| `unit/test_policy_diff.py` | 13 | `policy_diff` |
| `unit/test_policy_editor.py` | 9 | `policy_editor` |
| `unit/test_policy_editor_cli.py` | 12 | `cli` add/remove rule commands |
| `unit/test_policy_resolution.py` | 5 | `resolver` |
| `unit/test_risk.py` | 9 | `risk` |
| `unit/test_runtime_artifacts.py` | 16 | `runtime_artifacts` |
| `unit/test_runtime_context.py` | 3 | `runtime_context` |
| `unit/test_runtime_integrations.py` | 2 | `runtime_launchers` |

### Integration Tests (1 file, 30 tests)

| Test File | Test Count | Scope |
|-----------|------------|-------|
| `integration/test_e2e_claude_hook.py` | 30 | End-to-end Claude hook integration |

---

## FR to Test Coverage Mapping

| FR ID | Description | Primary Test Files | Status |
|-------|-------------|-------------------|--------|
| FR-RES-001 | Scope Discovery | `test_policy_common.py`, `unit/test_policy_resolution.py` | Covered |
| FR-RES-002 | Extension Precedence | `test_policy_common.py` | Covered |
| FR-RES-003 | Scope Merge Order | `unit/test_policy_resolution.py`, `test_policy_common.py` | Covered |
| FR-RES-004 | Policy Hash | `unit/test_policy_resolution.py` | Covered |
| FR-RES-005 | Scopes Chain | `unit/test_policy_resolution.py` | Covered |
| FR-RES-006 | CLI Parameters | `test_resolve_cli_governance.py` | Covered |
| FR-RES-007 | Task-Instance Override | `test_integration.py` | Covered |
| FR-RES-008 | Non-Zero Exit on Error | `test_resolve_cli_governance.py` | Covered |
| FR-COND-001 | Nested Condition Groups | `test_policy_contract.py` | Covered |
| FR-COND-002 | Required Flag | `test_policy_contract.py` | Covered |
| FR-COND-003 | On-Mismatch Fallback | `test_policy_contract.py` | Covered |
| FR-COND-004 | Built-In Git Predicates | `test_policy_contract.py` | Covered |
| FR-COND-005 | Unconditional vs Conditional Split | `test_policy_contract.py` | Covered |
| FR-COND-006 | Wrapper Bundle Schema | `test_platform_wrappers.py` | Covered |
| FR-COND-007 | Dispatch Manifest | `test_platform_wrappers.py` | Covered |
| FR-HOST-001 | Codex Rules Artifact | `test_sync_host_rules_governance.py` | Covered |
| FR-HOST-002 | Cursor CLI Config Artifact | `test_sync_host_rules_governance.py` | Covered |
| FR-HOST-003 | Claude Settings Artifact | `test_sync_host_rules_governance.py` | Covered |
| FR-HOST-004 | Factory-Droid Settings Artifact | `test_sync_host_rules_governance.py` | Covered |
| FR-HOST-005 | Apply Mode | `test_sync_host_rules_governance.py`, `test_smoke_dispatch_host_hook.py` | Covered |
| FR-HOST-006 | JSON Output Mode | `test_sync_host_rules_governance.py` | Covered |
| FR-GOV-001 | Schema Validation | `test_policy_contract_governance_workflow.py`, `test_policy_contract_validation_governance.py` | Covered |
| FR-GOV-002 | Schema Validation JSON Mode | `test_policy_contract_validation_governance.py` | Covered |
| FR-GOV-003 | Snapshot Drift Detection | `test_policy_snapshot_governance.py` | Covered |
| FR-GOV-004 | Snapshot Write and Validate | `test_policy_snapshot_governance.py` | Covered |
| FR-GOV-005 | Version Governance | `test_policy_version_governance.py` | Covered |
| FR-GOV-006 | Version Governance JSON Mode | `test_policy_version_governance.py` | Covered |
| FR-GOV-007 | Universal Exit-Code Convention | `test_resolve_cli_governance.py` | Covered |
| FR-GOV-008 | Smoke Test Coverage | `test_smoke.py` | Covered |
| FR-SCHEMA-001 | Policy Contract Schema | `test_policy_contract.py` | Covered |
| FR-SCHEMA-002 | Wrapper Schema | `test_platform_wrappers.py` | Covered |

---

## Coverage Gaps

### Missing Test Coverage
1. `policy_diff.py` - unit tests exist (`unit/test_policy_diff.py`, 13 tests) but lack coverage of edge cases (empty inputs, identical policies)
2. `gap_detector.py` - only 4 tests; missing tests for empty audit logs, malformed events
3. `headless_review.py` - only 3 tests; missing tests for markdown JSON extraction, reviewer unavailability
4. `learner.py` - 8 tests; missing tests for suggestion writing to disk

### Partial Coverage
1. `cli.py` - `_print_diff_with_color` has tests via integration (`test_cli_diff_*`) but no dedicated unit test
2. `config_loader.py` - extensive tests (25) but no tests for `_load_yaml_file` error handling paths

---

## Recommendations

### Immediate Actions
1. Add unit tests for `gap_detector.py` error handling (empty events, parse failures)
2. Add unit tests for `headless_review.py` JSON extraction edge cases
3. Add dedicated unit test for `_print_diff_with_color`

### Short-term Actions
1. Run `pytest --cov=cli/src/policy_federation --cov=resolve.py --cov=scripts --cov-report=term-missing` to get line-level coverage
2. Target 80% line coverage across all policy_federation modules
3. Add integration tests for the `resolve --emit-host-rules` pipeline
