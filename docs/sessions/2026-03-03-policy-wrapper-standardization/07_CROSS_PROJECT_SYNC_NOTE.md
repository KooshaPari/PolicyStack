# Cross-Project Sync Note: Standardized Wrapper Authorization Model

## Purpose

Disseminate the policy-wrapper split architecture so Cursor/Claude/Codex/Droid/host
surfaces can share the same conditional gate behavior while preserving existing
static command contracts.

## Standardized model to sync

- Static host-side rules remain authoritative for unconditional command allow/deny/request
  and are exported per platform as today.
- Conditional logic remains centralized in `policy-wrapper-*` binaries through
  `policy-wrapper-rules.json`.
- Host hooks call `wrappers/policy-wrapper-dispatch.sh` for commands that survive
  the static surface.
- Fallback behavior is explicit via manifest fields:
  - `fallback_missing_policy`
  - `fallback_malformed_bundle`
  - `fallback_condition_eval_error`

## Candidate targets for adoption

1. `thegent`
   - Existing multi-platform wrapper consumers and host adapter integration points.
2. `cliproxyapi++`
   - Already maintaining command-policy surfaces with similar hook constraints.
3. `portage`
   - Runtime-heavy CLI host interactions; deterministic fallback and hard-fail modes
     reduce silent-policy regressions.
4. `heliosCLI`
   - Developer-tool surfaces with frequent local execution paths benefit from
     standardized host hook behavior.
5. `tokenledger` and `trash-cli`
   - Follows quickly if policy surfaces are already host-export based.

## Rollout sequence

1. Share `wrappers/README.md` command contract and fallback semantics.
2. Share `policy-wrapper-dispatch.sh` behavior and manifest keys in the target repo
   issue/template.
3. Run dispatch smoke test spec before any host rule changes:
   - one positive command decision
   - one blocked command decision
4. Enable include-conditional host exports in sync tooling after parity checks.
5. Add child-agent follow-up WBS lane in each repo for host-adapter closure.

## Governance note

Use the same cross-repo coordination pattern used in this session:
- one standardized child-agent delegation model for discovery + execution
- lane-level WBS status ledger with explicit acceptance gates
- manifest-backed fallback rationale for every host integration decision.
