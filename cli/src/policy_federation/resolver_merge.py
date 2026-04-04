"""Policy merge and inheritance helpers."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .validate import validate_policy_file


def _append_unique_items(values: list) -> list:
    """Append list items while preserving order for unhashable values."""
    override_index: dict[tuple[str, str], int] = {}
    unique_values: list = []
    seen_keys: set[str] = set()
    for value in values:
        if isinstance(value, dict) and "id" in value and isinstance(value["id"], str):
            id_key = ("id", value["id"])
            if id_key in override_index:
                unique_values[override_index[id_key]] = copy.deepcopy(value)
                continue
            override_index[id_key] = len(unique_values)
            unique_values.append(copy.deepcopy(value))
            continue

        try:
            key = json.dumps(value, sort_keys=True)
        except TypeError:
            key = repr(value)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_values.append(copy.deepcopy(value))
    return unique_values


def _merge_maps(base: dict, overrides: dict, strategy: str, conflicts: list[dict], node: str = "root") -> dict:
    if not isinstance(base, dict) or not isinstance(overrides, dict):
        if strategy == "replace":
            return copy.deepcopy(overrides)
        conflicts.append(
            {
                "node": node,
                "strategy": strategy,
                "reason": "Type mismatch during merge_map",
            }
        )
        return copy.deepcopy(overrides)

    merged = dict(base)
    for key, value in overrides.items():
        merged_key = f"{node}.{key}" if node else key
        if key not in merged:
            merged[key] = copy.deepcopy(value)
            continue

        current = merged[key]
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_maps(current, value, strategy, conflicts, merged_key)
            continue

        if isinstance(current, list) and isinstance(value, list):
            if strategy == "append":
                merged[key] = current + value
            elif strategy == "append_unique":
                merged[key] = _append_unique_items(current + value)
            else:
                merged[key] = copy.deepcopy(value)
            continue

        if strategy in {"merge_map", "replace"}:
            merged[key] = copy.deepcopy(value)

    return merged


def _resolve_extend_reference(repo_root: Path, reference: str, current_path: Path) -> Path:
    """Resolve an extends reference to a concrete policy path."""
    if reference.endswith(".yaml"):
        candidate = (current_path.parent / reference).resolve() if not Path(reference).is_absolute() else Path(reference)
        return candidate

    if "/" not in reference:
        raise ValueError(f"invalid extends reference: {reference}")

    scope_dir_map = {
        "system": "system",
        "user": "user",
        "harness": "harness",
        "repo": "repo",
        "task_domain": "task-domain",
        "task_instance": "task-instance",
        "task_overlay": "task-overlay",
    }
    scope, name = reference.split("/", 1)
    scope_dir = scope_dir_map.get(scope)
    if scope_dir is None:
        raise ValueError(f"unknown extends scope: {scope}")
    return repo_root / "policies" / scope_dir / f"{name}.yaml"


def _load_policy_document(repo_root: Path, policy_path: Path, stack: tuple[Path, ...] = ()) -> dict:
    """Load one policy document and resolve any local inheritance chain."""
    normalized_path = policy_path.resolve()
    if normalized_path in stack:
        cycle = " -> ".join(str(path) for path in stack + (normalized_path,))
        raise ValueError(f"policy extends cycle detected: {cycle}")

    doc = validate_policy_file(normalized_path)
    extends = doc.get("extends") or []
    if not extends:
        return doc

    inherited_policy: dict = {}
    conflicts: list[dict] = []
    for reference in extends:
        parent_path = _resolve_extend_reference(repo_root, reference, normalized_path)
        parent_doc = _load_policy_document(repo_root, parent_path, stack + (normalized_path,))
        parent_strategy = parent_doc.get("merge", {}).get("strategy", "merge_map")
        inherited_policy = _merge_maps(
            inherited_policy,
            parent_doc.get("policy", {}),
            parent_strategy,
            conflicts,
            node="policy",
        )

    child_strategy = doc.get("merge", {}).get("strategy", "merge_map")
    resolved_policy = _merge_maps(
        inherited_policy,
        doc.get("policy", {}),
        child_strategy,
        conflicts,
        node="policy",
    )
    resolved_doc = copy.deepcopy(doc)
    resolved_doc["policy"] = resolved_policy
    if conflicts:
        resolved_doc.setdefault("_extends_conflicts", []).extend(conflicts)
    return resolved_doc

