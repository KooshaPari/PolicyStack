# Dispatch Host-Hook Smoke Test Specification

## Objective

Create a minimal smoke test that proves host-side dispatch behavior for one
conditionally allowed command and one conditionally blocked command.

## Scope

- Script: `wrappers/policy-wrapper-dispatch.sh`
- Inputs:
  - `policy-wrapper-rules.json`
  - `policy-wrapper-dispatch.manifest.json` (from `sync_host_rules.py`)
  - Temporary `PATH` with no git binary (for negative condition behavior)

## Positive path

1. Use a bundle with a single command rule:
   - `action: allow`
   - `conditions: { all: ["git_is_worktree"] }`
   - `pattern`: command that is expected to be evaluated.
2. Run dispatch with `--json` and command string.
3. Assert:
   - `decision` is `allow`
   - `matched` is `true`
   - `condition_passed` is `true`
   - `rule_id` matches the allow rule id.

## Blocked path

1. Reuse a similar bundle shape with a single rule:
   - `action: deny` (or `request`) with `conditions: { all: ["git_is_worktree"] }`
2. Execute with an environment that makes condition fail (`PATH` without valid `git` for
   `git_is_worktree`).
3. Assert:
   - `decision` is `deny` for `action: deny`, or `request` for `action: request`
   - `matched` is `true`
   - `condition_passed` is `false`
   - `error` is non-empty when condition evaluation fails.

## Success criteria

- Smoke test covers both evaluation outcomes in one loop.
- Script exit code follows current transport contract:
  - `0` => allow
  - `1` => request
  - `2` => deny
- Both outcomes preserve deterministic JSON schema emitted by `policy-wrapper-dispatch.sh`.

## Implementation note

- Keep this as a dedicated host-hook smoke test artifact under
  `docs/sessions/2026-03-03-policy-wrapper-standardization/`.
- Prefer executing it as a script-adjacent local test (`bash` + `jq`) before any host rollout.
