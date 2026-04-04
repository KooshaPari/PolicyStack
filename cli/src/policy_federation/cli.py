"""CLI entrypoint for policy resolution and checks."""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path

import yaml

from .authorization import evaluate_authorization
from .constants import ASK_MODE_REVIEW
from .compiler import compile_target, SUPPORTED_TARGETS
from .integrations import install_runtime_integrations, uninstall_runtime_integrations
from .interceptor import run_guarded_subprocess, intercept_command
from .policy_diff import diff_policies
from .resolver import resolve, _policy_layers
from .runtime_context import infer_repo_name_from_cwd

from .validate import validate_policy_file
from .resolver import hash_policy_sources
from .policy_editor import add_rule, remove_rule
from .runtime_artifacts import append_audit_event, filter_audit_events, read_audit_log, verify_audit_chain


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_repo_name() -> str:
    return infer_repo_name_from_cwd(str(Path.cwd()))


def _default_audit_log_path() -> Path | None:
    audit_log_path = os.environ.get("POLICY_AUDIT_LOG_PATH")
    return Path(audit_log_path).expanduser() if audit_log_path else None


def _emit_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def resolve_command(args: argparse.Namespace) -> None:
    repo_name = args.repo or _default_repo_name()
    result = resolve(
        repo_root=_default_repo_root(),
        harness=args.harness,
        repo=repo_name,
        task_domain=args.domain,
        task_instance=args.instance,
        task_overlay=args.overlay,
    )
    _emit_json(result)


def _resolve_from_args(args: argparse.Namespace) -> dict:
    return resolve(
        repo_root=_default_repo_root(),
        harness=args.harness,
        repo=args.repo or _default_repo_name(),
        task_domain=args.domain,
        task_instance=args.instance,
        task_overlay=args.overlay,
    )


def check_command(args: argparse.Namespace) -> None:
    if args.path:
        files = [Path(args.path)]
    else:
        root = _default_repo_root()
        files = sorted(root.glob("policies/**/*.yaml"))

    for f in files:
        validate_policy_file(f)
    _emit_json({"result": "policy-ok", "count": len(files)})


def manifest_command(args: argparse.Namespace) -> None:
    root = _default_repo_root()
    layers = _policy_layers(
        repo_root=root,
        harness=args.harness,
        repo=args.repo or _default_repo_name(),
        task_domain=args.domain,
        task_instance=args.instance,
        task_overlay=args.overlay,
    )
    _emit_json({"layers": [{"scope": scope, "path": str(path)} for scope, path in layers]})


def evaluate_command(args: argparse.Namespace) -> None:
    resolved = _resolve_from_args(args)
    result = evaluate_authorization(
        resolved["policy"],
        action=args.action,
        command=args.command,
        cwd=args.cwd,
        actor=args.actor,
        target_paths=args.target_path,
    )
    result["policy_hash"] = resolved["policy_hash"]
    result["scope_chain"] = resolved["scope_chain"]
    _emit_json(result)


def compile_command(args: argparse.Namespace) -> None:
    resolved = _resolve_from_args(args)
    _emit_json(compile_target(args.target, resolved))


def intercept_command_cli(args: argparse.Namespace) -> None:
    result = intercept_command(
        repo_root=_default_repo_root(),
        harness=args.harness,
        repo=args.repo or _default_repo_name(),
        task_domain=args.domain,
        task_instance=args.instance,
        task_overlay=args.overlay,
        action=args.action,
        command=args.command,
        cwd=args.cwd,
        actor=args.actor,
        target_paths=args.target_path,
        ask_mode=args.ask_mode,
        audit_log_path=_default_audit_log_path(),
    )
    _emit_json(result)
    raise SystemExit(result["exit_code"])


def review_command(args: argparse.Namespace) -> None:
    result = intercept_command(
        repo_root=_default_repo_root(),
        harness=args.harness,
        repo=args.repo or _default_repo_name(),
        task_domain=args.domain,
        task_instance=args.instance,
        task_overlay=args.overlay,
        action=args.action,
        command=args.command,
        cwd=args.cwd,
        actor=args.actor,
        target_paths=args.target_path,
        ask_mode=ASK_MODE_REVIEW,
        audit_log_path=_default_audit_log_path(),
    )
    _emit_json(result)
    raise SystemExit(result["exit_code"])


def exec_command(args: argparse.Namespace) -> None:
    argv = list(args.argv)
    if not argv:
        raise SystemExit("exec requires a command after --")

    cwd = args.cwd or str(Path.cwd())
    repo = args.repo or _default_repo_name()
    try:
        result = run_guarded_subprocess(
            repo_root=_default_repo_root(),
            harness=args.harness,
            repo=repo,
            task_domain=args.domain,
            task_instance=args.instance,
            task_overlay=args.overlay,
            argv=argv,
            cwd=cwd,
            actor=args.actor,
            target_paths=args.target_path,
            ask_mode=args.ask_mode,
            sidecar_path=Path(args.sidecar_path) if args.sidecar_path else None,
            audit_log_path=(
                Path(args.audit_log_path)
                if args.audit_log_path
                else _default_audit_log_path()
            ),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.report_json:
        _emit_json(result)
    raise SystemExit(result.get("subprocess_exit_code", result["exit_code"]))


def write_check_command(args: argparse.Namespace) -> None:
    result = intercept_command(
        repo_root=_default_repo_root(),
        harness=args.harness,
        repo=args.repo or _default_repo_name(),
        task_domain=args.domain,
        task_instance=args.instance,
        task_overlay=args.overlay,
        action="write",
        command=args.command or "write",
        cwd=args.cwd or str(Path.cwd()),
        actor=args.actor,
        target_paths=args.target_path,
        ask_mode=args.ask_mode,
        audit_log_path=_default_audit_log_path(),
    )
    _emit_json(result)
    raise SystemExit(result["exit_code"])


def network_check_command(args: argparse.Namespace) -> None:
    result = intercept_command(
        repo_root=_default_repo_root(),
        harness=args.harness,
        repo=args.repo or _default_repo_name(),
        task_domain=args.domain,
        task_instance=args.instance,
        task_overlay=args.overlay,
        action="network",
        command=args.command,
        cwd=args.cwd or str(Path.cwd()),
        actor=args.actor,
        target_paths=[],
        ask_mode=args.ask_mode,
        audit_log_path=_default_audit_log_path(),
    )
    _emit_json(result)
    raise SystemExit(result["exit_code"])


def install_runtime_command(args: argparse.Namespace) -> None:
    home = Path(args.home).expanduser() if args.home else Path.home()
    result = install_runtime_integrations(_default_repo_root(), home)
    _emit_json(result)


def uninstall_runtime_command(args: argparse.Namespace) -> None:
    home = Path(args.home).expanduser() if args.home else Path.home()
    result = uninstall_runtime_integrations(_default_repo_root(), home)
    _emit_json(result)


def audit_command(args: argparse.Namespace) -> None:
    """Read, filter, and display audit log events."""
    # Determine audit log path
    audit_log_path = None
    if args.log_path:
        audit_log_path = Path(args.log_path)
    else:
        env_path = os.environ.get("POLICY_AUDIT_LOG_PATH")
        if env_path:
            audit_log_path = Path(env_path)
        else:
            audit_log_path = Path.home() / ".policy-federation" / "audit.jsonl"

    # Read all events
    events = read_audit_log(audit_log_path)

    # Parse time filters
    since_dt = None
    if args.since:
        since_dt = _parse_iso_datetime(args.since)

    until_dt = None
    if args.until:
        until_dt = _parse_iso_datetime(args.until)

    # Filter events
    filtered = filter_audit_events(
        events,
        since=since_dt,
        until=until_dt,
        action=args.action,
        decision=args.decision,
        actor_pattern=args.actor,
    )

    # Verify chain if requested
    if args.verify_chain:
        chain_result = verify_audit_chain(filtered)
        print(f"Chain verification: {chain_result['message']}")
        if not chain_result["valid"]:
            _emit_json(chain_result)
            raise SystemExit(1)

    # Show summary if requested
    if args.summary:
        summary = _compute_audit_summary(filtered)
        _emit_json(summary)
    else:
        # Default: print each event as formatted JSON
        for event in filtered:
            print(json.dumps(event, sort_keys=True))


def _parse_iso_datetime(iso_str: str) -> datetime.datetime:
    """Parse ISO 8601 datetime string."""
    # Handle both 'Z' and '+00:00' formats
    normalized = iso_str.replace("Z", "+00:00")
    return datetime.datetime.fromisoformat(normalized)


def _compute_audit_summary(events: list[dict]) -> dict:
    """Compute summary statistics from audit events."""
    summary = {
        "total": len(events),
        "by_decision": {"allow": 0, "deny": 0, "ask": 0},
        "by_action": {},
    }

    for event in events:
        decision = event.get("final_decision", "unknown")
        if decision in summary["by_decision"]:
            summary["by_decision"][decision] += 1

        action = event.get("action", "unknown")
        summary["by_action"][action] = summary["by_action"].get(action, 0) + 1

    return summary


def diff_command(args: argparse.Namespace) -> None:
    """Load two policy YAML files and output their differences."""
    before_path = Path(args.before)
    after_path = Path(args.after)

    if not before_path.exists():
        raise SystemExit(f"before policy file not found: {before_path}")
    if not after_path.exists():
        raise SystemExit(f"after policy file not found: {after_path}")

    # Load before and after policies
    with before_path.open("r", encoding="utf-8") as f:
        before_doc = yaml.safe_load(f) or {}
    with after_path.open("r", encoding="utf-8") as f:
        after_doc = yaml.safe_load(f) or {}

    # Extract policy sections
    before_policy = before_doc.get("policy", {})
    after_policy = after_doc.get("policy", {})

    # Compute diff
    diff_result = diff_policies(before_policy, after_policy)

    # Pretty-print the diff with color
    _print_diff_with_color(diff_result)

    # Also output as JSON
    _emit_json(diff_result)


def _print_diff_with_color(diff_result: dict) -> None:
    """Print policy diff results with colored output."""
    # ANSI color codes
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    print(f"\n{BOLD}Policy Diff Report{RESET}")
    print("=" * 60)

    # Added rules (green)
    added = diff_result.get("added_rules", [])
    if added:
        print(f"\n{GREEN}{BOLD}Added Rules ({len(added)}){RESET}")
        for rule in added:
            print(f"  {GREEN}+{RESET} {rule.get('id', 'N/A')}: {rule.get('effect', 'N/A')}")
            if rule.get("description"):
                print(f"    {rule.get('description')}")

    # Removed rules (red)
    removed = diff_result.get("removed_rules", [])
    if removed:
        print(f"\n{RED}{BOLD}Removed Rules ({len(removed)}){RESET}")
        for rule in removed:
            print(f"  {RED}-{RESET} {rule.get('id', 'N/A')}: {rule.get('effect', 'N/A')}")
            if rule.get("description"):
                print(f"    {rule.get('description')}")

    # Modified rules (yellow)
    modified = diff_result.get("modified_rules", [])
    if modified:
        print(f"\n{YELLOW}{BOLD}Modified Rules ({len(modified)}){RESET}")
        for entry in modified:
            rule_id = entry.get("id", "N/A")
            before = entry.get("before", {})
            after = entry.get("after", {})
            print(f"  {YELLOW}~{RESET} {rule_id}")
            print(f"    Before: {before.get('effect', 'N/A')}")
            print(f"    After:  {after.get('effect', 'N/A')}")

    # Effect changes (cyan highlight)
    effect_changes = diff_result.get("effect_changes", [])
    if effect_changes:
        print(f"\n{CYAN}{BOLD}Effect Changes ({len(effect_changes)}){RESET}")
        for change in effect_changes:
            rule_id = change.get("id", "N/A")
            before_effect = change.get("before_effect", "N/A")
            after_effect = change.get("after_effect", "N/A")
            print(f"  {CYAN}!{RESET} {rule_id}: {before_effect} {CYAN}->{RESET} {after_effect}")
            if change.get("description"):
                print(f"    {change.get('description')}")

    # Summary
    total_added = len(added)
    total_removed = len(removed)
    total_modified = len(modified)
    total_effect_changes = len(effect_changes)
    print(f"\n{BOLD}Summary{RESET}: +{total_added} -{total_removed} ~{total_modified} !{total_effect_changes}")
    print("=" * 60 + "\n")


def add_rule_command(args: argparse.Namespace) -> None:
    """Add a rule to a policy file."""
    policy_path = Path(args.file)

    # Build the rule dictionary
    rule: dict = {
        "id": args.id,
        "effect": args.effect,
        "actions": args.actions.split(","),
        "priority": args.priority,
    }

    # Add optional match conditions
    match_conditions = {}
    if args.command_patterns:
        match_conditions["command_patterns"] = args.command_patterns.split(",")
    if args.target_path_patterns:
        match_conditions["target_path_patterns"] = args.target_path_patterns.split(",")
    if args.cwd_patterns:
        match_conditions["cwd_patterns"] = args.cwd_patterns.split(",")

    if match_conditions:
        rule["match"] = match_conditions

    try:
        add_rule(policy_path, rule)
        result = {
            "result": "rule-added",
            "policy": str(policy_path),
            "rule_id": args.id,
        }

        # Record audit event if audit log path provided
        if args.audit_log_path:
            audit_event = {
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "action": "policy-rule-add",
                "policy_file": str(policy_path),
                "rule_id": args.id,
                "effect": args.effect,
            }
            append_audit_event(
                audit_log_path=Path(args.audit_log_path),
                event=audit_event,
            )

        _emit_json(result)
    except ValueError as exc:
        _emit_json({"error": str(exc)})
        raise SystemExit(1)


def remove_rule_command(args: argparse.Namespace) -> None:
    """Remove a rule from a policy file."""
    policy_path = Path(args.file)

    try:
        remove_rule(policy_path, args.id)
        result = {
            "result": "rule-removed",
            "policy": str(policy_path),
            "rule_id": args.id,
        }

        # Record audit event if audit log path provided
        if args.audit_log_path:
            audit_event = {
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "action": "policy-rule-remove",
                "policy_file": str(policy_path),
                "rule_id": args.id,
            }
            append_audit_event(
                audit_log_path=Path(args.audit_log_path),
                event=audit_event,
            )

        _emit_json(result)
    except ValueError as exc:
        _emit_json({"error": str(exc)})
        raise SystemExit(1)


def verify_command(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root) if args.repo_root else _default_repo_root()
    baseline_file = repo_root / ".policyctl.verify"

    # Collect policy source files
    source_files = sorted(repo_root.glob("policies/**/*.yaml"))
    current_hash = hash_policy_sources([Path(f) for f in source_files])

    # Check if baseline exists
    if not baseline_file.exists():
        # Record baseline
        baseline_file.write_text(current_hash + "\n", encoding="utf-8")
        _emit_json({"status": "baseline-recorded", "hash": current_hash, "file_count": len(source_files)})
        return

    # Compare against baseline
    baseline_hash = baseline_file.read_text(encoding="utf-8").strip()

    if baseline_hash == current_hash:
        _emit_json({"status": "ok", "hash": current_hash, "file_count": len(source_files)})
    else:
        _emit_json({
            "status": "tampered",
            "current_hash": current_hash,
            "baseline_hash": baseline_hash,
            "file_count": len(source_files),
        })
        raise SystemExit(1)


def learn_command(args: argparse.Namespace) -> None:
    """Analyze audit logs and suggest policy rules."""
    from .learner import analyze_audit, suggestions_to_yaml, write_suggestions

    audit_path = Path(
        args.audit_log_path
        or os.environ.get("POLICY_AUDIT_LOG_PATH", str(Path.home() / ".policy-federation" / "audit.jsonl"))
    )

    since = None
    if args.since:
        import re as _re
        m = _re.match(r"(\d+)([dhm])", args.since)
        if m:
            n, unit = int(m.group(1)), m.group(2)
            delta = {"d": datetime.timedelta(days=n), "h": datetime.timedelta(hours=n), "m": datetime.timedelta(minutes=n)}[unit]
            since = datetime.datetime.now(datetime.UTC) - delta
        else:
            since = datetime.datetime.fromisoformat(args.since.replace("Z", "+00:00"))

    suggestions = analyze_audit(
        audit_path,
        since=since,
        min_cluster_size=args.min_cluster_size,
        min_confidence=args.min_confidence,
    )

    if not suggestions:
        print("No rule suggestions generated (insufficient data or all clusters below threshold).")
        return

    if args.dry_run:
        print(f"# {len(suggestions)} rule suggestion(s):\n")
        print(suggestions_to_yaml(suggestions))
    else:
        repo_root = Path(
            args.repo_root
            or os.environ.get("POLICY_REPO_ROOT", str(Path(__file__).resolve().parents[3]))
        )
        output_dir = repo_root / "policies" / "suggestions"
        output_path = write_suggestions(suggestions, output_dir)
        print(f"Wrote {len(suggestions)} suggestion(s) to {output_path}")


def gaps_command(args: argparse.Namespace) -> None:
    """Detect policy gaps from audit log analysis."""
    from .gap_detector import detect_gaps, format_gap_report

    audit_path = Path(
        args.audit_log_path
        or os.environ.get("POLICY_AUDIT_LOG_PATH", str(Path.home() / ".policy-federation" / "audit.jsonl"))
    )
    repo_root = Path(
        args.repo_root
        or os.environ.get("POLICY_REPO_ROOT", str(Path(__file__).resolve().parents[3]))
    )

    report = detect_gaps(
        audit_log_path=audit_path,
        repo_root=repo_root,
        harness=args.harness or "claude-code",
        repo=args.repo or "",
        task_domain=args.domain or "devops",
        min_ask_frequency=args.min_frequency,
    )

    print(format_gap_report(report))


def main() -> None:
    parser = argparse.ArgumentParser("policyctl")
    sub = parser.add_subparsers(dest="cmd", required=True)

    resolve_parser = sub.add_parser("resolve")
    resolve_parser.add_argument("--harness", required=True)
    resolve_parser.add_argument("--domain", required=True)
    resolve_parser.add_argument("--repo")
    resolve_parser.add_argument("--instance")
    resolve_parser.add_argument("--overlay")
    resolve_parser.set_defaults(func=resolve_command)

    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--harness", required=True)
    evaluate_parser.add_argument("--domain", required=True)
    evaluate_parser.add_argument("--repo")
    evaluate_parser.add_argument("--instance")
    evaluate_parser.add_argument("--overlay")
    evaluate_parser.add_argument("--action", required=True)
    evaluate_parser.add_argument("--command")
    evaluate_parser.add_argument("--cwd")
    evaluate_parser.add_argument("--actor")
    evaluate_parser.add_argument("--target-path", action="append", default=[])
    evaluate_parser.set_defaults(func=evaluate_command)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("path", nargs="?")
    check_parser.set_defaults(func=check_command)

    manifest_parser = sub.add_parser("manifest")
    manifest_parser.add_argument("--harness", required=True)
    manifest_parser.add_argument("--domain", required=True)
    manifest_parser.add_argument("--repo")
    manifest_parser.add_argument("--instance")
    manifest_parser.add_argument("--overlay")
    manifest_parser.set_defaults(func=manifest_command)

    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("--target", required=True, choices=sorted(SUPPORTED_TARGETS))
    compile_parser.add_argument("--harness", required=True)
    compile_parser.add_argument("--domain", required=True)
    compile_parser.add_argument("--repo")
    compile_parser.add_argument("--instance")
    compile_parser.add_argument("--overlay")
    compile_parser.set_defaults(func=compile_command)

    intercept_parser = sub.add_parser("intercept")
    intercept_parser.add_argument("--harness", required=True)
    intercept_parser.add_argument("--domain", required=True)
    intercept_parser.add_argument("--repo")
    intercept_parser.add_argument("--instance")
    intercept_parser.add_argument("--overlay")
    intercept_parser.add_argument("--action", required=True)
    intercept_parser.add_argument("--command", required=True)
    intercept_parser.add_argument("--cwd")
    intercept_parser.add_argument("--actor")
    intercept_parser.add_argument("--target-path", action="append", default=[])
    intercept_parser.add_argument("--ask-mode", choices=["fail", "allow", "prompt"], default="fail")
    intercept_parser.add_argument("--prompt-text")
    intercept_parser.set_defaults(func=intercept_command_cli)

    exec_parser = sub.add_parser("exec")
    exec_parser.add_argument("--harness", required=True)
    exec_parser.add_argument("--domain", required=True)
    exec_parser.add_argument("--repo")
    exec_parser.add_argument("--instance")
    exec_parser.add_argument("--overlay")
    exec_parser.add_argument("--cwd")
    exec_parser.add_argument("--actor")
    exec_parser.add_argument("--target-path", action="append", default=[])
    exec_parser.add_argument("--ask-mode", choices=["fail", "allow", "prompt"], default="fail")
    exec_parser.add_argument("--prompt-text")
    exec_parser.add_argument("--sidecar-path")
    exec_parser.add_argument("--audit-log-path")
    exec_parser.add_argument("--report-json", action="store_true")
    exec_parser.add_argument("argv", nargs=argparse.REMAINDER)
    exec_parser.set_defaults(func=exec_command)

    write_parser = sub.add_parser("write-check")
    write_parser.add_argument("--harness", required=True)
    write_parser.add_argument("--domain", required=True)
    write_parser.add_argument("--repo")
    write_parser.add_argument("--instance")
    write_parser.add_argument("--overlay")
    write_parser.add_argument("--cwd")
    write_parser.add_argument("--actor")
    write_parser.add_argument("--command")
    write_parser.add_argument("--target-path", action="append", required=True)
    write_parser.add_argument("--ask-mode", choices=["fail", "allow", "prompt"], default="fail")
    write_parser.add_argument("--prompt-text")
    write_parser.set_defaults(func=write_check_command)

    network_parser = sub.add_parser("network-check")
    network_parser.add_argument("--harness", required=True)
    network_parser.add_argument("--domain", required=True)
    network_parser.add_argument("--repo")
    network_parser.add_argument("--instance")
    network_parser.add_argument("--overlay")
    network_parser.add_argument("--cwd")
    network_parser.add_argument("--actor")
    network_parser.add_argument("--command", required=True)
    network_parser.add_argument("--ask-mode", choices=["fail", "allow", "prompt"], default="fail")
    network_parser.add_argument("--prompt-text")
    network_parser.set_defaults(func=network_check_command)

    install_parser = sub.add_parser("install-runtime")
    install_parser.add_argument("--home")
    install_parser.set_defaults(func=install_runtime_command)

    uninstall_parser = sub.add_parser("uninstall-runtime")
    uninstall_parser.add_argument("--home")
    uninstall_parser.set_defaults(func=uninstall_runtime_command)

    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument(
        "--log-path",
        help="Path to audit log (default: $POLICY_AUDIT_LOG_PATH or ~/.policy-federation/audit.jsonl)"
    )
    audit_parser.add_argument(
        "--since",
        help="Filter events since ISO-8601 datetime (e.g., 2024-01-01T00:00:00Z)"
    )
    audit_parser.add_argument(
        "--until",
        help="Filter events until ISO-8601 datetime (e.g., 2024-12-31T23:59:59Z)"
    )
    audit_parser.add_argument(
        "--action",
        choices=["exec", "write", "network"],
        help="Filter by action type"
    )
    audit_parser.add_argument(
        "--decision",
        choices=["allow", "deny", "ask"],
        help="Filter by decision"
    )
    audit_parser.add_argument(
        "--actor",
        help="Filter by actor (regex pattern or substring)"
    )
    audit_parser.add_argument(
        "--verify-chain",
        action="store_true",
        help="Verify audit chain integrity"
    )
    audit_parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary statistics instead of individual events"
    )
    audit_parser.set_defaults(func=audit_command)

    diff_parser = sub.add_parser("diff")
    diff_parser.add_argument("before", help="Path to before policy YAML file")
    diff_parser.add_argument("after", help="Path to after policy YAML file")
    diff_parser.set_defaults(func=diff_command)

    add_rule_parser = sub.add_parser("add-rule")
    add_rule_parser.add_argument("--file", required=True, help="Path to policy YAML file")
    add_rule_parser.add_argument("--id", required=True, help="Unique rule ID")
    add_rule_parser.add_argument("--effect", required=True, choices=["allow", "deny", "ask"],
                                help="Rule effect")
    add_rule_parser.add_argument("--priority", required=True, type=int, help="Rule priority (integer)")
    add_rule_parser.add_argument("--actions", required=True,
                                help="Comma-separated list of actions (e.g., exec,write,network)")
    add_rule_parser.add_argument("--command-patterns",
                                help="Comma-separated command pattern list")
    add_rule_parser.add_argument("--target-path-patterns",
                                help="Comma-separated target path pattern list")
    add_rule_parser.add_argument("--cwd-patterns",
                                help="Comma-separated cwd pattern list")
    add_rule_parser.add_argument("--audit-log-path",
                                help="Optional path to audit log for recording the change")
    add_rule_parser.set_defaults(func=add_rule_command)

    remove_rule_parser = sub.add_parser("remove-rule")
    remove_rule_parser.add_argument("--file", required=True, help="Path to policy YAML file")
    remove_rule_parser.add_argument("--id", required=True, help="Rule ID to remove")
    remove_rule_parser.add_argument("--audit-log-path",
                                   help="Optional path to audit log for recording the change")
    remove_rule_parser.set_defaults(func=remove_rule_command)

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--repo-root", help="Path to repository root (default: inferred)")
    verify_parser.set_defaults(func=verify_command)

    learn_parser = sub.add_parser("learn")
    learn_parser.add_argument(
        "--since",
        help="Time filter: '7d', '30d', '24h', or ISO-8601 datetime",
    )
    learn_parser.add_argument(
        "--min-cluster-size", type=int, default=5,
        help="Minimum events to form a suggestion (default: 5)",
    )
    learn_parser.add_argument(
        "--min-confidence", type=float, default=0.8,
        help="Minimum consistency ratio (default: 0.8)",
    )
    learn_parser.add_argument(
        "--dry-run", action="store_true",
        help="Print YAML suggestions without writing to disk",
    )
    learn_parser.add_argument("--audit-log-path", help="Override audit log path")
    learn_parser.add_argument("--repo-root", help="Override repo root")
    learn_parser.set_defaults(func=learn_command)

    gaps_parser = sub.add_parser("gaps")
    gaps_parser.add_argument(
        "--min-frequency", type=int, default=3,
        help="Minimum ask count to report (default: 3)",
    )
    gaps_parser.add_argument("--audit-log-path", help="Override audit log path")
    gaps_parser.add_argument("--repo-root", help="Override repo root")
    gaps_parser.add_argument("--harness", help="Harness name (default: claude-code)")
    gaps_parser.add_argument("--repo", help="Repository name")
    gaps_parser.add_argument("--domain", help="Task domain (default: devops)")
    gaps_parser.set_defaults(func=gaps_command)

    args = parser.parse_args()
    if getattr(args, "argv", None) and args.argv and args.argv[0] == "--":
        args.argv = args.argv[1:]
    args.func(args)


if __name__ == "__main__":
    main()
