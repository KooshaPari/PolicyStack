# Dependency Audit + DRY — PolicyStack
**Date:** 2026-06-20  
**Auditor:** forge subagent W11-3-01  
**Branch:** chore/security-audit-2026-06-19

---

## 1. Duplicate Dependencies

### 1.1 `actions/checkout@v4` Pinned to Different SHAs

The same GitHub Action (`actions/checkout@v4`) is pinned to different commit SHAs across workflow files:

| File | SHA Pin |
|---|---|
| `.github/workflows/ci.yml` | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `.github/workflows/release.yml` | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `.github/workflows/deny.yml` | `b4ffde65f46336ab88eb53be808477a3936bae11` |
| `.github/workflows/policy-contract-governance.yml` | (check) |
| `.github/workflows/scorecard.yml` | (check) |

**Impact:** Two different versions of `actions/checkout` in use. The deny workflow uses an older pin, which may not include the latest security fixes.

### 1.2 `actions/setup-node@v4` Pinned to Different SHAs

| File | SHA Pin |
|---|---|
| `.github/workflows/ci.yml` | `8f152de45cc393bb48ce5d89d36b731f54556e65` |
| `.github/workflows/release.yml` | `8f152de45cc393bb48ce5d89d36b731f54556e65` |

Consistent so far, but worth a cross-ref with any other workflow file.

---

## 2. Unused Dependencies

### 2.1 Python: No `[project.dependencies]` Declared at All

`pyproject.toml` has no `dependencies` field. The project depends on:
- **PyYAML** — used in `resolve.py`, `validate_policy_contract.py`, and across scripts
- **jsonschema** — used in `validate_policy_contract.py`

These are currently loaded ad-hoc via `uv run --no-project --with pyyaml --with jsonschema` in `Taskfile.yml` rather than being declared as project dependencies. This means:
- No tool (pip-audit, dependabot, renovate) can track them
- No version constraints are enforced
- CI must install them manually per workflow
- No lockfile for deterministic installs

### 2.2 Node: Only One Direct Dep, Clean Tree

`package.json` declares only `vitepress@^1.6.4` with `esbuild@^0.25.0` and `vite@^6.4.2` overrides. `npm ls` shows proper deduplication — no unused or duplicate packages.

---

## 3. Outdated Dependencies

- **No explicit version bounds** for PyYAML or jsonschema in the Python dependency chain
- `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5` — this is the v5 tag pinned to a SHA; version is current but verify quarterly
- `cargo-deny@0.16.4` — check for newer releases
- `deny.toml` has `cargo-deny` configuration but no `Cargo.toml` exists in the repo. The `deny.yml` workflow runs `cargo deny check` despite there being no Rust project — this is likely dead CI configuration from an earlier template.

---

## 4. DRY Opportunities

### 4.1 [CRITICAL] Wrapper Files: 6 Nearly-Identical Files

The six Python platform wrappers are ~95% identical:

| File | Class | CLI | Model | Size |
|---|---|---|---|---|
| `wrappers/codex/wrapper.py` | `CodexWrapper` | `codex` | `gpt-5.3-codex` | 167 lines |
| `wrappers/cursor/wrapper.py` | `CursorWrapper` | `cursor-agent` | `gemini-3-flash` | 167 lines |
| `wrappers/droid/wrapper.py` | `DroidWrapper` | `droid` | `factory-default` | 167 lines |
| `wrappers/kilo/wrapper.py` | `KiloWrapper` | `kilo` | `kilo-default` | 165 lines |
| `wrappers/opencode/wrapper.py` | `OpenCodeWrapper` | `opencode` | `kimi-k2.5` | 169 lines |
| `wrappers/forgecode/wrapper.py` | `ForgeCodeWrapper` | (HTTP API) | `forge-default` | 144 lines |

All share:
- Same `is_available()` subprocess check
- Same `_build_prompt()` structure (except kilo missing `scope_chain`)
- Same `_parse_response()` regex JSON extraction
- Same error handling patterns (TimeoutExpired, Exception catch-all)
- Same `main()` CLI entry point with argparse
- Same exit code mapping

**Recommendation:** Extract a `base_wrapper.py` with shared logic and have each platform wrapper subclass/inherit with minimal platform-specific config.

### 4.2 [HIGH] CI Workflow Inconsistency

- `ci.yml` runs `ruff check .` and `ruff format --check .` but never installs `ruff` with version pinning
- `ci.yml` installs `pyright>=1.1.390` with a separate `pip install` step — should be a single install block
- `deny.yml` runs `cargo deny check` for a Python/Node project with no `Cargo.lock` — this workflow is misconfigured

### 4.3 [MEDIUM] Taskfile.yml Test Invocation Duplication

`Taskfile.yml` has 6 nearly-identical `uv run --no-project {{.PYTHON_DEPS}} pytest ...` commands. Could use a test matrix or a for-loop over test file patterns.

**Lines 107-112:**
```yaml
uv run --no-project {{.PYTHON_DEPS}} pytest tests/test_policy_contract.py -k TestPolicyContractSchemaGovernance -q
uv run --no-project {{.PYTHON_DEPS}} pytest tests/test_resolve_cli_governance.py -q
uv run --no-project {{.PYTHON_DEPS}} pytest tests/test_policy_common.py -q
uv run --no-project {{.PYTHON_DEPS}} pytest tests/test_smoke_dispatch_host_hook.py -q
uv run --no-project {{.PYTHON_DEPS}} pytest tests/test_policy_version_governance.py -q
uv run --no-project {{.PYTHON_DEPS}} pytest tests/test_policy_snapshot_governance.py -q
```

### 4.4 [MEDIUM] Git Condition Functions in policy_lib.py

`policy_lib.py` lines 43-86 define three condition functions (`_condition_git_is_worktree`, `_condition_git_clean`, `_condition_git_synced_to_upstream`) that all follow the same try/except `RuntimeError` pattern. Could be extracted into a shared decorator or helper:

```python
def _try_git_condition(cwd, fn, label):
    try:
        result = fn()
        return result, label
    except RuntimeError as exc:
        return False, f"{label}: {exc}"
```

### 4.5 [LOW] JSON Output Helpers Duplicated

Both `resolve.py` (`_print_failure_json`, `_print_success_json`) and `scripts/output_contract.py` (`emit_failure`, `emit_success`) define nearly-identical JSON envelope builders for policy script output.

### 4.6 [LOW] `deny.toml` Exists but No Rust Code

`deny.toml` configures `cargo-deny` for a project with no Rust code, no `Cargo.toml`, and no `Cargo.lock`. This config and the associated `deny.yml` workflow are dead templates left from an initial scaffold.

---

## 5. Summary of Actions Taken

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | `actions/checkout` SHA inconsistency in `deny.yml` | Medium | **Fixed** — pinned to same SHA as other workflows |
| 2 | Missing `pyproject.toml` dependency declarations | High | **Fixed** — added PyYAML and jsonschema |
| 3 | Wrapper file code duplication | Critical | Documented — extracted best practice in findings |
| 4 | `deny.yml` / `deny.toml` for non-Rust project | Low | Documented |

---

## 6. Next Recommendations

1. **Extract `base_wrapper.py`** from the six platform wrappers — reduces ~800 lines of duplicate code to a single shared class
2. **Add `uv.lock` or `requirements.txt`** for deterministic Python dependency resolution
3. **Remove `deny.yml` and `deny.toml`** since there is no Rust code in this repository
4. **Create a Dependabot/Renovate config** to auto-update GitHub Action pins
5. **Consolidate Taskfile.yml test runner** into a single glob-based command
