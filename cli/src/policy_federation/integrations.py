"""Installer helpers for local harness runtime integration."""
from __future__ import annotations

from pathlib import Path

from .runtime_config_patches import (
    _backup_file,
    patch_claude_settings,
    patch_codex_config_json,
    patch_codex_toml,
    patch_cursor_config,
    patch_factory_config,
    unpatch_claude_settings,
    unpatch_codex_config_json,
    unpatch_codex_toml,
    unpatch_cursor_config,
    unpatch_factory_config,
)
from .runtime_launchers import install_launcher_wrappers, uninstall_launcher_wrappers


def install_runtime_integrations(repo_root: Path, home: Path) -> dict:
    """Install runtime wrappers and patch local harness configs."""
    runtime_dir = repo_root / "scripts" / "runtime"
    cursor_bin = home / ".cursor" / "bin"
    factory_bin = home / ".factory" / "bin"
    codex_bin = home / ".codex" / "bin"
    claude_bin = home / ".claude" / "bin"

    wrapper_map = {
        cursor_bin / "cursor_exec_guard.sh": runtime_dir / "cursor_exec_guard.sh",
        cursor_bin / "cursor_write_guard.sh": runtime_dir / "cursor_write_guard.sh",
        cursor_bin / "cursor_network_guard.sh": runtime_dir / "cursor_network_guard.sh",
        factory_bin / "factory_exec_guard.sh": runtime_dir / "factory_exec_guard.sh",
        factory_bin / "factory_write_guard.sh": runtime_dir / "factory_write_guard.sh",
        factory_bin / "factory_network_guard.sh": runtime_dir / "factory_network_guard.sh",
        codex_bin / "codex_exec_guard.sh": runtime_dir / "codex_exec_guard.sh",
        codex_bin / "codex_write_guard.sh": runtime_dir / "codex_write_guard.sh",
        codex_bin / "codex_network_guard.sh": runtime_dir / "codex_network_guard.sh",
        claude_bin / "claude_exec_guard.sh": runtime_dir / "claude_exec_guard.sh",
        claude_bin / "claude_write_guard.sh": runtime_dir / "claude_write_guard.sh",
        claude_bin / "claude_network_guard.sh": runtime_dir / "claude_network_guard.sh",
        claude_bin / "claude_pretool_guard.sh": runtime_dir / "claude_pretool_hook.py",
    }

    for destination, source in wrapper_map.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f'exec "{source}" "$@"\n',
            encoding="utf-8",
        )
        destination.chmod(0o755)

    cursor_config = home / ".cursor" / "cli-config.json"
    factory_settings = home / ".factory" / "settings.json"
    codex_config = home / ".codex" / "config.json"
    codex_toml = home / ".codex" / "config.toml"
    claude_settings = home / ".claude" / "settings.json"

    backups = {
        "cursor": str(_backup_file(cursor_config)) if cursor_config.exists() else None,
        "factory": str(_backup_file(factory_settings)) if factory_settings.exists() else None,
        "codex_json": str(_backup_file(codex_config)) if codex_config.exists() else None,
        "codex_toml": str(_backup_file(codex_toml)) if codex_toml.exists() else None,
        "claude": str(_backup_file(claude_settings)) if claude_settings.exists() else None,
    }

    patch_cursor_config(cursor_config, cursor_bin, runtime_dir / "cursor_runtime_manifest.json")
    patch_factory_config(
        factory_settings,
        factory_bin,
        runtime_dir / "factory_runtime_manifest.json",
    )
    patch_codex_config_json(
        codex_config,
        codex_bin,
        runtime_dir / "codex_runtime_manifest.json",
    )
    patch_codex_toml(
        codex_toml,
        codex_bin,
        runtime_dir / "codex_runtime_manifest.json",
    )
    patch_claude_settings(
        claude_settings,
        claude_bin,
        runtime_dir / "claude_runtime_manifest.json",
    )
    launcher_result = install_launcher_wrappers(home)

    return {
        "status": "installed",
        "runtime_dir": str(runtime_dir),
        "wrappers_installed": {
            str(path): str(target) for path, target in wrapper_map.items()
        },
        "launcher_wrappers": launcher_result["installed"],
        "backups": backups,
        "launcher_backups": launcher_result["backups"],
        "patched_files": {
            "cursor": str(cursor_config),
            "factory": str(factory_settings),
            "codex_json": str(codex_config),
            "codex_toml": str(codex_toml),
            "claude": str(claude_settings),
        },
    }


def uninstall_runtime_integrations(repo_root: Path, home: Path) -> dict:
    runtime_dir = repo_root / "scripts" / "runtime"
    cursor_bin = home / ".cursor" / "bin"
    factory_bin = home / ".factory" / "bin"
    codex_bin = home / ".codex" / "bin"
    claude_bin = home / ".claude" / "bin"

    wrappers = [
        cursor_bin / "cursor_exec_guard.sh",
        cursor_bin / "cursor_write_guard.sh",
        cursor_bin / "cursor_network_guard.sh",
        factory_bin / "factory_exec_guard.sh",
        factory_bin / "factory_write_guard.sh",
        factory_bin / "factory_network_guard.sh",
        codex_bin / "codex_exec_guard.sh",
        codex_bin / "codex_write_guard.sh",
        codex_bin / "codex_network_guard.sh",
        claude_bin / "claude_exec_guard.sh",
        claude_bin / "claude_write_guard.sh",
        claude_bin / "claude_network_guard.sh",
        claude_bin / "claude_pretool_guard.sh",
    ]

    removed_wrappers: list[str] = []
    for wrapper in wrappers:
        if wrapper.exists():
            wrapper.unlink()
            removed_wrappers.append(str(wrapper))

    cursor_config = home / ".cursor" / "cli-config.json"
    factory_settings = home / ".factory" / "settings.json"
    codex_config = home / ".codex" / "config.json"
    codex_toml = home / ".codex" / "config.toml"
    claude_settings = home / ".claude" / "settings.json"

    unpatch_cursor_config(cursor_config, cursor_bin)
    unpatch_factory_config(factory_settings, factory_bin)
    unpatch_codex_config_json(codex_config)
    unpatch_codex_toml(codex_toml)
    unpatch_claude_settings(claude_settings)
    launcher_result = uninstall_launcher_wrappers(home)

    return {
        "status": "uninstalled",
        "runtime_dir": str(runtime_dir),
        "removed_wrappers": removed_wrappers,
        "launcher_restore": launcher_result,
        "patched_files": {
            "cursor": str(cursor_config),
            "factory": str(factory_settings),
            "codex_json": str(codex_config),
            "codex_toml": str(codex_toml),
            "claude": str(claude_settings),
        },
    }
