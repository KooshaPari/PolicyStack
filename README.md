# Policy scope stack for multi-harness AgentOps

This folder contains a concrete policy scope model:

- `system` → global hard constraints
- `user` → operator-level constraints
- `repo` → repository contract baseline
- `harness` → Codex/Cursor-agent/Claude/Factory-Droid
- `task_domain` → domain-specific safety/runtime checks
- `task_instance` → one-off request override

Run:

```bash
python policy-contract/resolve.py \
  --root . \
  --harness codex \
  --task-domain deployment \
  --emit /tmp/effective-policy.json
```

Validate policy scope files against the canonical contract schema:

```bash
python policy-contract/scripts/validate_policy_contract.py \
  --root policy-contract
```

### Policy discovery precedence

Policy discovery uses deterministic precedence and ordering:

- extension precedence for same stem: `.yaml` > `.yml` > `.json`
- default scope resolution order: `system`, `user`, `repo`
- discovery scope directory order: `harness`, `task-domain`, `task-instance`
- within each discovery scope directory, files are deduped by stem using extension precedence

### Governance Validation

From the canonical repo root (`CodeProjects/Phenotype/repos/policy-contract`):

Governance pytest matrix:

| Module | Command |
| --- | --- |
| `tests/test_resolve_cli_governance.py` | `uv run --with pytest --with pyyaml --with jsonschema pytest tests/test_resolve_cli_governance.py -q` |
| `tests/test_policy_common.py` | `uv run --with pytest --with pyyaml pytest tests/test_policy_common.py -q` |
| `tests/test_smoke_dispatch_host_hook.py` | `uv run --with pytest --with pyyaml pytest tests/test_smoke_dispatch_host_hook.py -q` |

```bash
uv run --with pyyaml --with jsonschema python scripts/validate_policy_contract.py --root .
uv run --with pyyaml python scripts/check_policy_versions.py --root .
uv run --with pytest --with pyyaml --with jsonschema pytest tests/test_policy_contract.py -k TestPolicyContractSchemaGovernance -q
uv run --with pytest --with pyyaml --with jsonschema pytest tests/test_resolve_cli_governance.py -q
uv run --with pytest --with pyyaml pytest tests/test_policy_common.py -q
uv run --with pytest --with pyyaml pytest tests/test_smoke_dispatch_host_hook.py -q
uv run --with pytest --with pyyaml pytest tests/test_policy_version_governance.py -q
uv run --with pytest --with pyyaml pytest tests/test_policy_snapshot_governance.py -q
```

Canonical snapshot drift check (`--check-existing`) for canonical pair(s):

```bash
for pair in "codex:deployment" "codex:query"; do
  harness="${pair%%:*}"
  task_domain="${pair##*:}"
  uv run --with pyyaml python scripts/generate_policy_snapshot.py \
    --root . \
    --harness "${harness}" \
    --task-domain "${task_domain}" \
    --output "policy-config/snapshots/policy_snapshot_${harness}_${task_domain}.json" \
    --check-existing
done
```

Canonical snapshot update and validation commands:

```bash
# update committed canonical snapshots (default: policy-config/snapshots)
uv run --with pyyaml python scripts/generate_policy_snapshot.py \
  --root . \
  --write-canonical

# validate committed canonical snapshots exist and match current resolution
uv run --with pyyaml python scripts/generate_policy_snapshot.py \
  --root . \
  --validate-canonical

# optional custom canonical directory for update/validate
uv run --with pyyaml python scripts/generate_policy_snapshot.py \
  --root . \
  --validate-canonical \
  --canonical-dir /tmp/custom-policy-snapshots
```

Host-hook smoke check:

```bash
bash scripts/smoke_dispatch_host_hook.sh
```

### Governance script JSON and exit-code conventions

Governance tooling now follows consistent machine-facing behavior:

- `0` exit code means validation/checks passed.
- non-zero exit code means at least one governance failure or invalid invocation.
- when JSON mode is enabled, scripts emit JSON error/success payloads suitable for CI parsing.

Examples (commands + representative success JSON payloads):

```bash
# JSON validation output for contract/schema checks
uv run --with pyyaml --with jsonschema python scripts/validate_policy_contract.py --root . --json
```

```json
{"type":"status","code":"ok","message":"validation passed"}
{"type":"summary","checked":7,"missing":0,"invalid":0}
```

```bash
# JSON policy-version governance output
uv run --with pyyaml python scripts/check_policy_versions.py --root . --json
```

```json
{"code":"ok","message":"policy version governance passed","details":{"allowed_versions":["v1"],"missing_required":[],"observed_versions":["v1"],"summary":{"checked":7,"missing_required":0,"invalid_versions":0}}}
```

```bash
# JSON snapshot drift check output
uv run --with pyyaml python scripts/generate_policy_snapshot.py \
  --root . \
  --harness codex \
  --task-domain deployment \
  --output policy-config/snapshots/policy_snapshot_codex_deployment.json \
  --check-existing \
  --json \
```

```json
{"status":"ok","kind":"check","message":"snapshot matches","output":"policy-config/snapshots/policy_snapshot_codex_deployment.json","policy_hash":"<sha256>"}
```

```bash
# JSON host-rule sync output from resolved policy
uv run --with pyyaml python resolve.py \
  --root . \
  --harness codex \
  --task-domain deployment \
  --emit /tmp/effective-policy.json \
  --emit-host-rules \
  --host-out-dir /tmp/policy-host \
  --include-conditional
uv run --with pyyaml python scripts/sync_host_rules.py \
  --policy-json /tmp/effective-policy.json \
  --out-dir /tmp/policy-host-sync \
  --include-conditional \
  --json
```

```json
{"ok":true,"mode":"emit","platforms":[{"platform":"codex","unconditional_rules":4,"conditional_rules":1,"written_to":"/tmp/policy-host-sync"}],"summary":{"unconditional_rules":4,"conditional_rules":1,"total_rules":5}}
```

In CI, treat non-zero as authoritative failure and parse JSON output (when requested)
for structured diagnostics.

One-shot host sync (resolve + emit host snippets):

```bash
python policy-contract/resolve.py \
  --root . \
  --harness codex \
  --task-domain deployment \
  --emit /tmp/effective-policy.json \
  --emit-host-rules \
  --host-out-dir /tmp/host-policy-fragments \
  --include-conditional
```

Apply directly into live host configs (default locations):

```bash
python policy-contract/resolve.py \
  --root . \
  --harness codex \
  --task-domain deployment \
  --emit /tmp/effective-policy.json \
  --emit-host-rules \
  --apply-host-rules \
  --include-conditional
```

If using a one-off task-instance override file:

```bash
python policy-contract/resolve.py \
  --root . \
  --harness codex \
  --task-domain deployment \
  --task-instance policy-contract/policy-config/task-instance/sample.yaml \
  --emit /tmp/effective-policy.json
```

Resolved output contains:

- `policy_hash` for audit trail
- `scopes` chain used
- final `policy`

### New: conditional `command_rules`

The contract now supports rule-level authorization with optional conditions:

```yaml
command_rules:
  - id: git_checkout_safe_sync
    action: allow
    match: "git checkout*"
    on_mismatch: request
    conditions:
      all:
        - git_is_worktree
        - name: git_clean_worktree
          required: true
        - name: git_synced_to_upstream
          required: true
```

This example allows checkout only when all 3 git conditions hold, and otherwise
emits a `request` decision.

`required` is optional and defaults to `true`.

### Multi-condition git predicates (authoritative examples)

Use nested `all` / `any` groups to model safety checks:

```yaml
command_rules:
  - id: git_checkout_requires_workspace_and_optional_sync
    action: allow
    match: "git checkout*"
    on_mismatch: request
    conditions:
      all:
        - name: git_is_worktree
          required: true
        - name: git_clean_worktree
          required: true
        - any:
            - name: git_synced_to_upstream
              required: true
            - name: git_clean_worktree
              required: false
```

```yaml
command_rules:
  - id: git_push_warn_if_dirty
    action: allow
    match: "git push*"
    on_mismatch: request
    conditions:
      all:
        - name: git_is_worktree
        - any:
            - name: git_clean_worktree
              required: false
            - name: git_synced_to_upstream
              required: false
```

In the second case, when both `git_clean_worktree` and `git_synced_to_upstream`
are optional and both fail, the nested `any` group returns failure and `on_mismatch`
is triggered.

Notes on request-capability across hosts:

- Codex and Claude support explicit request/deny/allow host artifacts directly.
- Cursor currently has no request slot in managed fragments; request actions are emitted as `deny` for static host fragments and require wrapper dispatch for richer semantics.
- Factory-Droid now receives explicit request entries:
  - `commandAllowlist` (allow)
  - `commandRequestlist` (request)
  - `commandDenylist` (deny)
- Go/Rust/Zig wrapper evaluators process `allow`, `request`, and `deny` directly from
  `policy_wrapper` bundles.

### Syncing to host policy files

After resolving policy, generate host-specific artifacts:

```bash
python policy-contract/scripts/sync_host_rules.py \
  --policy-json /tmp/effective-policy.json \
  --out-dir /tmp/host-policy-fragments
```

Apply directly to live host files from a resolved payload:

```bash
python policy-contract/scripts/sync_host_rules.py \
  --policy-json /tmp/effective-policy.json \
  --apply
```

Generated files:

- `codex.rules` → Codex `prefix_rule(...)` entries
- `cursor.cli-config.json` → Cursor allow/deny shell rules
- `claude.settings.json` → Claude allow/deny/ask shell rules
- `factory-droid.settings.json` → factory-droid allow/request/deny command lists
- `policy-wrapper-rules.json` → machine schema for conditional rule evaluators (go/zig/rust)
- `policy-wrapper-dispatch.manifest.json` → canonical runtime wiring for host hooks

The renderer writes only unconditional rules into host fragments.
Rules with conditions are routed into:

- `conditional_rules`: compact audit list of unresolved conditional entries
- `policy_wrapper` inside `host_rules`: full wrapper payload with schema version, condition
  mode, and normalized command patterns

This wrapper payload is intended for your non-Python policy evaluators to make final
runtime decisions.

For host wrappers (Go/Zig/Rust/etc.), consume:

- `policy_wrapper` from the `host_rules` payload in resolver/sync output
- `policy-wrapper-rules.json` from the generated out-dir artifacts
- `agent-scope/policy_wrapper.schema.json` for machine validation of the wrapper payload
- `agent-scope/policy_contract.schema.json` for machine validation of policy scope YAML/JSON

### Canonical host dispatch flow

1. Resolve policy and emit host artifacts (including conditional payload):

```bash
python policy-contract/resolve.py \
  --root . \
  --harness codex \
  --task-domain deployment \
  --emit /tmp/effective-policy.json \
  --emit-host-rules \
  --host-out-dir /tmp/policy-host \
  --include-conditional
```

2. Use the generated manifest in the hook layer:

```json
// /tmp/policy-host/policy-wrapper-dispatch.manifest.json
{
  "schema_version": 1,
  "bundle_path": "/tmp/policy-host/policy-wrapper-rules.json",
  "dispatch_script": "/path/to/policy-contract/wrappers/policy-wrapper-dispatch.sh",
  "dispatch_command": [
    "/path/to/policy-contract/wrappers/policy-wrapper-dispatch.sh",
    "--json",
    "--bundle",
    "/tmp/policy-host/policy-wrapper-rules.json",
    "--command",
    "{command}",
    "--cwd",
    "{cwd}"
  ],
  "required_conditions": ["git_clean_worktree", "git_is_worktree", "git_synced_to_upstream"],
  "wrapper_rule_count": 4,
  "missing_policy_default": "allow"
}
```

Host behavior:

- Call `dispatch_script` only for commands in the wrapper candidate set.
- On `allow`, proceed.
- On `request`, surface user confirmation.
- On `deny`, block execution.
- For hosts without native request plumbing in their direct config consumers, request-capable behavior is only guaranteed through wrapper dispatch.

This contract is the canonical shape for cross-language wrappers:

```json
{
  "schema_version": 1,
  "required_conditions": ["git_clean_worktree", "..."],
  "commands": [
    {
      "id": "git_checkout_safe_sync",
      "source": "repo.yaml",
      "action": "allow",
      "on_mismatch": "request",
      "matcher": "prefix",
      "pattern": "git checkout",
      "normalized_pattern": "git checkout",
      "conditions": {
        "mode": "all",
        "conditions": [
          {"name": "git_is_worktree", "required": true},
          {"name": "git_clean_worktree", "required": true},
          {"name": "git_synced_to_upstream", "required": true}
        ]
      },
      "platform_action": "allow",
      "shell_entry": "Shell(git checkout *)",
      "bash_entry": "Bash(git checkout *)"
    }
  ]
}
```

Reference evaluators:

- `wrappers/go` (runnable Go implementation)
- `wrappers/rust` (runnable Rust implementation)
- `wrappers/zig` (runnable Zig implementation)

/// @trace PS-001

/// @trace PS-001
