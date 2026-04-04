"""Launcher wrapper helpers for local harness runtime integration."""
from __future__ import annotations

from pathlib import Path

from .constants import DEFAULT_ASK_MODE


LAUNCHER_MARKER = "# agentops-policy-federation launcher wrapper"


def _launcher_backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.policy-federation.real")


def _resolve_launcher_target(path: Path, backup_target: Path) -> Path:
    if backup_target.exists():
        return backup_target
    if path.exists():
        path.rename(backup_target)
        return backup_target
    return backup_target


def _write_launcher_wrapper(
    launcher_path: Path,
    target_path: Path,
    harness: str,
    repo_name: str,
    task_domain: str,
    fallback_command: str | None = None,
) -> None:
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_block = (
        "if [ ! -x \"$TARGET\" ] && command -v "
        f'"{fallback_command}" >/dev/null 2>&1; then\n'
        f'  exec "{fallback_command}" "$@"\n'
        "fi\n"
    ) if fallback_command else ""
    audit_log_default = "$HOME/.policy-federation/audit.jsonl"
    launcher_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"{LAUNCHER_MARKER}\n"
        "infer_repo_name_from_pwd() {\n"
        "  local cwd=\"$1\"\n"
        "  local IFS='/'\n"
        "  local -a parts\n"
        "  read -r -a parts <<< \"$cwd\"\n"
        "  for ((i=0; i<${#parts[@]}; i++)); do\n"
        "    case \"${parts[i]}\" in\n"
        "      worktrees)\n"
        "        if (( i + 1 < ${#parts[@]} )); then\n"
        "          printf '%s\\n' \"${parts[i+1]}\"\n"
        "          return 0\n"
        "        fi\n"
        "        ;;\n"
        "      PROJECT-wtrees)\n"
        "        if (( i > 0 )); then\n"
        "          printf '%s\\n' \"${parts[i-1]}\"\n"
        "          return 0\n"
        "        fi\n"
        "        ;;\n"
        "      *-wtrees)\n"
        "        printf '%s\\n' \"${parts[i]%-wtrees}\"\n"
        "        return 0\n"
        "        ;;\n"
        "      *-worktrees)\n"
        "        printf '%s\\n' \"${parts[i]%-worktrees}\"\n"
        "        return 0\n"
        "        ;;\n"
        "    esac\n"
        "  done\n"
        "  basename \"$cwd\"\n"
        "}\n"
        f'export POLICY_HARNESS="{harness}"\n'
        f'export POLICY_REPO="${{POLICY_REPO:-$(infer_repo_name_from_pwd \"$PWD\")}}"\n'
        f'export POLICY_TASK_DOMAIN="${{POLICY_TASK_DOMAIN:-{task_domain}}}"\n'
        f'export POLICY_ASK_MODE="${{POLICY_ASK_MODE:-{DEFAULT_ASK_MODE}}}"\n'
        f'export POLICY_AUDIT_LOG_PATH="${{POLICY_AUDIT_LOG_PATH:-{audit_log_default}}}"\n'
        f'TARGET="{target_path}"\n'
        f"{fallback_block}"
        f'exec "$TARGET" "$@"\n',
        encoding="utf-8",
    )
    launcher_path.chmod(0o755)


def install_launcher_wrappers(
    home: Path,
    repo_name: str = "thegent",
    task_domain: str = "devops",
) -> dict:
    launcher_specs = {
        home / ".local" / "bin" / "codex": {
            "target": Path("/opt/homebrew/bin/codex"),
            "harness": "codex",
            "fallback": "codex",
        },
        home / ".local" / "bin" / "cursor": {
            "target": home / ".local" / "bin" / "cursor",
            "harness": "cursor-agent",
            "fallback": "cursor",
        },
        home / ".local" / "bin" / "droid": {
            "target": home / ".local" / "share" / "uv" / "tools" / "thegent" / "bin" / "droid",
            "harness": "factory-droid",
            "fallback": "droid",
        },
        home / ".local" / "bin" / "claude": {
            "target": Path("/opt/homebrew/bin/claude"),
            "harness": "claude-code",
            "fallback": "claude",
        },
    }

    backups: dict[str, str | None] = {}
    installed: dict[str, str] = {}
    for launcher_path, spec in launcher_specs.items():
        backup_path = _launcher_backup_path(launcher_path)
        target_path = spec["target"]
        if target_path == launcher_path:
            target_path = _resolve_launcher_target(launcher_path, backup_path)
        elif launcher_path.exists() and not backup_path.exists():
            launcher_path.rename(backup_path)
        backups[launcher_path.name] = str(backup_path) if backup_path.exists() else None
        _write_launcher_wrapper(
            launcher_path=launcher_path,
            target_path=target_path,
            harness=spec["harness"],
            repo_name=repo_name,
            task_domain=task_domain,
            fallback_command=spec.get("fallback"),
        )
        installed[str(launcher_path)] = str(target_path)
    return {"backups": backups, "installed": installed}


def uninstall_launcher_wrappers(home: Path) -> dict:
    launcher_paths = [
        home / ".local" / "bin" / "codex",
        home / ".local" / "bin" / "cursor",
        home / ".local" / "bin" / "droid",
        home / ".local" / "bin" / "claude",
    ]
    restored: dict[str, str | None] = {}
    removed: list[str] = []
    for launcher_path in launcher_paths:
        backup_path = _launcher_backup_path(launcher_path)
        if launcher_path.exists():
            current = launcher_path.read_text(encoding="utf-8") if launcher_path.is_file() else ""
            if LAUNCHER_MARKER in current:
                launcher_path.unlink()
                removed.append(str(launcher_path))
        if backup_path.exists():
            backup_path.rename(launcher_path)
            restored[str(launcher_path)] = str(launcher_path)
        else:
            restored[str(launcher_path)] = None
    return {"removed": removed, "restored": restored}
