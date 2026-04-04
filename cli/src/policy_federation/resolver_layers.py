"""Policy layer enumeration helpers."""
from __future__ import annotations

from pathlib import Path


def _policy_layers(
    repo_root: Path,
    harness: str,
    repo: str,
    task_domain: str,
    task_instance: str | None,
    task_overlay: str | None,
) -> list[tuple[str, Path]]:
    layers: list[tuple[str, Path]] = [
        ("system/base", repo_root / "policies/system/base.yaml"),
        ("user/org-default", repo_root / "policies/user/org-default.yaml"),
        ("harness/" + harness, repo_root / f"policies/harness/{harness}.yaml"),
        ("repo/" + repo, repo_root / f"policies/repo/{repo}.yaml"),
    ]

    repo_dir = repo_root / "policies/repo"
    primary_repo_file = (repo_dir / f"{repo}.yaml").resolve()
    if repo_dir.is_dir():
        for extra in sorted(repo_dir.glob("*.yaml")):
            if extra.resolve() != primary_repo_file:
                layers.append(("repo/" + extra.stem, extra))

    layers.append(("task_domain/" + task_domain, repo_root / f"policies/task-domain/{task_domain}.yaml"))
    if task_instance:
        layers.append(("task_instance/" + task_instance, repo_root / f"policies/task-instance/{task_instance}.yaml"))
    if task_overlay:
        layers.append(("task_overlay/" + task_overlay, repo_root / f"policies/task-overlay/{task_overlay}.yaml"))
    return layers

