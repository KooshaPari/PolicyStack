#!/usr/bin/env python3
"""
Resolve layered agent policy scopes.
"""

from __future__ import annotations

import argparse
import importlib.util
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


SCOPE_ORDER = [
    "system",
    "user",
    "repo",
    "harness",
    "task_domain",
    "task_instance",
]
REQUIRED_SCOPES = ("system", "user", "repo", "harness", "task_domain")


SAFE_SCOPE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


MERGE_STRATEGY = {
    "commands.allow": "append_dedup",
    "commands.require": "replace",
    "commands.deny": "replace",
    "command_rules": "append_dedup",
    "required_checks": "append_dedup",
    "tooling.harness": "append_dedup",
    "observability.telemetry_targets": "append_dedup",
    "observability.audit_events": "append_dedup",
    "approval.needs_confirmation_for": "append_dedup",
    "security.guardrails": "append_dedup",
    "security.secret_backends": "append_dedup",
    "security.pii_policy": "replace",
}

APPEND_LIST_PATHS = {
    key for key, strategy in MERGE_STRATEGY.items() if strategy == "append_dedup"
}

EXIT_CODE_OK = 0
EXIT_CODE_ARG = 2
EXIT_CODE_MISSING = 3
EXIT_CODE_INVALID = 4
EXIT_CODE_INTERNAL = 5

ERROR_CODE_OK = "ok"
ERROR_CODE_ARG = "arg"
ERROR_CODE_MISSING = "missing"
ERROR_CODE_INVALID = "invalid"
ERROR_CODE_INTERNAL = "internal"


class _ArgumentParseError(Exception):
    def __init__(self, message: str, *, status: int = EXIT_CODE_ARG) -> None:
        super().__init__(message)
        self.status = status


class _ResolverArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentParseError(message, status=EXIT_CODE_ARG)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if status == 0:
            raise SystemExit(EXIT_CODE_OK)
        text = (message or "").strip() or "argument parsing failed"
        raise _ArgumentParseError(text, status=status)


def load_yaml(
    path: Path, *, required: bool = False, scope: str | None = None
) -> dict[str, Any]:
    if not path.exists():
        if required:
            scope_label = f" for scope '{scope}'" if scope else ""
            raise FileNotFoundError(
                f"missing required policy file{scope_label}: {path}"
            )
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"policy at {path} must be a YAML map")
    return data


def validate_policy(
    data: dict[str, Any], path: Path, *, expected_scope: str | None = None
) -> None:
    if "policy_version" not in data or not isinstance(data["policy_version"], str):
        raise ValueError(f"{path}: policy_version missing or invalid")
    if data["policy_version"] != "v1":
        raise ValueError(f"{path}: policy_version must be 'v1'")
    scope_name = data.get("scope")
    if scope_name not in SCOPE_ORDER:
        raise ValueError(f"{path}: invalid scope {scope_name}")
    if expected_scope is not None and scope_name != expected_scope:
        raise ValueError(
            f"{path}: scope mismatch in chain: expected "
            f"{expected_scope}, got {scope_name}"
        )


def _validate_scope_identifier(value: str, flag: str) -> None:
    if "/" in value or "\\" in value or value != Path(value).name:
        raise _ArgumentParseError(f"{flag} must not contain path separators")
    if not SAFE_SCOPE_RE.fullmatch(value):
        raise _ArgumentParseError(f"{flag} must match {SAFE_SCOPE_RE.pattern}")


def _get_nested_value(data: dict[str, Any], dotted_key: str) -> Any:
    value: Any = data
    parts = dotted_key.split(".")
    for idx, part in enumerate(parts):
        if not isinstance(value, dict):
            parent = ".".join(parts[:idx]) or "policy"
            raise TypeError(f"{dotted_key}: expected mapping at {parent}")
        if part not in value:
            return None
        value = value[part]
    return value


def _validate_policy_payload_types(data: dict[str, Any], path: Path) -> None:
    for dotted_key in APPEND_LIST_PATHS:
        try:
            value = _get_nested_value(data, dotted_key)
        except TypeError as exc:
            raise TypeError(f"{path}: {exc}") from exc
        if value is not None and not isinstance(value, list):
            raise TypeError(f"{path}: {dotted_key} must be a list")


def _ensure_list(value: Any, label: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a list")
    return list(value)


def _dedupe(items: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen = set()
    for item in items:
        key = repr(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _scope_priority(scope_name: str) -> int:
    try:
        return SCOPE_ORDER.index(scope_name)
    except ValueError:
        return len(SCOPE_ORDER)


def _validate_scope_chain(chain: list[tuple[str, str]]) -> None:
    scope_names = [scope_name for scope_name, _ in chain]
    for index, scope_name in enumerate(scope_names):
        if index < len(REQUIRED_SCOPES):
            expected_scope = REQUIRED_SCOPES[index]
            if scope_name != expected_scope:
                raise ValueError(
                    "scope progression mismatch: expected "
                    f"{expected_scope}, got {scope_name} at position {index + 1}"
                )
            continue

        if scope_name != "task_instance":
            raise ValueError(
                f"scope progression mismatch: unexpected scope {scope_name} "
                f"at position {index + 1}; expected task_instance"
            )

    if not set(REQUIRED_SCOPES).issubset(scope_names):
        missing_scopes = ", ".join(sorted(set(REQUIRED_SCOPES) - set(scope_names)))
        raise ValueError(
            f"required scopes missing from final resolved policy: {missing_scopes}"
        )

    task_instance_count = scope_names.count("task_instance")
    if task_instance_count > 1:
        raise ValueError("duplicate scope in chain: task_instance")


def _normalized_scope_chain(chain: list[tuple[str, str]]) -> list[tuple[str, str]]:
    indexed_chain = list(enumerate(chain))
    indexed_chain.sort(
        key=lambda entry: (
            _scope_priority(entry[1][0]),
            entry[0],
        )
    )
    return [item for _, item in indexed_chain]


def _build_resolved_payload(
    merged_policy: dict[str, Any],
    scope_chain: list[tuple[str, str]],
) -> dict[str, Any]:
    normalized_scopes = _normalized_scope_chain(scope_chain)
    digest = hashlib.sha256(
        json.dumps(merged_policy, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "policy_hash": digest,
        "scopes": normalized_scopes,
        "policy": merged_policy,
    }


def _merge_dict(
    base: dict[str, Any], override: dict[str, Any], base_path: str = ""
) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        key_path = f"{base_path}.{key}" if base_path else key
        if key in ("extends", "notes"):
            continue
        if key not in out:
            out[key] = value
            continue
        base_value = out[key]
        if isinstance(base_value, dict) and not isinstance(value, dict):
            raise TypeError(
                f"{key_path}: expected mapping but got {type(value).__name__}"
            )
        if isinstance(base_value, list) and not isinstance(value, list):
            raise TypeError(f"{key_path}: expected list but got {type(value).__name__}")
        if isinstance(base_value, dict) and isinstance(value, dict):
            out[key] = _merge_dict(base_value, value, key_path)
            continue
        if isinstance(base_value, list) and isinstance(value, list):
            strategy = MERGE_STRATEGY.get(key_path, "replace")
            if strategy == "append_dedup":
                out[key] = _dedupe(base_value + value)
            else:
                out[key] = value
            continue
        out[key] = value
    if base_path == "":
        out["scope"] = override.get("scope", out.get("scope"))
        out["policy_version"] = override.get(
            "policy_version", out.get("policy_version")
        )
    return out


def _load_host_rules_emitter():
    """Load the host-rule emitter without importing package-level path state."""
    script_path = Path(__file__).resolve().parent / "scripts" / "sync_host_rules.py"
    spec = importlib.util.spec_from_file_location(
        "policy_contract_host_sync", script_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load host sync script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_host_artifacts(out_dir: Path, rendered: dict[str, Any]) -> None:
    required_files = [
        out_dir / "codex.rules",
        out_dir / "cursor.cli-config.json",
        out_dir / "claude.settings.json",
        out_dir / "factory-droid.settings.json",
        out_dir / "policy-wrapper-rules.json",
        out_dir / "policy-wrapper-dispatch.manifest.json",
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing host artifacts: {', '.join(missing)}")

    with (out_dir / "policy-wrapper-dispatch.manifest.json").open(
        "r", encoding="utf-8"
    ) as fp:
        manifest = json.load(fp)
    if manifest.get("bundle_path") != str(out_dir / "policy-wrapper-rules.json"):
        raise ValueError(
            "dispatch manifest bundle_path does not match output directory"
        )

    required_fallbacks = (
        "fallback_missing_policy",
        "fallback_malformed_bundle",
        "fallback_condition_eval_error",
    )
    for key in required_fallbacks:
        if key not in manifest:
            raise ValueError(f"dispatch manifest missing fallback field: {key}")
        decision = manifest.get(key)
        if decision not in {"allow", "request", "deny"}:
            raise ValueError(
                f"dispatch manifest field {key} has invalid decision: {decision}"
            )

    wrapper_rules = rendered.get("wrapper_rules")
    if not isinstance(wrapper_rules, list):
        raise ValueError("rendered wrapper_rules missing or invalid")
    payload_count = len(wrapper_rules)

    expected_wrapper_rules = rendered.get("wrapper_rule_count", payload_count)
    if not isinstance(expected_wrapper_rules, int):
        raise ValueError("rendered wrapper_rule_count must be an integer when provided")
    if expected_wrapper_rules != payload_count:
        raise ValueError(
            "rendered wrapper rule count mismatch: "
            f"{expected_wrapper_rules} != {payload_count}"
        )

    manifest_wrapper_count = manifest.get("wrapper_rule_count")
    if manifest_wrapper_count != expected_wrapper_rules:
        raise ValueError(
            "dispatch manifest wrapper_rule_count mismatch: "
            f"{manifest_wrapper_count} != {expected_wrapper_rules}"
        )

    with (out_dir / "policy-wrapper-rules.json").open("r", encoding="utf-8") as fp:
        policy_wrapper_payload = json.load(fp)
    if len(policy_wrapper_payload.get("commands", [])) != payload_count:
        raise ValueError("policy-wrapper command payload count mismatch")


def resolve(
    policies: list[tuple[str, Path]], output: Path | None = None
) -> dict[str, Any]:
    chain = []
    merged: dict[str, Any] = {}
    required_scopes = set(REQUIRED_SCOPES)
    seen_scopes = set()
    for scope, path in policies:
        policy = load_yaml(path, required=scope in required_scopes, scope=scope)
        if not policy:
            if scope in required_scopes:
                raise ValueError(
                    f"{path}: required scope '{scope}' file is empty or missing payload"
                )
            continue
        _validate_policy_payload_types(policy, path)
        validate_policy(policy, path)
        scope_name = policy["scope"]
        if scope_name in seen_scopes and scope in {"task_domain", "task_instance"}:
            raise ValueError(f"duplicate scope in chain: {scope_name}")
        if scope_name != scope:
            raise ValueError(
                f"{path}: scope mismatch in chain: expected {scope}, got {scope_name}"
            )
        if scope_name in seen_scopes:
            raise ValueError(f"duplicate scope in chain: {scope_name}")
        seen_scopes.add(scope_name)
        chain.append((scope_name, str(path)))
        merged = _merge_dict(merged, policy)
    _validate_scope_chain(chain)
    if output is None:
        return merged
    payload = _build_resolved_payload(merged, chain)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _resolve_config_root(root: Path) -> Path:
    repo_layout = root / "policy-config"
    nested_layout = root / "policy-contract" / "policy-config"

    if repo_layout.exists():
        return repo_layout
    if nested_layout.exists():
        return nested_layout
    raise FileNotFoundError(
        "no supported config root layout exists; expected one of "
        f"{repo_layout} or {nested_layout}"
    )


def _build_chain(args: argparse.Namespace) -> list[tuple[str, Path]]:
    _validate_scope_identifier(args.harness, "--harness")
    _validate_scope_identifier(args.task_domain, "--task-domain")
    root = Path(args.root).resolve()
    config_root = _resolve_config_root(root)
    chain: list[tuple[str, Path]] = []

    # Optional global/system/user override files if present.
    if args.system:
        chain.append(("system", Path(args.system).expanduser().resolve()))
    else:
        chain.append(("system", config_root / "system.yaml"))

    if args.user:
        chain.append(("user", Path(args.user).expanduser().resolve()))
    else:
        chain.append(("user", config_root / "user.yaml"))

    chain.append(("repo", config_root / "repo.yaml"))
    chain.append(("harness", config_root / "harness" / f"{args.harness}.yaml"))
    chain.append(
        ("task_domain", config_root / "task-domain" / f"{args.task_domain}.yaml")
    )

    if args.task_instance:
        chain.append(("task_instance", Path(args.task_instance).expanduser().resolve()))
    return chain


def _count_existing_scopes(chain: list[tuple[str, Path]]) -> int:
    return sum(1 for _, path in chain if path.exists())


def _print_failure_json(
    code: str, message: str, details: dict[str, Any] | None = None
) -> None:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    print(json.dumps(payload, indent=2))


def _print_success_json(
    message: str,
    result: dict[str, Any],
    *,
    scope_count: int,
    chain_length: int,
    emit_path: Path | None = None,
    scopes_ordering_assertion_path: str | None = None,
) -> None:
    details: dict[str, Any] = {
        "scope_count": scope_count,
        "chain_length": chain_length,
    }
    if emit_path is not None:
        details["emit_path"] = str(emit_path)
    if scopes_ordering_assertion_path is not None:
        details["scopes_ordering_assertion_path"] = scopes_ordering_assertion_path
    payload = {
        "code": ERROR_CODE_OK,
        "message": message,
        "details": details,
        "result": result,
    }
    print(json.dumps(payload, indent=2))


def _build_parser() -> _ResolverArgumentParser:
    parser = _ResolverArgumentParser(description="Resolve scoped agent policy files.")
    parser.add_argument(
        "--root", default=".", help="Repo root containing policy-contract."
    )
    parser.add_argument("--harness", required=True, help="harness identifier")
    parser.add_argument("--task-domain", required=True, help="task domain identifier")
    parser.add_argument("--task-instance", help="optional task-instance policy file")
    parser.add_argument(
        "--system", help="optional absolute or relative system policy path"
    )
    parser.add_argument("--user", help="optional absolute or relative user policy path")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON payload on resolver failure",
    )
    parser.add_argument("--emit", help="write resolved policy JSON to file")
    parser.add_argument(
        "--emit-host-rules",
        action="store_true",
        help="emit cross-host command policy fragments",
    )
    parser.add_argument(
        "--apply-host-rules",
        action="store_true",
        help="apply host policy fragments to live tool configs",
    )
    parser.add_argument(
        "--host-out-dir",
        default=None,
        help="optional output directory for host-specific policy snippets",
    )
    parser.add_argument(
        "--include-conditional",
        action="store_true",
        help="include conditional rules in host snippets instead of only reporting them",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in argv
    parser = _build_parser()

    try:
        args = parser.parse_args(argv)
        json_mode = json_mode or args.json
        if args.host_out_dir and not args.emit_host_rules:
            raise _ArgumentParseError("--host-out-dir requires --emit-host-rules")

        chain = _build_chain(args)
        emit_path = Path(args.emit) if args.emit else None
        payload = resolve(chain, output=emit_path)
        resolved_payload = (
            payload
            if args.emit
            else _build_resolved_payload(
                payload,
                [
                    (scope_name, str(scope_path))
                    for scope_name, scope_path in chain
                    if scope_path.exists()
                ],
            )
        )
        if args.emit_host_rules:
            host_sync = _load_host_rules_emitter()
            rendered = host_sync.render_platform_payload(
                resolved_payload,
                include_conditional=args.include_conditional,
            )
            host_out_dir = (
                Path(args.host_out_dir).expanduser().resolve()
                if args.host_out_dir
                else None
            )
            if host_out_dir is not None:
                host_sync.write_host_artifacts(rendered, host_out_dir)
                _validate_host_artifacts(host_out_dir, rendered)
            if args.apply_host_rules:
                applied = host_sync.apply_host_artifacts(
                    rendered,
                    codex_path=Path.home() / ".codex" / "rules" / "default.rules",
                    cursor_path=Path.home() / ".cursor" / "cli-config.json",
                    claude_path=Path.home() / ".claude" / "settings.json",
                    droid_path=Path.home() / ".factory" / "settings.json",
                )
            else:
                applied = None
            success_payload = {
                "policy": resolved_payload,
                "host_rules": rendered["policy"],
                "conditional_rules": rendered["conditional_rules"],
                "wrapper_rules": rendered["wrapper_rules"],
                "wrapper_condition_set": rendered["wrapper_condition_set"],
                "include_conditional": args.include_conditional,
                "wrapper_rule_count": len(rendered["wrapper_rules"]),
                "policy_wrapper_bundle": (
                    str(host_out_dir / "policy-wrapper-rules.json")
                    if host_out_dir is not None
                    else None
                ),
                "applied": applied,
                "host_artifacts_written_to": str(host_out_dir)
                if host_out_dir
                else None,
            }
            if json_mode:
                _print_success_json(
                    "policy resolved",
                    success_payload,
                    scope_count=_count_existing_scopes(chain),
                    chain_length=len(chain),
                    emit_path=emit_path.resolve() if emit_path is not None else None,
                    scopes_ordering_assertion_path="result.policy.scopes",
                )
            else:
                print(json.dumps(success_payload, indent=2))
        else:
            success_payload = {"policy": resolved_payload}
            if json_mode:
                _print_success_json(
                    "policy resolved",
                    success_payload,
                    scope_count=_count_existing_scopes(chain),
                    chain_length=len(chain),
                    emit_path=emit_path.resolve() if emit_path is not None else None,
                    scopes_ordering_assertion_path="result.policy.scopes",
                )
            else:
                print(json.dumps(success_payload, indent=2))
        return EXIT_CODE_OK
    except SystemExit as exc:
        if int(exc.code) == EXIT_CODE_OK:
            return EXIT_CODE_OK
        if json_mode:
            _print_failure_json(
                ERROR_CODE_ARG,
                "argument parsing failed",
                {"status": int(exc.code)},
            )
        return EXIT_CODE_ARG
    except _ArgumentParseError as exc:
        if json_mode:
            _print_failure_json(ERROR_CODE_ARG, str(exc))
        else:
            print(str(exc), file=sys.stderr)
        return EXIT_CODE_ARG
    except FileNotFoundError as exc:
        if json_mode:
            _print_failure_json(ERROR_CODE_MISSING, str(exc))
        else:
            print(str(exc), file=sys.stderr)
        return EXIT_CODE_MISSING
    except (TypeError, ValueError) as exc:
        if json_mode:
            _print_failure_json(ERROR_CODE_INVALID, str(exc))
        else:
            print(str(exc), file=sys.stderr)
        return EXIT_CODE_INVALID
    except Exception as exc:  # pragma: no cover
        if json_mode:
            _print_failure_json(
                ERROR_CODE_INTERNAL,
                "internal resolver error",
                {"exception_type": type(exc).__name__, "exception_message": str(exc)},
            )
        else:
            print(f"internal resolver error: {exc}", file=sys.stderr)
        return EXIT_CODE_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
