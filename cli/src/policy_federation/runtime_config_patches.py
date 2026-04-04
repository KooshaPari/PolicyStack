"""Config patching helpers for local harness runtime integration."""
from __future__ import annotations

import datetime
import json
import shutil
from pathlib import Path


INSTALL_MARKER_START = "# policy-federation runtime start"
INSTALL_MARKER_END = "# policy-federation runtime end"
CLAUDE_PRETOOL_COMMAND = "\"$HOME/.claude/bin/claude_pretool_guard.sh\""


def _timestamp() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y%m%d-%H%M%S")


def _backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup_path = path.with_name(f"{path.name}.bak.{_timestamp()}")
    shutil.copy2(path, backup_path)
    return backup_path


def _load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return {} if default is None else dict(default)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _ensure_unique(items: list[str], new_items: list[str]) -> list[str]:
    seen = set(items)
    merged = list(items)
    for item in new_items:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _append_unique_mapping(items: list[dict], new_item: dict) -> list[dict]:
    matcher = new_item.get("matcher")
    if matcher is None:
        if new_item in items:
            return items
        return [*items, new_item]

    merged: list[dict] = []
    updated = False
    for item in items:
        if item.get("matcher") != matcher:
            merged.append(item)
            continue
        merged_hooks = [
            hook
            for hook in item.get("hooks", [])
            if hook.get("command") != CLAUDE_PRETOOL_COMMAND
        ]
        for new_hook in new_item.get("hooks", []):
            if new_hook in merged_hooks:
                continue
            merged_hooks.append(new_hook)
        merged_item = dict(item)
        merged_item["hooks"] = merged_hooks
        merged.append(merged_item)
        updated = True

    if not updated:
        merged.append(new_item)
    return merged


def _is_managed_claude_hook(entry: dict) -> bool:
    hooks = entry.get("hooks") or []
    return any(hook.get("command") == CLAUDE_PRETOOL_COMMAND for hook in hooks)


def _remove_values(items: list[str], remove_items: list[str]) -> list[str]:
    remove_set = set(remove_items)
    return [item for item in items if item not in remove_set]


def patch_cursor_config(cursor_config_path: Path, wrapper_root: Path, manifest_path: Path) -> None:
    payload = _load_json(
        cursor_config_path,
        default={"permissions": {"allow": [], "deny": []}, "version": 1},
    )
    permissions = payload.setdefault("permissions", {})
    allow = permissions.setdefault("allow", [])

    allow_entries = [
        f"Shell({wrapper_root / 'cursor_exec_guard.sh'})",
        f"Shell({wrapper_root / 'cursor_exec_guard.sh'}:*)",
        f"Shell({wrapper_root / 'cursor_write_guard.sh'})",
        f"Shell({wrapper_root / 'cursor_write_guard.sh'}:*)",
        f"Shell({wrapper_root / 'cursor_network_guard.sh'})",
        f"Shell({wrapper_root / 'cursor_network_guard.sh'}:*)",
    ]
    permissions["allow"] = _ensure_unique(allow, allow_entries)
    payload["policyRuntime"] = {
        "managedBy": "agentops-policy-federation",
        "manifest": str(manifest_path),
        "wrappers": {
            "exec": str(wrapper_root / "cursor_exec_guard.sh"),
            "write_check": str(wrapper_root / "cursor_write_guard.sh"),
            "network_check": str(wrapper_root / "cursor_network_guard.sh"),
        },
    }
    _write_json(cursor_config_path, payload)


def patch_factory_config(
    factory_settings_path: Path,
    wrapper_root: Path,
    manifest_path: Path,
) -> None:
    payload = _load_json(factory_settings_path, default={})
    allowlist = payload.setdefault("commandAllowlist", [])
    allow_entries = [
        str(wrapper_root / "factory_exec_guard.sh"),
        str(wrapper_root / "factory_write_guard.sh"),
        str(wrapper_root / "factory_network_guard.sh"),
    ]
    payload["commandAllowlist"] = _ensure_unique(allowlist, allow_entries)
    payload["policyRuntime"] = {
        "managedBy": "agentops-policy-federation",
        "manifest": str(manifest_path),
        "wrappers": {
            "exec": str(wrapper_root / "factory_exec_guard.sh"),
            "write_check": str(wrapper_root / "factory_write_guard.sh"),
            "network_check": str(wrapper_root / "factory_network_guard.sh"),
        },
    }
    _write_json(factory_settings_path, payload)


def patch_codex_config_json(
    codex_config_path: Path,
    wrapper_root: Path,
    manifest_path: Path,
) -> None:
    payload = _load_json(codex_config_path, default={})
    payload["policyRuntime"] = {
        "managedBy": "agentops-policy-federation",
        "manifest": str(manifest_path),
        "wrappers": {
            "exec": str(wrapper_root / "codex_exec_guard.sh"),
            "write_check": str(wrapper_root / "codex_write_guard.sh"),
            "network_check": str(wrapper_root / "codex_network_guard.sh"),
        },
    }
    _write_json(codex_config_path, payload)


def patch_codex_toml(codex_toml_path: Path, wrapper_root: Path, manifest_path: Path) -> None:
    codex_toml_path.parent.mkdir(parents=True, exist_ok=True)
    current = codex_toml_path.read_text(encoding="utf-8") if codex_toml_path.exists() else ""
    if INSTALL_MARKER_START in current and INSTALL_MARKER_END in current:
        prefix = current.split(INSTALL_MARKER_START, 1)[0].rstrip()
    else:
        prefix = current.rstrip()

    block = (
        f"{INSTALL_MARKER_START}\n"
        "[policy_runtime]\n"
        'managed_by = "agentops-policy-federation"\n'
        f'manifest = "{manifest_path}"\n'
        f'exec_wrapper = "{wrapper_root / "codex_exec_guard.sh"}"\n'
        f'write_wrapper = "{wrapper_root / "codex_write_guard.sh"}"\n'
        f'network_wrapper = "{wrapper_root / "codex_network_guard.sh"}"\n'
        f"{INSTALL_MARKER_END}\n"
    )
    new_text = f"{prefix}\n\n{block}" if prefix else block
    codex_toml_path.write_text(new_text, encoding="utf-8")


def patch_claude_settings(
    claude_settings_path: Path,
    wrapper_root: Path,
    manifest_path: Path,
) -> None:
    payload = _load_json(
        claude_settings_path,
        default={"$schema": "https://json.schemastore.org/claude-code-settings.json"},
    )
    hooks = payload.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("PreToolUse", [])
    pre_tool_use = [entry for entry in pre_tool_use if not _is_managed_claude_hook(entry)]

    managed_entries = [
        {
            "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit",
            "hooks": [{"type": "command", "command": CLAUDE_PRETOOL_COMMAND}],
        },
        {
            "matcher": "WebFetch|WebSearch",
            "hooks": [{"type": "command", "command": CLAUDE_PRETOOL_COMMAND}],
        },
    ]
    for entry in managed_entries:
        pre_tool_use = _append_unique_mapping(pre_tool_use, entry)
    hooks["PreToolUse"] = pre_tool_use

    payload["policyRuntime"] = {
        "managedBy": "agentops-policy-federation",
        "manifest": str(manifest_path),
        "hooks": {"pretool": CLAUDE_PRETOOL_COMMAND},
        "wrappers": {
            "exec": str(wrapper_root / "claude_exec_guard.sh"),
            "write_check": str(wrapper_root / "claude_write_guard.sh"),
            "network_check": str(wrapper_root / "claude_network_guard.sh"),
            "pretool_hook": str(wrapper_root / "claude_pretool_guard.sh"),
        },
    }
    _write_json(claude_settings_path, payload)


def unpatch_cursor_config(cursor_config_path: Path, wrapper_root: Path) -> None:
    if not cursor_config_path.exists():
        return
    payload = _load_json(cursor_config_path, default={})
    permissions = payload.get("permissions") or {}
    allow = permissions.get("allow") or []
    remove_entries = [
        f"Shell({wrapper_root / 'cursor_exec_guard.sh'})",
        f"Shell({wrapper_root / 'cursor_exec_guard.sh'}:*)",
        f"Shell({wrapper_root / 'cursor_write_guard.sh'})",
        f"Shell({wrapper_root / 'cursor_write_guard.sh'}:*)",
        f"Shell({wrapper_root / 'cursor_network_guard.sh'})",
        f"Shell({wrapper_root / 'cursor_network_guard.sh'}:*)",
    ]
    permissions["allow"] = _remove_values(allow, remove_entries)
    payload["permissions"] = permissions
    payload.pop("policyRuntime", None)
    _write_json(cursor_config_path, payload)


def unpatch_factory_config(factory_settings_path: Path, wrapper_root: Path) -> None:
    if not factory_settings_path.exists():
        return
    payload = _load_json(factory_settings_path, default={})
    allowlist = payload.get("commandAllowlist") or []
    remove_entries = [
        str(wrapper_root / "factory_exec_guard.sh"),
        str(wrapper_root / "factory_write_guard.sh"),
        str(wrapper_root / "factory_network_guard.sh"),
    ]
    payload["commandAllowlist"] = _remove_values(allowlist, remove_entries)
    payload.pop("policyRuntime", None)
    _write_json(factory_settings_path, payload)


def unpatch_codex_config_json(codex_config_path: Path) -> None:
    if not codex_config_path.exists():
        return
    payload = _load_json(codex_config_path, default={})
    payload.pop("policyRuntime", None)
    _write_json(codex_config_path, payload)


def unpatch_codex_toml(codex_toml_path: Path) -> None:
    if not codex_toml_path.exists():
        return
    current = codex_toml_path.read_text(encoding="utf-8")
    if INSTALL_MARKER_START not in current or INSTALL_MARKER_END not in current:
        return
    prefix = current.split(INSTALL_MARKER_START, 1)[0].rstrip()
    codex_toml_path.write_text(f"{prefix}\n" if prefix else "", encoding="utf-8")


def unpatch_claude_settings(claude_settings_path: Path) -> None:
    if not claude_settings_path.exists():
        return
    payload = _load_json(claude_settings_path, default={})
    hooks = payload.get("hooks") or {}
    pre_tool_use = hooks.get("PreToolUse") or []
    filtered_pre_tool_use: list[dict] = []
    for entry in pre_tool_use:
        if not _is_managed_claude_hook(entry):
            filtered_pre_tool_use.append(entry)
            continue
        remaining_hooks = [
            hook
            for hook in entry.get("hooks", [])
            if hook.get("command") != CLAUDE_PRETOOL_COMMAND
        ]
        if not remaining_hooks:
            continue
        stripped_entry = dict(entry)
        stripped_entry["hooks"] = remaining_hooks
        filtered_pre_tool_use.append(stripped_entry)
    hooks["PreToolUse"] = filtered_pre_tool_use
    payload["hooks"] = hooks
    payload.pop("policyRuntime", None)
    _write_json(claude_settings_path, payload)

