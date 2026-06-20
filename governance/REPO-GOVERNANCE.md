# Repository Governance — PolicyStack

**Last updated:** 2026-06-19
**Owner:** @kooshapari
**Substrate tier:** `policy-stack` (Python-native policy-as-code framework)
**Repository:** PolicyStack

---

## Purpose

PolicyStack is the canonical **policy-as-code framework** for the Phenotype organization, providing unified, declarative policy definition, evaluation, and enforcement across infrastructure, applications, and operations.

## Scope

This governance covers all artifacts within this repository:

- Core framework (`policy_lib.py`, `resolve.py`, `cli/`)
- Policy definitions (`policies/`, `policy-config/`)
- Test suite (`tests/`)
- CI/CD workflows (`.github/workflows/`)
- Governance artifacts (this directory, `AGENTS.md`, `CLAUDE.md`, etc.)
- Language wrappers (`wrappers/`)
- Documentation (`docs/`, `SPEC.md`, `ARCHITECTURE.md`)

## Policies

### 1. Conventional commits

All commits MUST follow [Conventional Commits](https://www.conventionalcommits.org/):

| Scope             | Prefix       | Example                                                   |
|-------------------|--------------|-----------------------------------------------------------|
| Core engine       | `feat(core)` | `feat(core): add multi-condition predicate evaluation`    |
| CLI               | `feat(cli)`  | `feat(cli): add --format json output`                    |
| Policy definition | `feat(policy)` | `feat(policy): add network-egress rule`                |
| Wrapper           | `feat(wrap)` | `feat(wrap): add rust ffi bindings`                      |
| Bug fix           | `fix`        | `fix: correct false-negative on nested conditionals`      |
| Governance        | `chore`      | `chore(tier-0): add governance/ and justfile`            |
| Docs              | `docs`       | `docs: update SPEC.md with evaluation semantics`         |
| CI/CD             | `ci`         | `ci: add cargo-deny step to workflow`                    |

### 2. Branch naming

| Purpose                  | Pattern                       |
|--------------------------|-------------------------------|
| Governance/hygiene       | `chore/tier-0-*`             |
| New feature              | `feat/<feature-name>`        |
| Bug fix                  | `fix/<bug-description>`      |
| Documentation            | `docs/<topic>`               |
| CI/CD changes            | `ci/<change-description>`    |

### 3. Review requirements

- All changes must go through a pull request (no direct pushes to `main`).
- Governance files (`AGENTS.md`, `governance/`, `deny.toml`, `justfile`, `CODEOWNERS`) require owner approval.
- CI must pass before merge.
- Policy-contract changes require governance workflow validation.

### 4. Quality gates

- **Lint:** ruff (zero errors) — syntax, import, and style checks
- **Format:** ruff format (zero diffs)
- **Test:** pytest (all tests green)
- **Security:** gitleaks secret scan, pip-audit dependency scan
- **Governance:** `validate_governance.py` (all checks pass)
- **Type check:** pyright (strict mode)

### 5. Versioning

This project follows [Semantic Versioning 2.0.0](https://semver.org/):

- **Patch** (`0.1.x`): Bug fixes, documentation, CI changes
- **Minor** (`0.x.0`): New features, non-breaking API changes
- **Major** (`x.0.0`): Breaking changes to API or CLI interface

### 6. Dependencies

- **Python:** Managed via `uv`. Third-party dependencies in `pyproject.toml`.
- **Rust:** Managed via `cargo`. Limited to wrapper crate in `wrappers/rust/`.
- **Node:** Managed via `npm`. Limited to documentation build tooling.
- All dependency changes require `cargo deny` / `pip-audit` validation.

## Related documents

- `CHARTER.md` — project charter, mission, and tenets
- `ARCHITECTURE.md` — system architecture description
- `SPEC.md` — technical specification
- `AGENTS.md` — AI agent context and operating procedures
- `CLAUDE.md` — Claude Code project instructions
- `CONTRIBUTING.md` — contributor guide
- `CODE_OF_CONDUCT.md` — code of conduct
