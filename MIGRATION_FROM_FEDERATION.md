# PolicyStack Migration: agentops-policy-federation Features

**Status:** Migration Document - Ready for Implementation  
**Date:** 2026-04-02  
**Source:** agentops-policy-federation → PolicyStack  

---

## Overview

This document tracks the features from `agentops-policy-federation` that need to be merged into `PolicyStack` to complete the consolidation.

**Canonical Repository:** `PolicyStack` (camelCase)  
**Source Repository:** `agentops-policy-federation` (to be archived)  

---

## Features to Migrate

### 1. CLI Tools (High Priority)

| Tool | Source Path | Target Location | Description |
|------|-------------|-----------------|-------------|
| `federate_policy.py` | `tools/federate_policy.py` | `PolicyStack/tools/` | Cross-repo policy federation |
| `validate_policy_payload.py` | `tools/validate_policy_payload.py` | `PolicyStack/tools/` | Policy payload validation |
| `audit_policy_rotation.py` | `tools/audit_policy_rotation.py` | `PolicyStack/tools/` | Audit and rotation tracking |
| `build_pr_package.py` | `tools/build_pr_package.py` | `PolicyStack/tools/` | PR package building |

**Migration Notes:**
- Ensure compatibility with PolicyStack's existing `resolve.py` and `policy_lib.py`
- Integrate into PolicyStack's tool naming convention
- Update any relative imports to use PolicyStack structure

### 2. Wrapper System (High Priority)

| Component | Source Path | Target Location | Description |
|-----------|-------------|-----------------|-------------|
| `policy-wrapper-dispatch.sh` | `wrappers/policy-wrapper-dispatch.sh` | `PolicyStack/wrappers/` | Universal dispatcher |
| Go wrapper | `wrappers/go/` | `PolicyStack/wrappers/go/` | Go evaluator shim |
| Rust wrapper | `wrappers/rust/` | `PolicyStack/wrappers/rust/` | Rust evaluator shim |
| Zig wrapper | `wrappers/zig/` | `PolicyStack/wrappers/zig/` | Zig evaluator shim |

**Migration Notes:**
- Integrate with PolicyStack's `scripts/wrapper_dispatch_host_hook.py`
- Ensure consistent environment variable handling
- Document usage in PolicyStack README

### 3. Policyctl CLI (Medium Priority)

**Commands to Port:**

| Command | Description | Integration Target |
|---------|-------------|-------------------|
| `policyctl resolve` | Policy resolution | Merge into `resolve.py` |
| `policyctl evaluate` | Policy evaluation | New: `tools/evaluate.py` |
| `policyctl compile` | Policy compilation | New: `tools/compile.py` |
| `policyctl intercept` | Command interception | Integrate with wrappers |
| `policyctl verify` | Policy verification | New: `tools/verify.py` |

**Migration Notes:**
- PolicyStack already has strong resolution in `resolve.py` - enhance rather than replace
- Create unified CLI entry point: `policyctl` (could wrap existing PolicyStack tools)

### 4. Runtime Guards (Medium Priority)

| Guard | Purpose | Integration Approach |
|-------|---------|---------------------|
| Exec Guard | Command execution interception | Integrate with wrapper dispatch |
| Write Guard | File write protection | Add to PolicyStack validation |
| Network Guard | Network access control | Add to policy evaluation |

**Migration Notes:**
- These may already exist in PolicyStack's validation layer - verify before porting
- Runtime guards should integrate with PolicyStack's scope-based resolution

### 5. Testing Infrastructure (Low Priority)

| Test Category | Source Location | Target Location |
|---------------|-----------------|-----------------|
| Unit tests | `tests/unit/` | Merge into `PolicyStack/tests/` |
| Integration tests | `tests/` root | Merge into `PolicyStack/tests/integration/` |
| Fixtures | `tests/fixtures/` | Merge into `PolicyStack/tests/fixtures/` |

**Migration Notes:**
- Merge test cases that don't duplicate existing PolicyStack tests
- Ensure test fixtures are compatible

---

## Files Inventory

### Source Files (agentops-policy-federation)

```
agentops-policy-federation/
├── policy_lib.py              # May duplicate PolicyStack - compare
├── resolve.py                 # May duplicate PolicyStack - compare
├── tools/
│   ├── federate_policy.py     # MIGRATE
│   ├── validate_policy_payload.py  # MIGRATE
│   ├── audit_policy_rotation.py    # MIGRATE
│   └── build_pr_package.py    # MIGRATE
├── wrappers/
│   ├── policy-wrapper-dispatch.sh  # MIGRATE
│   ├── go/
│   ├── rust/
│   └── zig/
├── tests/
│   ├── unit/                  # SELECTIVE MIGRATION
│   └── fixtures/              # SELECTIVE MIGRATION
└── docs/                      # MERGE RELEVANT CONTENT
```

### Target Structure (PolicyStack)

```
PolicyStack/
├── resolve.py                 # Keep canonical
├── policy_lib.py              # Keep canonical
├── tools/                     # Add new tools here
│   ├── federate_policy.py     # NEW
│   ├── validate_policy_payload.py  # NEW
│   ├── audit_policy_rotation.py    # NEW
│   ├── build_pr_package.py    # NEW
│   ├── evaluate.py            # NEW (from policyctl)
│   ├── compile.py             # NEW (from policyctl)
│   └── verify.py              # NEW (from policyctl)
├── wrappers/                  # NEW DIRECTORY
│   ├── policy-wrapper-dispatch.sh  # MIGRATED
│   ├── go/                    # MIGRATED
│   ├── rust/                  # MIGRATED
│   └── zig/                   # MIGRATED
├── scripts/                   # Keep existing
└── tests/                     # Merge new tests
```

---

## Implementation Steps

### Phase 1: Tool Migration (Week 1)

1. **Copy and Adapt Tools**
   ```bash
   cp agentops-policy-federation/tools/*.py PolicyStack/tools/
   ```
   - Update imports to use PolicyStack modules
   - Ensure compatibility with PolicyStack's `resolve.py`

2. **Test Tools**
   - Run each tool against PolicyStack's test fixtures
   - Fix any incompatibilities

### Phase 2: Wrapper Migration (Week 1-2)

1. **Copy Wrapper Infrastructure**
   ```bash
   cp -r agentops-policy-federation/wrappers PolicyStack/
   ```

2. **Integrate with Existing Dispatch**
   - Review `scripts/wrapper_dispatch_host_hook.py`
   - Merge dispatcher logic if needed

3. **Test Wrappers**
   - Test each language wrapper
   - Verify environment variable handling

### Phase 3: CLI Consolidation (Week 2)

1. **Create Unified policyctl**
   - Create `PolicyStack/policyctl` entry point
   - Delegate to existing tools where possible
   - Add new commands for missing features

2. **Documentation**
   - Update PolicyStack README with new capabilities
   - Document migration from agentops-policy-federation

### Phase 4: Testing (Week 2-3)

1. **Merge Tests**
   - Run full PolicyStack test suite
   - Add federation-specific test cases

2. **Validation**
   - Verify no regression in existing PolicyStack functionality
   - Ensure new features work as expected

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Duplicate functionality | Low | Audit both codebases before merging |
| Import path changes | Low | Systematic find/replace with testing |
| Test incompatibilities | Medium | Run selective test migration |
| Documentation drift | Low | Update docs as part of migration |

---

## Post-Migration Checklist

- [ ] All tools migrated and tested
- [ ] Wrappers integrated and functional
- [ ] policyctl CLI unified
- [ ] Tests passing
- [ ] Documentation updated
- [ ] agentops-policy-federation README updated with redirect
- [ ] Archive agentops-policy-federation repository

---

## Related Documents

- `agentops-policy-federation/README.md` - Source repository
- `PolicyStack/README.md` - Target repository
- `DUPLICATION_AUDIT_2026-04-02.md` - Consolidation plan
- `MASTER_AUDIT_2026-04-02.md` - Master git state audit

---

*Migration ready for execution. Coordinate with heliosCLI and sharecli consolidations.*
