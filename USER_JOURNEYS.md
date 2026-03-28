# User Journeys -- policy-contract

**Version:** 1.0
**Last Updated:** 2026-03-27

Traces to: `PRD.md` epics. Each journey maps to FR categories in `FUNCTIONAL_REQUIREMENTS.md`.

---

## UJ-1: CI Pipeline Resolves Effective Policy

**Actor:** CI/CD pipeline (automated agent)
**Goal:** Produce a stable, auditable JSON policy artifact before running agent tasks.

```
CI Pipeline
     |
     v
[1] Run resolve.py
    --root <repo-root>
    --harness codex
    --task-domain build
    --emit /tmp/effective-policy.json
     |
     v
[2] resolver scans policy-config/
    system/ -> user/ -> repo/ -> harness/codex/ -> task-domain/build/
     |
     v
[3] Merges scopes in order;
    later scope overrides earlier on key collision;
    command_rules appended + deduped by id
     |
     v
[4] Emits JSON with:
    policy_hash (SHA-256)
    scopes (list of contributing files)
    policy (merged object)
     |
     v
[5] CI stores artifact;
    downstream tasks read policy
```

**Traces to:** FR-RES-001, FR-RES-003, FR-RES-004, FR-RES-005, FR-CLI-001

---

## UJ-2: Repository Owner Adds a Conditional Git Rule

**Actor:** Repository owner
**Goal:** Block `git checkout` on non-worktree branches unless the workspace is clean.

```
Repo Owner
     |
     v
[1] Edit policy-config/repo/repo.yaml
    Add command rule with id=policy_checkout_guard
    action: allow
    match: "git checkout*"
    on_mismatch: request
    conditions:
      all:
        - name: git_is_worktree
        - name: git_clean_worktree
     |
     v
[2] Run validate_policy_contract.py --root .
    Validates repo.yaml against agent-scope/policy_contract.schema.json
     |
     v
[3] Validation passes (exit 0)
     |
     v
[4] Run resolve.py; inspect policy_wrapper block
    Confirms checkout rule appears in wrapper bundle
     |
     v
[5] Run sync_host_rules.py --policy-json effective.json
    Conditional rule goes to policy-wrapper-rules.json
    (not to host-specific allow/deny fragments)
     |
     v
[6] Go/Rust/Zig wrapper evaluator consumes
    policy-wrapper-rules.json at runtime
```

**Traces to:** FR-CND-001, FR-CND-002, FR-CND-003, FR-VAL-001, FR-HST-001, FR-WRP-001

---

## UJ-3: Harness Integrator Applies Host Rules

**Actor:** Harness integrator (Cursor, Claude, Codex, or Factory-Droid)
**Goal:** Apply machine-generated host artifacts without manual configuration.

```
Harness Integrator
     |
     v
[1] Run sync_host_rules.py
    --policy-json /path/to/effective-policy.json
    --out-dir /tmp/host-rules/
    --apply
     |
     v
[2] Script generates per-host artifacts:
    codex.rules -> Codex prefix_rule() entries
    cursor.cli-config.json -> Cursor allow/deny shell rules
    claude.settings.json -> Claude allow/deny/ask rules
    factory-droid.settings.json -> FD allow/request/deny lists
    policy-wrapper-rules.json -> conditional evaluator payload
    policy-wrapper-dispatch.manifest.json -> runtime wiring
     |
     v
[3] --apply writes artifacts to live config paths
     |
     v
[4] Each harness reads its own artifact;
    unconditional rules enforced natively;
    conditional rules routed to wrapper evaluator
```

**Traces to:** FR-HST-001, FR-HST-002, FR-HST-003, FR-WRP-001, FR-WRP-002

---

## UJ-4: Governance Enforcer Detects Snapshot Drift

**Actor:** CI governance job
**Goal:** Catch unintended policy changes before merge.

```
CI Governance Job
     |
     v
[1] Run generate_policy_snapshot.py
    --check-existing
     |
     v
[2] Script resolves current policy fresh
     |
     v
[3] Compares policy_hash against committed
    canonical snapshot file
     |
     v
[4a] Hashes match -> exit 0, no drift
     |
     v
[4b] Hashes differ -> exit non-zero
     Print mismatch: old_hash vs new_hash
     List differing keys
     |
     v
[5] CI fails; author must either:
    - Revert unintended change, OR
    - Run --write-canonical to update snapshot
```

**Traces to:** FR-SNP-001, FR-SNP-002, FR-SNP-003

---

## UJ-5: Policy Author Validates New Scope File

**Actor:** Policy author
**Goal:** Confirm a new policy file passes schema before committing.

```
Policy Author
     |
     v
[1] Create policy-config/harness/cursor/cursor.yaml
     |
     v
[2] Run validate_policy_contract.py
    --root .
    --json
     |
     v
[3a] Exit 0, JSON: { checked: N, missing: 0, invalid: 0 }
     File is valid, proceed with commit
     |
[3b] Exit non-zero, JSON: { invalid: 1, errors: [...] }
     Print specific schema violations
     Author fixes file and re-runs
```

**Traces to:** FR-VAL-001, FR-VAL-002, FR-VAL-003

---

## UJ-6: Cross-Language Evaluator Consumes Wrapper Bundle

**Actor:** Go/Rust/Zig wrapper evaluator (automated)
**Goal:** Make a runtime allow/deny/request decision for a shell command.

```
Wrapper Evaluator (Go/Rust/Zig)
     |
     v
[1] Reads policy-wrapper-dispatch.manifest.json
    Extracts: bundle_path, dispatch_command template,
    required_conditions list
     |
     v
[2] Evaluates required_conditions:
    git_is_worktree, git_clean_worktree,
    git_synced_to_upstream (as applicable)
     |
     v
[3] Reads policy-wrapper-rules.json
    Finds matching command entry for incoming command
     |
     v
[4a] Conditions met + action=allow -> returns "allow"
     |
[4b] Conditions not met + on_mismatch=request -> returns "request"
     Host surfaces confirmation prompt
     |
[4c] No match -> uses missing_policy_default
```

**Traces to:** FR-CND-002, FR-WRP-001, FR-WRP-002, FR-WRP-003
