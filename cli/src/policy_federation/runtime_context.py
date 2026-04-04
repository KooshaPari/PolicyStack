"""Runtime context helpers shared by CLI, hooks, and launchers."""
from __future__ import annotations

from pathlib import Path


def infer_repo_name_from_cwd(cwd: str | None) -> str:
    """Infer the owning repo name from a worktree or repository cwd."""
    if cwd:
        path = Path(cwd)
        parts = path.parts
        for index, part in enumerate(parts):
            if part == "worktrees" and index + 1 < len(parts):
                return parts[index + 1]
            if part == "PROJECT-wtrees" and index > 0:
                return parts[index - 1]
            if part.endswith("-wtrees"):
                return part.removesuffix("-wtrees")
            if part.endswith("-worktrees"):
                return part.removesuffix("-worktrees")
    if cwd:
        return Path(cwd).name
    return Path.cwd().name
