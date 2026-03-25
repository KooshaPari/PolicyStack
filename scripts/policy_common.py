"""Shared policy discovery rules and governance constants."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Final

POLICY_CONFIG_DIR_NAME: Final[str] = "policy-config"
DEFAULT_POLICY_SCOPE_STEMS: Final[tuple[str, ...]] = ("system", "user", "repo")
DISCOVERY_SCOPE_DIRS: Final[tuple[str, ...]] = (
    "harness",
    "task-domain",
    "task-instance",
)
DISCOVERY_EXTENSIONS: Final[tuple[str, ...]] = (".yaml", ".yml", ".json")
ALLOWED_POLICY_VERSIONS: Final[frozenset[str]] = frozenset({"v1"})

_EXTENSION_PRIORITY: Final[dict[str, int]] = {
    ".yaml": 0,
    ".yml": 1,
    ".json": 2,
}


def _extension_priority(path: Path) -> int:
    return _EXTENSION_PRIORITY.get(path.suffix.lower(), 99)


def _select_preferred(candidates: Iterable[Path]) -> Path:
    ranked = sorted(candidates, key=lambda path: (_extension_priority(path), path.name))
    return ranked[0]


def _default_missing_placeholder(config_root: Path, stem: str) -> Path:
    return config_root / f"{stem}.yaml"


def _deduped_scope_files(scope_root: Path) -> list[Path]:
    if not scope_root.exists():
        return []

    by_stem: dict[str, Path] = {}
    for ext in DISCOVERY_EXTENSIONS:
        for candidate in sorted(scope_root.glob(f"*{ext}")):
            chosen = by_stem.get(candidate.stem)
            if chosen is None:
                by_stem[candidate.stem] = candidate
                continue
            by_stem[candidate.stem] = _select_preferred((chosen, candidate))

    return [by_stem[stem] for stem in sorted(by_stem)]


def discover_default_policy_paths(root: Path) -> list[Path]:
    config_root = root / POLICY_CONFIG_DIR_NAME
    discovered: list[Path] = []

    for stem in DEFAULT_POLICY_SCOPE_STEMS:
        candidates = [
            config_root / f"{stem}{ext}"
            for ext in DISCOVERY_EXTENSIONS
            if (config_root / f"{stem}{ext}").exists()
        ]
        if candidates:
            discovered.append(_select_preferred(candidates))
        else:
            discovered.append(_default_missing_placeholder(config_root, stem))

    return discovered


def discover_policy_paths(root: Path) -> list[Path]:
    config_root = root / POLICY_CONFIG_DIR_NAME
    discovered = discover_default_policy_paths(root)
    for scope_dir in DISCOVERY_SCOPE_DIRS:
        discovered.extend(_deduped_scope_files(config_root / scope_dir))
    return discovered


def required_default_policy_paths(root: Path) -> set[Path]:
    return set(discover_default_policy_paths(root))


def normalize_input_paths(paths: Iterable[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        normalized = path.expanduser().resolve()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def format_policy_path(path: Path, *, root: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
