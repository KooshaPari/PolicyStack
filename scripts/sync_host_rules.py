#!/usr/bin/env python3
"""Emit host-policy artifacts from a resolved policy payload."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.host_rules_managed import (
        JSON_MANAGED_MARKER_END,
        JSON_MANAGED_MARKER_START,
        MANAGED_MARKER_END,
        MANAGED_MARKER_START,
        count_policy_entries,
        ensure_prefix_rules_file,
        find_managed_segment,
        replace_managed_entries,
    )
except ModuleNotFoundError:
    from host_rules_managed import (
        JSON_MANAGED_MARKER_END,
        JSON_MANAGED_MARKER_START,
        MANAGED_MARKER_END,
        MANAGED_MARKER_START,
        count_policy_entries,
        ensure_prefix_rules_file,
        find_managed_segment,
        replace_managed_entries,
    )
from policy_lib import Condition, ConditionGroup, CommandRule, _normalized_command, normalize_payload


COD_EX_DECISION = {"allow": "allow", "request": "prompt", "deny": "forbidden"}


def _safe_command_tokens(pattern: str) -> list[str]:
    try:
        return shlex.split(pattern)
    except ValueError:
        return pattern.split()


def _cursor_pattern(rule: CommandRule) -> str:
    command = _normalized_command(rule.pattern)
    if rule.matcher == "prefix":
        if "*" not in command:
            return f"{command} *"
    if rule.matcher == "exact":
        return command
    return command


def _shell_entry(command: str) -> str:
    return f"Shell({command})"


def _bash_entry(command: str) -> str:
    return f"Bash({command})"


def _wrapper_pattern(rule: CommandRule) -> str:
    return _normalized_command(rule.pattern)


def _collect_required_conditions(
    condition: Condition | ConditionGroup,
) -> list[str]:
    if isinstance(condition, Condition):
        return [condition.name] if condition.required else []

    names: list[str] = []
    for item in condition.items:
        names.extend(_collect_required_conditions(item))
    return names


WRAPPER_SCHEMA_VERSION = 1
VALID_DECISIONS = frozenset({"allow", "request", "deny"})
EXIT_SUCCESS = 0
EXIT_INVALID_INPUT = 2
EXIT_RENDER_FAILURE = 3
EXIT_APPLY_FAILURE = 4
EXIT_INTERNAL_ERROR = 5


def _normalize_decision_default(value: object, fallback: str) -> str:
    if value in VALID_DECISIONS:
        return str(value)
    return fallback


def _render_codex(rule: CommandRule, command: str) -> str:
    tokens = json.dumps(_safe_command_tokens(command))
    decision = COD_EX_DECISION[rule.action]
    return f'prefix_rule(pattern={tokens}, decision="{decision}")'


def _summarize_rule(rule: CommandRule) -> dict[str, Any]:
    return {
        "id": rule.rule_id,
        "source": rule.source,
        "action": rule.action,
        "matcher": rule.matcher,
        "pattern": rule.pattern,
        "on_mismatch": rule.on_mismatch,
        "conditions": rule.conditions.export() if rule.conditions is not None else None,
        "condition_mode": rule.conditions.mode if rule.conditions is not None else None,
    }


def _normalize_for_wrapper(rule: CommandRule, command: str) -> dict[str, Any]:
    if rule.conditions is None:
        return {}
    return {
        "id": rule.rule_id,
        "source": rule.source,
        "action": rule.action,
        "on_mismatch": rule.on_mismatch,
        "matcher": rule.matcher,
        "pattern": rule.pattern,
        "normalized_pattern": _wrapper_pattern(rule),
        "conditions": rule.conditions.export(),
        "platform_action": rule.action,
        "shell_entry": _shell_entry(command),
        "bash_entry": _bash_entry(command),
    }


def render_platform_payload(
    policy_payload: dict[str, Any],
    include_conditional: bool = False,
    cwd: Path | None = None,
) -> dict[str, Any]:
    policy = policy_payload.get("policy", policy_payload)
    resolved_cwd = cwd.resolve() if cwd is not None else Path.cwd().resolve()
    rules = normalize_payload(policy, cwd=resolved_cwd)

    codex_rules = []
    cursor_allow = []
    cursor_deny = []
    claude_allow = []
    claude_deny = []
    claude_ask = []
    droid_allow = []
    droid_request = []
    droid_deny = []
    conditional_rules: list[dict[str, Any]] = []
    wrapper_rules: list[dict[str, Any]] = []
    wrapper_conditions: set[str] = set()

    for rule in rules:
        if rule.conditions is not None:
            conditional_rules.append(_summarize_rule(rule))
            wrapper_rules.append(_normalize_for_wrapper(rule, _cursor_pattern(rule)))
            wrapper_conditions.update(
                _collect_required_conditions(rule.conditions)
            )
            if not include_conditional:
                continue

        command = _cursor_pattern(rule)
        platform_decision = rule.action

        codex_rules.append(_render_codex(rule, command))
        if platform_decision == "allow":
            cursor_allow.append(_shell_entry(command))
            claude_allow.append(_bash_entry(command))
            droid_allow.append(command)
        elif platform_decision == "request":
            cursor_deny.append(_shell_entry(command))
            claude_ask.append(_bash_entry(command))
            droid_request.append(command)
        else:
            cursor_deny.append(_shell_entry(command))
            claude_deny.append(_bash_entry(command))
            droid_deny.append(command)

    return {
        "policy": {
            "cursor": {"allow": cursor_allow, "deny": cursor_deny},
            "claude": {
                "allow": claude_allow,
                "deny": claude_deny,
                "ask": claude_ask,
            },
            "droid": {
                "commandAllowlist": droid_allow,
                "commandRequestlist": droid_request,
                "commandDenylist": droid_deny,
            },
            "codex": {
                "rules": codex_rules,
            },
            "policy_wrapper": {
                "schema_version": WRAPPER_SCHEMA_VERSION,
                "required_conditions": sorted(wrapper_conditions),
                "commands": wrapper_rules,
            },
        },
        "conditional_rules": conditional_rules,
        "wrapper_rules": wrapper_rules,
        "wrapper_condition_set": sorted(wrapper_conditions),
        "unconditional_count": len(rules) - len(conditional_rules),
        "conditional_count": len(conditional_rules),
    }


def write_host_artifacts(payload: dict[str, Any], out_dir: Path | None) -> None:
    if out_dir is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    policy = payload["policy"]

    (out_dir / "codex.rules").write_text(
        "\n".join(policy["codex"]["rules"]) + "\n",
        encoding="utf-8",
    )
    (out_dir / "cursor.cli-config.json").write_text(
        json.dumps({"permissions": policy["cursor"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "claude.settings.json").write_text(
        json.dumps({"permissions": policy["claude"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "factory-droid.settings.json").write_text(
        json.dumps(policy["droid"], indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "policy-wrapper-rules.json").write_text(
        json.dumps(policy["policy_wrapper"], indent=2) + "\n",
        encoding="utf-8",
    )
    _write_wrapper_manifest(out_dir, policy["policy_wrapper"])


def _write_wrapper_manifest(out_dir: Path, wrapper_payload: dict[str, Any]) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    missing_policy_default = _normalize_decision_default(
        wrapper_payload.get("missing_policy_default"), "allow"
    )
    malformed_bundle_default = _normalize_decision_default(
        wrapper_payload.get("malformed_bundle_default"), missing_policy_default
    )
    condition_eval_default = _normalize_decision_default(
        wrapper_payload.get("condition_eval_default"), "request"
    )
    manifest = {
        "schema_version": wrapper_payload.get("schema_version"),
        "bundle_path": str(out_dir / "policy-wrapper-rules.json"),
        "bundle_relative": "policy-wrapper-rules.json",
        "dispatch_script": str(
            repo_root / "wrappers" / "policy-wrapper-dispatch.sh"
        ),
        "dispatch_command": [
            str(repo_root / "wrappers" / "policy-wrapper-dispatch.sh"),
            "--json",
            "--bundle",
            str(out_dir / "policy-wrapper-rules.json"),
            "--command",
            "{command}",
            "--cwd",
            "{cwd}",
            "--missing-policy-default",
            missing_policy_default,
            "--malformed-bundle-default",
            malformed_bundle_default,
            "--condition-eval-error-default",
            condition_eval_default,
        ],
        "required_conditions": wrapper_payload.get("required_conditions", []),
        "wrapper_rule_count": len(wrapper_payload.get("commands", [])),
        "fallback_missing_policy": missing_policy_default,
        "fallback_malformed_bundle": malformed_bundle_default,
        "fallback_condition_eval_error": condition_eval_default,
    }
    (out_dir / "policy-wrapper-dispatch.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON ({exc.msg})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: host config must be a JSON object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_list_field(container: dict[str, Any], key: str, path: Path) -> list[Any]:
    value = container.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{path}: field '{key}' must be a JSON array")
    return list(value)


def _apply_codex_rules(path: Path, generated: list[str]) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    return ensure_prefix_rules_file(path, generated)


def _apply_cursor_rules(path: Path, payload: dict[str, Any]) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_json(path)
    permissions_raw = data.get("permissions")
    if permissions_raw is None:
        permissions: dict[str, Any] = {}
    elif isinstance(permissions_raw, dict):
        permissions = dict(permissions_raw)
    else:
        raise ValueError(f"{path}: field 'permissions' must be a JSON object")
    old_allow = _read_list_field(permissions, "allow", path)
    old_deny = _read_list_field(permissions, "deny", path)
    permissions["allow"] = replace_managed_entries(old_allow, payload["allow"], path, "allow")
    permissions["deny"] = replace_managed_entries(old_deny, payload["deny"], path, "deny")
    data["permissions"] = permissions
    _write_json(path, data)
    return count_policy_entries(old_allow) + count_policy_entries(old_deny), (
        count_policy_entries(permissions["allow"]) + count_policy_entries(permissions["deny"])
    )


def _apply_claude_rules(path: Path, payload: dict[str, Any]) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_json(path)
    permissions_raw = data.get("permissions")
    if permissions_raw is None:
        permissions: dict[str, Any] = {}
    elif isinstance(permissions_raw, dict):
        permissions = dict(permissions_raw)
    else:
        raise ValueError(f"{path}: field 'permissions' must be a JSON object")
    old_allow = _read_list_field(permissions, "allow", path)
    old_deny = _read_list_field(permissions, "deny", path)
    old_ask = _read_list_field(permissions, "ask", path)
    permissions["allow"] = replace_managed_entries(old_allow, payload["allow"], path, "allow")
    permissions["deny"] = replace_managed_entries(old_deny, payload["deny"], path, "deny")
    permissions["ask"] = replace_managed_entries(old_ask, payload["ask"], path, "ask")
    data["permissions"] = permissions
    _write_json(path, data)
    return (
        count_policy_entries(old_allow)
        + count_policy_entries(old_deny)
        + count_policy_entries(old_ask),
        count_policy_entries(permissions["allow"])
        + count_policy_entries(permissions["deny"])
        + count_policy_entries(permissions["ask"]),
    )


def _apply_droid_rules(path: Path, payload: dict[str, Any]) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_json(path)
    old_allow = _read_list_field(data, "commandAllowlist", path)
    old_request = _read_list_field(data, "commandRequestlist", path)
    old_deny = _read_list_field(data, "commandDenylist", path)
    data["commandAllowlist"] = replace_managed_entries(
        old_allow, payload["commandAllowlist"], path, "commandAllowlist"
    )
    data["commandRequestlist"] = replace_managed_entries(
        old_request, payload["commandRequestlist"], path, "commandRequestlist"
    )
    data["commandDenylist"] = replace_managed_entries(
        old_deny, payload["commandDenylist"], path, "commandDenylist"
    )
    _write_json(path, data)
    return (
        count_policy_entries(old_allow)
        + count_policy_entries(old_request)
        + count_policy_entries(old_deny),
        count_policy_entries(data["commandAllowlist"])
        + count_policy_entries(data["commandRequestlist"])
        + count_policy_entries(data["commandDenylist"]),
    )


def apply_host_artifacts(
    payload: dict[str, Any],
    codex_path: Path | None = None,
    cursor_path: Path | None = None,
    claude_path: Path | None = None,
    droid_path: Path | None = None,
) -> dict[str, Any]:
    policy = payload["policy"]
    result: dict[str, Any] = {
        "applied": {
            "codex": None,
            "cursor": None,
            "claude": None,
            "droid": None,
        }
    }

    if codex_path is not None:
        before, after = _apply_codex_rules(codex_path, policy["codex"]["rules"])
        result["applied"]["codex"] = {"path": str(codex_path), "before": before, "after": after}

    if cursor_path is not None:
        before, after = _apply_cursor_rules(cursor_path, policy["cursor"])
        result["applied"]["cursor"] = {"path": str(cursor_path), "before": before, "after": after}

    if claude_path is not None:
        before, after = _apply_claude_rules(claude_path, policy["claude"])
        result["applied"]["claude"] = {"path": str(claude_path), "before": before, "after": after}

    if droid_path is not None:
        before, after = _apply_droid_rules(droid_path, policy["droid"])
        result["applied"]["droid"] = {"path": str(droid_path), "before": before, "after": after}

    return result


def load_policy(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: resolved policy payload must be a JSON object")
    return data


def _validate_policy_json_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise ValueError(f"--policy-json does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"--policy-json must be a file: {path}")
    try:
        with path.open("r", encoding="utf-8"):
            pass
    except OSError as exc:
        detail = exc.strerror or str(exc)
        raise ValueError(f"--policy-json is not readable: {path} ({detail})") from exc
    return path.resolve()


def _validate_cwd_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise ValueError(f"--cwd does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"--cwd must be a directory: {path}")
    return path.resolve()


def _emit_failure(message: str, exit_code: int, json_mode: bool) -> int:
    if json_mode:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": exit_code,
                        "message": message,
                    },
                }
            )
        )
    else:
        print(f"error: {message}", file=sys.stderr)
    return exit_code


def _count_platform_rules(policy: dict[str, Any], platform: str) -> int:
    if platform == "codex":
        return len(policy["codex"]["rules"])
    if platform == "cursor":
        return len(policy["cursor"]["allow"]) + len(policy["cursor"]["deny"])
    if platform == "claude":
        claude_policy = policy["claude"]
        return len(claude_policy["allow"]) + len(claude_policy["deny"]) + len(claude_policy["ask"])
    if platform == "droid":
        droid_policy = policy["droid"]
        return (
            len(droid_policy["commandAllowlist"])
            + len(droid_policy["commandRequestlist"])
            + len(droid_policy["commandDenylist"])
        )
    raise ValueError(f"unknown platform: {platform}")


def _build_success_entries(
    policy: dict[str, Any],
    mode: str,
    codex_path: Path,
    cursor_path: Path,
    claude_path: Path,
    droid_path: Path,
) -> list[dict[str, Any]]:
    entries = [
        ("codex", codex_path),
        ("cursor", cursor_path),
        ("claude", claude_path),
        ("droid", droid_path),
    ]
    return [
        {
            "platform": platform,
            "target_path": str(path),
            "rule_count": _count_platform_rules(policy, platform),
            "mode": mode,
            "had_managed_segment_before": _had_managed_segment_before(platform, path),
            "managed_segment_length_after": _managed_segment_length_after(policy, platform),
        }
        for platform, path in entries
    ]


def _managed_segment_length_after(policy: dict[str, Any], platform: str) -> int:
    if platform == "codex":
        return len(policy["codex"]["rules"])
    if platform == "cursor":
        return len(policy["cursor"]["allow"]) + len(policy["cursor"]["deny"])
    if platform == "claude":
        claude_policy = policy["claude"]
        return len(claude_policy["allow"]) + len(claude_policy["deny"]) + len(claude_policy["ask"])
    if platform == "droid":
        droid_policy = policy["droid"]
        return (
            len(droid_policy["commandAllowlist"])
            + len(droid_policy["commandRequestlist"])
            + len(droid_policy["commandDenylist"])
        )
    raise ValueError(f"unknown platform: {platform}")


def _has_json_managed_segment(
    sequence: list[Any],
    *,
    path: Path,
    key: str,
) -> bool:
    start, end = find_managed_segment(
        sequence,
        JSON_MANAGED_MARKER_START,
        JSON_MANAGED_MARKER_END,
        path=path,
        key=key,
    )
    return start is not None and end is not None


def _had_managed_segment_before(platform: str, path: Path) -> bool:
    if not path.exists():
        return False
    if platform == "codex":
        existing = path.read_text(encoding="utf-8").splitlines()
        start, end = find_managed_segment(
            existing,
            MANAGED_MARKER_START,
            MANAGED_MARKER_END,
            path=path,
            key="codex",
        )
        return start is not None and end is not None

    data = _load_json(path)
    if platform == "cursor":
        permissions = data.get("permissions", {})
        if not isinstance(permissions, dict):
            raise ValueError(f"{path}: field 'permissions' must be a JSON object")
        allow = _read_list_field(permissions, "allow", path)
        deny = _read_list_field(permissions, "deny", path)
        return _has_json_managed_segment(allow, path=path, key="allow") or _has_json_managed_segment(
            deny, path=path, key="deny"
        )
    if platform == "claude":
        permissions = data.get("permissions", {})
        if not isinstance(permissions, dict):
            raise ValueError(f"{path}: field 'permissions' must be a JSON object")
        allow = _read_list_field(permissions, "allow", path)
        deny = _read_list_field(permissions, "deny", path)
        ask = _read_list_field(permissions, "ask", path)
        return (
            _has_json_managed_segment(allow, path=path, key="allow")
            or _has_json_managed_segment(deny, path=path, key="deny")
            or _has_json_managed_segment(ask, path=path, key="ask")
        )
    if platform == "droid":
        allow = _read_list_field(data, "commandAllowlist", path)
        request = _read_list_field(data, "commandRequestlist", path)
        deny = _read_list_field(data, "commandDenylist", path)
        return (
            _has_json_managed_segment(allow, path=path, key="commandAllowlist")
            or _has_json_managed_segment(request, path=path, key="commandRequestlist")
            or _has_json_managed_segment(deny, path=path, key="commandDenylist")
        )
    raise ValueError(f"unknown platform: {platform}")


def _build_text_summary(
    mode: str,
    unconditional_count: int,
    conditional_count: int,
    success_entries: list[dict[str, Any]],
) -> str:
    total_count = unconditional_count + conditional_count
    lines = [
        f"sync_host_rules mode={mode} unconditional={unconditional_count} conditional={conditional_count} total={total_count}"
    ]
    for entry in success_entries:
        lines.append(
            "platform={platform} mode={mode} target_path={target_path} rule_count={rule_count}".format(
                platform=entry["platform"],
                mode=entry["mode"],
                target_path=entry["target_path"],
                rule_count=entry["rule_count"],
            )
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit host-specific command policy snippets from a resolved policy JSON."
    )
    parser.add_argument("--policy-json", required=True, help="Resolved policy JSON file")
    parser.add_argument(
        "--cwd",
        default=None,
        help="Deterministic working directory for policy normalization/rendering",
    )
    parser.add_argument(
        "--include-conditional",
        action="store_true",
        help="Include conditional rules in host rule outputs in addition to reporting them.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Write artifacts into this directory",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply generated policies into live host files",
    )
    parser.add_argument(
        "--codex-rules",
        default=str(Path.home() / ".codex" / "rules" / "default.rules"),
        help="path to Codex default rules file",
    )
    parser.add_argument(
        "--cursor-config",
        default=str(Path.home() / ".cursor" / "cli-config.json"),
        help="path to Cursor CLI config",
    )
    parser.add_argument(
        "--claude-settings",
        default=str(Path.home() / ".claude" / "settings.json"),
        help="path to Claude settings",
    )
    parser.add_argument(
        "--factory-settings",
        default=str(Path.home() / ".factory" / "settings.json"),
        help="path to factory-droid settings",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output for failure responses.",
    )
    args = parser.parse_args()

    try:
        policy_path = _validate_policy_json_path(args.policy_json)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        render_cwd = _validate_cwd_path(args.cwd) if args.cwd else Path.cwd().resolve()
    except ValueError as exc:
        parser.error(str(exc))

    try:
        payload = load_policy(policy_path)
    except Exception as exc:
        return _emit_failure(
            f"invalid input: {exc}",
            EXIT_INVALID_INPUT,
            args.json,
        )

    try:
        rendered = render_platform_payload(
            payload,
            include_conditional=args.include_conditional,
            cwd=render_cwd,
        )
    except Exception as exc:
        return _emit_failure(
            f"render failed: {exc}",
            EXIT_RENDER_FAILURE,
            args.json,
        )

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else None
    try:
        write_host_artifacts(rendered, out_dir)
    except Exception as exc:
        return _emit_failure(
            f"write failed: {exc}",
            EXIT_APPLY_FAILURE,
            args.json,
        )

    codex_target = Path(args.codex_rules).expanduser().resolve()
    cursor_target = Path(args.cursor_config).expanduser().resolve()
    claude_target = Path(args.claude_settings).expanduser().resolve()
    droid_target = Path(args.factory_settings).expanduser().resolve()

    apply_result = None
    mode = "apply" if args.apply else "preview"
    if args.apply:
        try:
            codex_target.parent.mkdir(parents=True, exist_ok=True)
            apply_result = apply_host_artifacts(
                rendered,
                codex_path=codex_target,
                cursor_path=cursor_target,
                claude_path=claude_target,
                droid_path=droid_target,
            )
        except Exception as exc:
            return _emit_failure(
                f"apply failed: {exc}",
                EXIT_APPLY_FAILURE,
                args.json,
            )

    try:
        success_entries = _build_success_entries(
            rendered["policy"],
            mode=mode,
            codex_path=codex_target,
            cursor_path=cursor_target,
            claude_path=claude_target,
            droid_path=droid_target,
        )
        text_summary = _build_text_summary(
            mode=mode,
            unconditional_count=rendered["unconditional_count"],
            conditional_count=rendered["conditional_count"],
            success_entries=success_entries,
        )
        manifest = {
            "conditional_rules": rendered["conditional_rules"],
            "host_rules": rendered["policy"],
            "wrapper_rules": rendered["wrapper_rules"],
            "wrapper_condition_set": rendered["wrapper_condition_set"],
            "applied": apply_result,
            "summary": {
                "mode": mode,
                "unconditional_rules": rendered["unconditional_count"],
                "conditional_rules": rendered["conditional_count"],
                "written_to": str(out_dir) if out_dir else None,
            },
            "text_summary": text_summary,
        }
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "mode": mode,
                        "platforms": success_entries,
                        "summary": {
                            "unconditional_rules": rendered["unconditional_count"],
                            "conditional_rules": rendered["conditional_count"],
                            "total_rules": rendered["unconditional_count"]
                            + rendered["conditional_count"],
                        },
                    }
                )
            )
        else:
            print(text_summary)
            print(json.dumps(manifest, indent=2))
    except Exception as exc:
        return _emit_failure(
            f"internal error: {exc}",
            EXIT_INTERNAL_ERROR,
            args.json,
        )

    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
