# PolicyStack Oracle Specification (`policyctl` + `policy_federation` surface)

Status: draft  
Owner: spec/policystack-oracle

Scope: CLI command surface and package API under `cli/src/policy_federation/`.
Only source-backed behavior in `cli/src/policy_federation` and `cli/pyproject.toml` is covered.

## Functional Requirements

- **FR-1**: `policyctl resolve` SHALL output a resolved payload containing `policy_hash`, `scope_chain`, `policy`, `source_files`, and `resolved_at` for a given `--harness`/`--domain`.  
  - **Mapped to**: `cli.py:resolve_command` -> `resolver.py:resolve`; `resolver.py:_policy_layers`  
  - **TESTABLE**: Run `policyctl resolve` on a fixture repo and assert the JSON includes the listed keys and `policy_hash` is non-empty.

- **FR-2**: `policyctl manifest` SHALL list active policy layer scope names and source paths in merge order.  
  - **Mapped to**: `cli.py:manifest_command` and `resolver.py:_policy_layers`  
  - **TESTABLE**: Given layered policy files, run `policyctl manifest` and assert layers are present with deterministic order and expected source paths.

- **FR-3**: `policyctl check` SHALL validate one or all policy files using schema + authorization block validation.  
  - **Mapped to**: `cli.py:check_command`, `validate.py:validate_policy_file`  
  - **TESTABLE**: Run `policyctl check` against valid and invalid policy YAML files; valid set exits 0 and invalid set raises `SystemExit` with failure.

- **FR-4**: `policyctl evaluate` SHALL return the policy decision and a decision summary that includes `reason`, matched rules, and metadata for the request.  
  - **Mapped to**: `cli.py:evaluate_command`, `authorization.py:evaluate_authorization`  
  - **TESTABLE**: Given a rule that matches `action`/`command`, verify output decision equals the winning rule and includes `matched_rules`.

- **FR-5**: Authorization rule evaluation SHALL apply deterministic precedence: highest priority first, then stricter effect order (deny > ask > allow).  
  - **Mapped to**: `authorization.py:normalize_authorization_rules`, `authorization.py:evaluate_authorization`, `authorization.AuthorizationRule`  
  - **TESTABLE**: Provide two rules with same priority and different effects; assert effective decision follows deny over ask over allow.

- **FR-6**: `policyctl compile --target <supported>` SHALL produce target-specific `native_config`, canonical `defaults`, and `shim_rules` for non-native conditions/targets.  
  - **Mapped to**: `cli.py:compile_command`, `compiler.py:compile_target`, `compiler.SUPPORTED_TARGETS`  
  - **TESTABLE**: Compile a policy with conditional/runtime-only rules for each supported target and assert shim entries are generated as required.

- **FR-7**: Delegation shall attempt local-fast evaluation first, then cache lookup, then harness fallback chain, and return `allow|deny|ask` with confidence.  
  - **Mapped to**: `delegate.py:delegate_ask`, `delegate.py:_local_fast_evaluate`, `delegate.py:_get_cached_decision`, `delegate.py:_invoke_harness`, `delegate.HARNESS_FALLBACK`  
  - **TESTABLE**: Mock a local-fast allow path and a fallback path; assert returned `DelegateResult` contains expected `decision`, `source`, and `confidence`.

- **FR-8**: `policyctl intercept|write-check|network-check` and review modes SHALL map policy decisions to normalized exit behavior (`allow`/`deny`/`ask`) using `ALLOW_EXIT_CODE`, `DENY_EXIT_CODE`, `ASK_EXIT_CODE`.  
  - **Mapped to**: `interceptor.py:intercept_command`, `interceptor.py:ALLOW_EXIT_CODE`, `interceptor.py:DENY_EXIT_CODE`, `interceptor.py:ASK_EXIT_CODE`, `interceptor.py:_sources_hash`  
  - **TESTABLE**: Evaluate deny/allow/ask outcomes across modes and verify returned `exit_code` and `final_decision`.

- **FR-9**: `policyctl exec` SHALL verify policy integrity immediately before executing subprocess and deny execution on source hash change.  
  - **Mapped to**: `interceptor.py:run_guarded_subprocess`, `interceptor.py:intercept_command`, `resolver.py:hash_policy_sources`  
  - **TESTABLE**: Simulate `sources_hash` drift between pre-check and execution and verify subprocess is blocked with `DENY_EXIT_CODE`.

- **FR-10**: Audit workflows (`audit`, `verify`) shall support filtering by action/decision/time/actor and optional chain validation.  
  - **Mapped to**: `cli.py:audit_command`, `_parse_iso_datetime`, `_compute_audit_summary`, `runtime_artifacts.py:filter_audit_events`, `runtime_artifacts.py:verify_audit_chain`  
  - **TESTABLE**: Use a fixture audit log with mixed actions and decisions and assert filters and `verify_audit_chain` report expected counts/validity.

- **FR-11**: `policyctl add-rule` and `policyctl remove-rule` SHALL safely mutate policy YAML while enforcing duplicate/absence constraints.  
  - **Mapped to**: `cli.py:add_rule_command`, `cli.py:remove_rule_command`, `policy_editor.py:add_rule`, `policy_editor.py:remove_rule`  
  - **TESTABLE**: Add a unique rule then attempt duplicate add and non-existent remove; assert success and validation failures are represented in errors.

- **FR-12**: `policyctl diff` SHALL report added, removed, modified, and effect changes when comparing two policies.  
  - **Mapped to**: `cli.py:diff_command`, `policy_federation.policy_diff.diff_policies`  
  - **TESTABLE**: Compare two fixture policies with all four diff types and assert each output bucket is populated accordingly.

- **FR-13**: `policyctl verify` SHALL create `.policy-federation/verify` baseline on first run and fail with `tampered` if subsequent hash differs.  
  - **Mapped to**: `cli.py:verify_command`, `resolver.py:hash_policy_sources`  
  - **TESTABLE**: Run verify twice with unchanged files (status ok) and once after file touch (status tampered).

- **FR-14**: Runtime integration install/uninstall commands SHALL install/remove launcher wrappers and return structured before/after payloads.  
  - **Mapped to**: `cli.py:install_runtime_command`, `cli.py:uninstall_runtime_command`, `integrations.py:install_runtime_integrations`, `integrations.py:uninstall_runtime_integrations`  
  - **TESTABLE**: Invoke install then uninstall on temp HOME and assert payload includes wrapper and backup/restore metadata.

## Non-Functional Requirements

- **NFR-1**: JSON emission from CLI entrypoints SHALL be deterministic for the same inputs.  
  - **Mapped to**: `cli.py:_emit_json`, `resolve.py:resolve` ordering via `scope_chain`, `resolver.py:hash_policy_sources`  
  - **TESTABLE**: Run identical command twice against same fixtures and compare stable output JSON semantics including sorted keys.

- **NFR-2**: Delegation and API fallback paths SHALL bound runtime via explicit timeouts and fail-safe `ask` behavior on unresponsive or missing tools.  
  - **Mapped to**: `delegate.py:_invoke_harness`, `delegate.py:_invoke_api_harness`, `delegate.HARNESS_CONFIG`  
  - **TESTABLE**: Configure harness path/URL unavailable and assert returned result is `ask` and does not hang indefinitely.

- **NFR-3**: Audit event handling SHALL keep chain integrity checks non-crashing and report invalid entries with explicit invalid-event context.  
  - **Mapped to**: `runtime_artifacts.py:verify_audit_chain`, `runtime_artifacts.py:filter_audit_events`  
  - **TESTABLE**: Feed malformed events missing required fields and assert `valid=False` with details.

- **NFR-4**: Delegation cache shall support bounded TTL behavior and explicit clearability, and not crash policy enforcement when unavailable.  
  - **Mapped to**: `delegate.py:_get_cached_decision`, `delegate.py:_cache_decision`, `delegate.py:clear_cache`, `delegate.py:get_cache_stats`  
  - **TESTABLE**: Write and invalidate cache path entries and validate hit/miss behavior and clear_cache success boolean.

- **NFR-5**: Decision artifacts for execution failures (denial/tamper/path) SHALL include source action/rules context to support post-hoc investigation.  
  - **Mapped to**: `runtime_artifacts.py:build_permission_audit_event`, `runtime_artifacts.py:record_audit_event`, `interceptor.py:intercept_command`, `interceptor.py:run_guarded_subprocess`  
  - **TESTABLE**: Force a denied execution and assert audit payload contains `request.action`, `final_decision`, and `scope_chain`.

- **NFR-6**: Runtime context helpers SHALL avoid throwing on empty input and infer repository context from common worktree path patterns.  
  - **Mapped to**: `runtime_context.py:infer_repo_name_from_cwd`  
  - **TESTABLE**: Call with worktree and non-worktree paths and assert non-empty, deterministic repo inference.

## Acceptance Artifacts

- Pending Gherkin files: one per FR
  - `docs/specs/acceptance/FR-1-resolve.command.feature`
  - `docs/specs/acceptance/FR-2-manifest.command.feature`
  - `docs/specs/acceptance/FR-3-check.command.feature`
  - `docs/specs/acceptance/FR-4-evaluate.command.feature`
  - `docs/specs/acceptance/FR-5-rule-precedence.command.feature`
  - `docs/specs/acceptance/FR-6-compile.command.feature`
  - `docs/specs/acceptance/FR-7-delegate.command.feature`
  - `docs/specs/acceptance/FR-8-intercept-exit.command.feature`
  - `docs/specs/acceptance/FR-9-exec-tamper.command.feature`
  - `docs/specs/acceptance/FR-10-audit.command.feature`
  - `docs/specs/acceptance/FR-11-policy-edit.command.feature`
  - `docs/specs/acceptance/FR-12-diff.command.feature`
  - `docs/specs/acceptance/FR-13-verify.command.feature`
  - `docs/specs/acceptance/FR-14-runtime-install.command.feature`
