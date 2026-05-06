# SPEC-001: Policy Resolution and Layering

**Version**: 1.0
**Status**: Active
**Created**: 2026-05-06
**Author**: PolicyStack Agent

## Overview

Policy resolution determines which policy rules apply to a given request by consulting a layered hierarchy of policy sources. The system resolves at runtime based on harness, repository, task domain, task instance, and task overlay parameters.

## Resolution Algorithm

1. **Layer collection**: Build ordered list of policy layers from `repo_root/policies/` using the resolver.
2. **Scope chain**: Each layer contributes rules with a scope tag (`global`, `harness`, `repo`, `domain`, `instance`, `overlay`).
3. **Merge strategy**: Layers are merged in order; later scopes override earlier ones for the same rule ID.
4. **Hash computation**: Resolved policy is hashed (`hash_policy_sources`) for audit and tamper-detection use.

## Layer Precedence (highest to lowest)

| Scope | Override Priority |
|-------|-----------------|
| overlay | 6 (highest) |
| instance | 5 |
| domain | 4 |
| repo | 3 |
| harness | 2 |
| global | 1 (lowest) |

## Implementation

- **CLI command**: `policyctl resolve --harness <h> --domain <d> [--repo <r>] [--instance <i>] [--overlay <o>]`
- **Manifest**: `policyctl manifest --harness <h> --domain <d> [--repo <r>] [--instance <i>] [--overlay <o>]`
- **Module**: `cli/src/policy_federation/resolver.py`
- **Supporting**: `resolver_layers.py`, `resolver_merge.py`, `resolver_extensions.py`

## Acceptance Criteria

- [ ] `resolve` returns JSON with `policy`, `policy_hash`, `scope_chain`
- [ ] `manifest` returns ordered list of layers with scope and path
- [ ] Layer ordering respects precedence table above
- [ ] Policy hash is deterministic for the same inputs
- [ ] Unknown scope keys produce an error, not silent ignore

## Traceability

- FR-RES-001, FR-RES-002, FR-RES-003
