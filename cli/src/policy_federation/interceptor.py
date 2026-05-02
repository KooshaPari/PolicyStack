"""Runtime interception helpers for policy-enforced command execution."""

from __future__ import annotations

import datetime
import os
import shlex
import subprocess
from pathlib import Path

from .authorization import evaluate_authorization
from .headless_review import run_headless_review
from .resolver import hash_policy_sources, resolve
from .runtime_artifacts import (
    append_audit_event,
    build_permission_audit_event,
    build_run_sidecar,
    record_audit_event,
    write_sidecar,
)

ALLOW_EXIT_CODE = 0
DENY_EXIT_CODE = 2
ASK_EXIT_CODE = 3


def intercept_command(
    *,
    repo_root: Path,
    harness: str,
    repo: str,
    task_domain: str,
    task_instance: str | None,
    task_overlay: str | None,
    action: str,
    command: str,
    cwd: str | None,
    actor: str | None,
    target_paths: list[str] | None,
    ask_mode: str,
    audit_log_path: Path | None = None,
    audit_source: str = "cli",
    audit_context: dict | None = None,
    audit_conversation: dict | None = None,
    raw_command: str | None = None,
) -> dict:
    """Evaluate one runtime command and compute enforcement behavior."""
    resolved = resolve(
        repo_root=repo_root,
        harness=harness,
        repo=repo,
        task_domain=task_domain,
        task_instance=task_instance,
        task_overlay=task_overlay,
    )
    source_paths = [Path(p) for p in resolved.get("source_files", [])]
    sources_hash = hash_policy_sources(source_paths)

    evaluation = evaluate_authorization(
        resolved["policy"],
        action=action,
        command=command,
        cwd=cwd,
        actor=actor,
        target_paths=target_paths,
    )

    decision = evaluation["decision"]
    if decision == "allow":
        exit_code = ALLOW_EXIT_CODE
        allowed = True
        final_decision = "allow"
    elif decision == "deny":
        exit_code = DENY_EXIT_CODE
        allowed = False
        final_decision = "deny"
    elif ask_mode == "allow":
        exit_code = ALLOW_EXIT_CODE
        allowed = True
        final_decision = "allow"
    elif ask_mode == "review":
        review = run_headless_review(
            repo_root=repo_root,
            action=action,
            command=command,
            cwd=cwd,
            actor=actor,
            target_paths=target_paths,
            policy_decision=decision,
            policy_reason=evaluation.get("reason", "default policy"),
            matched_rules=evaluation.get("matched_rules", []),
        )
        final_decision = review["decision"]
        # Add headless_review to evaluation for test compatibility
        evaluation["headless_review"] = review
        if final_decision == "allow":
            exit_code = ALLOW_EXIT_CODE
            allowed = True
        elif final_decision == "deny":
            exit_code = DENY_EXIT_CODE
            allowed = False
        else:
            exit_code = ASK_EXIT_CODE
            allowed = False
            final_decision = "ask"
    elif ask_mode == "delegate":
        from .delegate import DelegateContext, delegate_ask
        from .risk import RiskTier, assess_risk_tiered, get_tiered_decision_path

        # Detect worktree vs canonical for risk assessment
        is_worktree = cwd and (
            ".worktrees" in cwd or "worktrees" in cwd or "-wtrees/" in cwd
        )
        is_canonical = cwd and not is_worktree

        # Use tiered risk assessment (4-tier system)
        risk_assessment = assess_risk_tiered(
            command=command,
            cwd=cwd,
            target_paths=target_paths,
            is_worktree=is_worktree,
            is_canonical=is_canonical,
        )

        tier = risk_assessment.tier
        decision_path = get_tiered_decision_path(risk_assessment)

        winning_rule = evaluation.get("winning_rule") or {}
        ctx = DelegateContext(
            action=action,
            command=command,
            cwd=cwd,
            target_paths=target_paths or [],
            risk_score=risk_assessment.score,
            risk_factors={"factors": risk_assessment.factors, "tier": tier.name},
            rule_id=winning_rule.get("id"),
            rule_description=winning_rule.get("description"),
            scope_chain=resolved["scope_chain"],
        )

        # Tier 1: Auto-allow (read ops, safe patterns) - ~60% of commands
        if tier == RiskTier.TIER_1_NONE:
            exit_code = ALLOW_EXIT_CODE
            allowed = True
            final_decision = "allow"
            evaluation = {
                **evaluation,
                "risk_tier": tier.name,
                "risk_score": risk_assessment.score,
                "risk_factors": risk_assessment.factors,
                "decision_path": decision_path,
                "auto_allowed": True,
            }

        # Tier 2: Cache-allow (low-risk, use cache) - ~15% of commands
        elif tier == RiskTier.TIER_2_LOW:
            # Check cache first via delegate_ask with cache only
            delegate_result = delegate_ask(
                ctx, use_local_fast=False, use_cache=True,
            )

            if (
                delegate_result.decision == "allow"
                and delegate_result.source.startswith("cache")
            ):
                exit_code = ALLOW_EXIT_CODE
                allowed = True
                final_decision = "allow"
            else:
                # Cache miss - use local-fast evaluator
                delegate_result = delegate_ask(
                    ctx, use_local_fast=True, use_cache=False,
                )
                if delegate_result.decision == "allow":
                    exit_code = ALLOW_EXIT_CODE
                    allowed = True
                    final_decision = "allow"
                else:
                    exit_code = ASK_EXIT_CODE
                    allowed = False
                    final_decision = "ask"

            evaluation = {
                **evaluation,
                "risk_tier": tier.name,
                "risk_score": risk_assessment.score,
                "risk_factors": risk_assessment.factors,
                "decision_path": decision_path,
                "delegate_source": delegate_result.source,
                "delegate_reasoning": delegate_result.reasoning,
            }

        # Tier 3: Fast-check (medium risk, quick validation) - ~10% of commands
        elif tier == RiskTier.TIER_3_MEDIUM:
            # Use local-fast evaluator first
            delegate_result = delegate_ask(ctx, use_local_fast=True, use_cache=True)

            if delegate_result.decision == "allow":
                exit_code = ALLOW_EXIT_CODE
                allowed = True
                final_decision = "allow"
            elif delegate_result.decision == "deny":
                exit_code = DENY_EXIT_CODE
                allowed = False
                final_decision = "deny"
            else:
                # Need full delegation
                delegate_result = delegate_ask(
                    ctx, use_local_fast=False, use_cache=True,
                )
                if delegate_result.decision == "allow":
                    exit_code = ALLOW_EXIT_CODE
                    allowed = True
                    final_decision = "allow"
                elif delegate_result.decision == "deny":
                    exit_code = DENY_EXIT_CODE
                    allowed = False
                    final_decision = "deny"
                else:
                    exit_code = ASK_EXIT_CODE
                    allowed = False
                    final_decision = "ask"

            evaluation = {
                **evaluation,
                "risk_tier": tier.name,
                "risk_score": risk_assessment.score,
                "risk_factors": risk_assessment.factors,
                "decision_path": decision_path,
                "delegate_source": delegate_result.source,
                "delegate_reasoning": delegate_result.reasoning,
                "delegate_confidence": delegate_result.confidence,
            }

        # Tier 4: Full delegation (high risk) - ~15% of commands
        else:  # RiskTier.TIER_4_HIGH
            delegate_result = delegate_ask(
                ctx, use_local_fast=False, use_cache=True,
            )

            if delegate_result.decision == "allow":
                exit_code = ALLOW_EXIT_CODE
                allowed = True
                final_decision = "allow"
            elif delegate_result.decision == "deny":
                exit_code = DENY_EXIT_CODE
                allowed = False
                final_decision = "deny"
            else:
                exit_code = ASK_EXIT_CODE
                allowed = False
                final_decision = "ask"

            evaluation = {
                **evaluation,
                "risk_tier": tier.name,
                "risk_score": risk_assessment.score,
                "risk_factors": risk_assessment.factors,
                "decision_path": decision_path,
                "delegate_source": delegate_result.source,
                "delegate_reasoning": delegate_result.reasoning,
                "delegate_confidence": delegate_result.confidence,
            }
    else:
        exit_code = ASK_EXIT_CODE
        allowed = False
        final_decision = "ask"

    result = {
        "allowed": allowed,
        "exit_code": exit_code,
        "final_decision": final_decision,
        "policy_decision": decision,
        "policy_hash": resolved["policy_hash"],
        "scope_chain": resolved["scope_chain"],
        "source_files": resolved.get("source_files", []),
        "evaluation": evaluation,
        "_sources_hash": sources_hash,
    }
    if audit_log_path is not None:
        audit_event = build_permission_audit_event(
            source=audit_source,
            request={
                "action": action,
                "command": command,
                "raw_command": raw_command or command,
                "cwd": cwd,
                "actor": actor,
                "target_paths": target_paths or [],
                "ask_mode": ask_mode,
            },
            result=result,
            context={
                "harness": harness,
                "repo": repo,
                "task_domain": task_domain,
                "task_instance": task_instance,
                "task_overlay": task_overlay,
                "policy_hash": resolved["policy_hash"],
                "scope_chain": resolved["scope_chain"],
                **(audit_context or {}),
            },
            conversation=audit_conversation,
        )
        record_audit_event(
            audit_log_path=audit_log_path,
            event=audit_event,
            stream=os.environ.get("POLICY_AUDIT_STREAM"),
        )
    return result


def run_guarded_subprocess(
    *,
    repo_root: Path,
    harness: str,
    repo: str,
    task_domain: str,
    task_instance: str | None,
    task_overlay: str | None,
    argv: list[str],
    cwd: str | None,
    actor: str | None,
    target_paths: list[str] | None,
    ask_mode: str,
    sidecar_path: Path | None = None,
    audit_log_path: Path | None = None,
) -> dict:
    """Intercept and, when allowed, execute the requested subprocess."""
    resolved_cwd = Path(cwd or Path.cwd())
    if not resolved_cwd.exists():
        raise ValueError(f"cwd does not exist: {resolved_cwd}")
    if not resolved_cwd.is_dir():
        raise ValueError(f"cwd is not a directory: {resolved_cwd}")

    command = shlex.join(argv)
    result = intercept_command(
        repo_root=repo_root,
        harness=harness,
        repo=repo,
        task_domain=task_domain,
        task_instance=task_instance,
        task_overlay=task_overlay,
        action="exec",
        command=command,
        cwd=str(resolved_cwd),
        actor=actor,
        target_paths=target_paths,
        ask_mode=ask_mode,
        audit_log_path=None,
        audit_source="runtime-exec",
        audit_context={
            "subprocess": True,
        },
        raw_command=command,
    )
    run_sidecar = build_run_sidecar(
        harness=harness,
        task_domain=task_domain,
        task_instance=task_instance,
        policy_hash=result["policy_hash"],
        scope_chain=result["scope_chain"],
        source_files=result.get("source_files", []),
    )
    audit_event = {
        "run_id": run_sidecar["run_id"],
        "action": "exec",
        "command": command,
        "cwd": str(resolved_cwd),
        "actor": actor,
        "final_decision": result["final_decision"],
        "policy_decision": result["policy_decision"],
        "policy_hash": result["policy_hash"],
        "scope_chain": result["scope_chain"],
        "timestamp": datetime.datetime.now(datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }
    if not result["allowed"]:
        if sidecar_path is not None:
            run_sidecar["audit"] = audit_event
            write_sidecar(sidecar_path=sidecar_path, payload=run_sidecar)
        if audit_log_path is not None:
            record_audit_event(
                audit_log_path=audit_log_path,
                event=build_permission_audit_event(
                    source="runtime-exec",
                    request={
                        "action": "exec",
                        "command": command,
                        "raw_command": command,
                        "cwd": str(resolved_cwd),
                        "actor": actor,
                        "target_paths": target_paths or [],
                        "ask_mode": ask_mode,
                    },
                    result={**result, "subprocess_exit_code": None},
                    context={
                        "harness": harness,
                        "repo": repo,
                        "task_domain": task_domain,
                        "task_instance": task_instance,
                        "task_overlay": task_overlay,
                        "policy_hash": result["policy_hash"],
                        "scope_chain": result["scope_chain"],
                        "subprocess": False,
                    },
                ),
                stream=os.environ.get("POLICY_AUDIT_STREAM"),
            )
        return result

    # TOCTOU re-verification immediately before exec
    source_paths = [Path(p) for p in result.get("source_files", [])]
    pre_exec_hash = hash_policy_sources(source_paths)
    if pre_exec_hash != result.get("_sources_hash", pre_exec_hash):
        result["allowed"] = False
        result["exit_code"] = DENY_EXIT_CODE
        result["final_decision"] = "deny"
        result["evaluation"] = {
            **result.get("evaluation", {}),
            "decision": "deny",
            "reason": "policy-tampered",
        }
        audit_event["final_decision"] = "deny"
        audit_event["policy_decision"] = "deny"
        if sidecar_path is not None:
            run_sidecar["audit"] = audit_event
            write_sidecar(sidecar_path=sidecar_path, payload=run_sidecar)
        if audit_log_path is not None:
            append_audit_event(audit_log_path=audit_log_path, event=audit_event)
        return result

    completed = subprocess.run(
        argv,
        cwd=str(resolved_cwd),
        env=os.environ.copy(),
        check=False,
    )
    executed = dict(result)
    executed["subprocess_exit_code"] = completed.returncode
    audit_event["subprocess_exit_code"] = completed.returncode
    if sidecar_path is not None:
        run_sidecar["audit"] = audit_event
        write_sidecar(sidecar_path=sidecar_path, payload=run_sidecar)
    if audit_log_path is not None:
        record_audit_event(
            audit_log_path=audit_log_path,
            event=build_permission_audit_event(
                source="runtime-exec",
                request={
                    "action": "exec",
                    "command": command,
                    "raw_command": command,
                    "cwd": str(resolved_cwd),
                    "actor": actor,
                    "target_paths": target_paths or [],
                    "ask_mode": ask_mode,
                },
                result=audit_event,
                context={
                    "harness": harness,
                    "repo": repo,
                    "task_domain": task_domain,
                    "task_instance": task_instance,
                    "task_overlay": task_overlay,
                    "policy_hash": result["policy_hash"],
                    "scope_chain": result["scope_chain"],
                    "subprocess": True,
                },
            ),
            stream=os.environ.get("POLICY_AUDIT_STREAM"),
        )
    return executed
