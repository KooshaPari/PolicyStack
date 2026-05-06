# SPECS_INDEX — PolicyStack

**Version**: 1.0
**Last Updated**: 2026-05-05
**Status**: Active

This file indexes all formal specifications in the PolicyStack repository.

---

## Specification Index

### Core Specifications

| Spec | File | Status | Version |
|------|------|--------|---------|
| Feature Requirements | `FUNCTIONAL_REQUIREMENTS.md` | Active | 1.0 (2026-03-26) |
| System Specification | `SPEC.md` | Active | 1.0 (2026-04-03) |
| Architecture | `ARCHITECTURE.md` | Active | — |
| Product Requirements | `PRD.md` | Active | — |

### Governance Specifications

| Spec | File | Status |
|------|------|--------|
| Architecture Decision Records | `ADR.md` | Active (all Accepted) |
| Charter | `CHARTER.md` | Active |
| Governance | `GOVERNANCE.md` | Active |
| Security Policy | `SECURITY.md` | Active |

### Contract Schemas

| Spec | File | Status |
|------|------|--------|
| Policy Contract Schema | `contracts/session-sidecar.schema.json` | Active |
| Agent Scope Schema | `agent-scope/schema.json` | Active |
| Agent Policy Contract Schema | `agent-scope/policy_contract.schema.json` | Active |
| Agent Policy Wrapper Schema | `agent-scope/policy_wrapper.schema.json` | Active |

### Reference Documents

| Spec | File | Status |
|------|------|--------|
| Functional Requirements | `FUNCTIONAL_REQUIREMENTS.md` | Active |
| Migration Guide (Federation) | `MIGRATION_FROM_FEDERATION.md` | Active |
| User Journeys | `USER_JOURNEYS.md` | Active |
| Platform Comparison | `COMPARISON.md` | Active |

### Local Spec Extensions

| Spec | File | Status | Notes |
|------|------|--------|-------|
| Local Extensions | `specs/README.md` | Active | Links to `AgilePlus/specs/` |

---

## Coverage

- **FR-RES** (Policy Resolution): 8 specs — All implemented
- **FR-COND** (Conditional Rules): 7 specs — All implemented
- **FR-HOST** (Host Rule Sync): 6 specs — All implemented
- **FR-GOV** (Governance Validation): 8 specs — All implemented
- **FR-SCHEMA** (Schema Artifacts): 2 specs — All implemented

Total: **31 functional requirements** — all marked as Active/Implemented.

---

## Open Issues

- `AgilePlus/specs/` link in `specs/README.md` requires `AgilePlus` sibling repo to be present
- `SPEC.md` section 10 (Detailed API Reference) may be incomplete — verify all API endpoints documented
- `ARCHITECTURE.md` should be cross-referenced against current `cli/src/policy_federation/` layout

---

## How to Use This Index

1. Start with `FUNCTIONAL_REQUIREMENTS.md` for what must be implemented
2. Cross-reference with `SPEC.md` for detailed design
3. Check `ADR.md` for why design decisions were made
4. Validate implementation against `FUNCTIONAL_REQUIREMENTS.md` using `validate_governance.py`
5. Update this index when adding new spec files
