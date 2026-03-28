# Testing Strategy

## Dispatch Host-Hook Smoke Test Specification

### Objective

Create a minimal smoke test that proves host-side dispatch behavior for one conditionally allowed command and one conditionally blocked command.

### Scope

- Script: `wrappers/policy-wrapper-dispatch.sh`
- Inputs:
  - `policy-wrapper-rules.json`
  - `policy-wrapper-dispatch.manifest.json` from `sync_host_rules.py`
  - Temporary clean and dirty git repositories for deterministic condition evaluation

### Partial comment scan behavior note

- In this smoke/spec context, comment checks are expected to be tolerant of partial command failures when API endpoints return incomplete comment payloads.
- The lane4 audit still treats any comment scan error as a hard block (`exit code 2`) in read-only mode so operators can triage before merge when policy context is uncertain.

### Positive path

1. Use a bundle with a single command rule.
   - `action: allow`
   - `conditions: { all: ["git_clean_worktree"] }`
   - `pattern`: command expected to be evaluated.
2. Run dispatch with `--json` and the command string.
3. Assert:
   - `decision` is `allow`
   - `matched` is `true`
   - `condition_passed` is `true`
   - `rule_id` matches the allow rule id.

### Blocked path

1. Reuse a similar bundle shape with a single rule.
   - `action: allow`
   - `on_mismatch: deny`
   - `conditions: { all: ["git_clean_worktree"] }`
2. Execute with a dirty git worktree so condition evaluation succeeds but returns false.
3. Assert:
   - `decision` is `deny`
   - `matched` is `true`
   - `condition_passed` is `false`
   - condition evaluation remains deterministic without relying on wrapper fallback defaults.

### Success criteria

- Smoke test covers both evaluation outcomes in one loop.
- Script exit code follows current transport contract:
  - `0` => allow
  - `1` => request
  - `2` => deny
- Both outcomes preserve deterministic JSON schema emitted by `policy-wrapper-dispatch.sh`.

### Implementation note

- Keep this as a dedicated host-hook smoke test artifact under `docs/sessions/2026-03-03-policy-wrapper-standardization/`.
- Prefer executing it as a script-adjacent local test (`bash` + `jq`) before any host rollout.

### Execution status (resumed lane-4 pass)

- The smoke contract is now implemented in `scripts/smoke_dispatch_host_hook.sh`.
- Tests in `tests/test_smoke_dispatch_host_hook.py` validate both allow and blocked dispatch paths using deterministic mocked wrapper output.
- Workflow-stage audit integration now emits a lane4 `::error::` annotation for `comment_scan_errors`, and failure strings in `.github/workflows/policy-contract-governance.yml` now cross-link back to session docs.
