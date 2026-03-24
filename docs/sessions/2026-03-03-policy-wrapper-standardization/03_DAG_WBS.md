# Policy Wrapper Standardization WBS

## Current status legend
- [done]
- [in_progress]
- [blocked]
- [pending]

## Scope
Build a robust, cross-platform permissions library centered on `policy-contract` where
base host config handles static allow/deny/ask gates and wrapper binaries enforce
conditional logic (`on_mismatch`, required/optional conditions, nested condition groups).

## Initial work already completed
1. [done] Add parser-level validation for invalid `on_mismatch` actions.
2. [done] Add regression test `test_invalid_on_mismatch_rejected_during_parse`.
3. [done] Add regression test `test_rendered_wrapper_payload_conditional_split_counts`.
4. [done] Document conditional export behavior in `wrappers/README.md`.
5. [done] Align wrapper README examples with `--include-conditional` host-sync behavior.
6. [done] Rename `resolve.py` flag to `--include-conditional` and update docs examples.

## Dependency map (WBS)

### Lane 1: API & parser parity
1. [done] Validate parser-specified command matchers and `on_mismatch` combinations end-to-end.
2. [done] Add contract test to ensure conditional rendering does not mutate unconditional host rules.
3. [done] Add test fixture for mixed `any` group with required + optional entries including failures.
4. [done] Add schema-safe fixture output assertions for `required_conditions` ordering and dedupe.

### Lane 2: Resolve/sync control plane
5. [done] Add explicit usage error when `--host-out-dir` is used without `--emit-host-rules`.
6. [done] Add manifest sanity validation after `write_host_artifacts` (bundle presence + counts).
7. [done] Add CLI output field documenting `include_conditional` mode for machine parsing.
8. [done] Add regression test for include-conditional flow in `resolve.py` through a temporary effective policy JSON.

### Lane 3: Wrapper binary behavior parity
9. [done] Add golden tests for go/rust/zig wrapper outputs for one `allow` + one `request` conditional rule.
10. [done] Align `go` wrapper decision precedence with parser-exported `on_mismatch` ordering.
11. [done] Add coverage for empty condition groups in all three binaries.
12. [done] Add coverage for malformed condition payload rejection with explicit exit/status mapping.

### Lane 4: Dispatch/runtime integration
13. [done] Add optional `--binary` candidate health check in `policy-wrapper-dispatch.sh` before execution.
14. [done] Add explicit failure mode output for `--require-binary` with clearer stderr and exit code.
15. [done] Add request/deny fallback policy knobs in wrapper manifest generator and docs.
16. [done] Add host-hook integration smoke test spec for dispatch script with one positive and one blocked command.
17. [done] Extend smoke-script execution to validate allow + blocked transport outputs in one run.
18. [done] Add workflow-gated stacked-PR audit invocation using explicit lane4 exit codes.

### Lane 5: Host surface adapters
17. [done] Confirm Cursor/Claude/Codex/Droid payload parity for static + conditional command exports.
18. [done] Ensure conditional `request` does not regress static deny/ask channels in Cursor/Claude outputs.
19. [done] Add doc note for partial platform support with fallback-only behavior on non-wrapper hosts.
20. [done] Add checklist for host file apply order and merge-safe update behavior.

### Lane 6: Rollout, docs, and governance
21. [done] Create cross-project sync note for the proposed standardized child-agent wrapper model.
22. [done] Draft `docs/sessions/.../00_SESSION_OVERVIEW.md` and `03_DAG_WBS.md` index updates.
23. [done] Add `status` ledger with acceptance checkpoints and dependencies for each lane.
24. [done] Run final dependency verification pass and mark all lane dependencies green/blocked.

## E2E Phased Work Plan (Next Execution Window)

### Phase A — E2E Validation (in progress)
- [done] Run lane4 stack-audit + smoke tests locally with synthetic fixtures.
- [done] Verify allow/blocked dispatch contract assertions in `scripts/smoke_dispatch_host_hook.sh`.
- [done] Verify exit-code mapping for comment scan/remediation/failures.
- [done] Capture regression test for malformed dispatch output.

### Phase B — CI & Governance (next, by child agents)
- [done] Add CI-only matrix entry for `scripts/smoke_dispatch_host_hook.sh` (if not already enabled).
- [done] Add e2e workflow acceptance log artifact upload for audit JSON.
- [done] Add alert annotation for `comment_scan_errors` trend.
- [done] Add doc cross-link from `policy-contract-governance.yml` failure message to session spec.

### Phase C — Policy quality hardening (next)
- [done] Add explicit documentation for partial comment scan behavior in session artifacts.
- [done] Add remediation metrics (missing token counts by source) to audit JSON consumers.
- [done] Add deterministic fixture for mixed comment errors + partial data in `find_stacked_and_token_findings`.
- [done] Expand lane5 host parity matrix to full allow/request/deny permutations.
