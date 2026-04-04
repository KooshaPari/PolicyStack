"""Policy resolution helpers."""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

from .authorization import normalize_authorization_rules
from .resolver_extensions import _resolve_extensions
from .resolver_layers import _policy_layers
from . import resolver_merge as _resolver_merge

_append_unique_items = _resolver_merge._append_unique_items
_load_policy_document = _resolver_merge._load_policy_document
_merge_maps = _resolver_merge._merge_maps


def resolve(
    repo_root: Path,
    harness: str,
    repo: str,
    task_domain: str,
    task_instance: str | None = None,
    task_overlay: str | None = None,
) -> dict:
    source_files: list[str] = []
    scope_chain: list[str] = []
    contract_ids: list[str] = []
    contract_versions: dict[str, str] = {}
    conflicts: list[dict] = []
    merged_policy: dict = {}

    for scope_name, policy_path in _policy_layers(
        repo_root=repo_root,
        harness=harness,
        repo=repo,
        task_domain=task_domain,
        task_instance=task_instance,
        task_overlay=task_overlay,
    ):
        scope_chain.append(scope_name)
        if not policy_path.exists():
            source_files.append(str(policy_path))
            continue

        policy_doc = _load_policy_document(repo_root, policy_path)
        source_files.append(str(policy_path))
        contract_ids.append(policy_doc["id"])
        contract_versions[policy_doc["id"]] = policy_doc.get("version", "unknown")
        conflicts.extend(policy_doc.get("_extends_conflicts", []))

        merge_strategy = policy_doc.get("merge", {}).get("strategy", "merge_map")
        if merge_strategy not in {"replace", "append", "append_unique", "merge_map"}:
            conflicts.append(
                {
                    "scope": scope_name,
                    "path": str(policy_path),
                    "reason": f"unknown merge strategy: {merge_strategy}",
                }
            )
            merge_strategy = "merge_map"

        merged_policy = _merge_maps(
            base=merged_policy,
            overrides=policy_doc.get("policy", {}),
            strategy=merge_strategy,
            conflicts=conflicts,
        )

    default_effects, authorization_rules = normalize_authorization_rules(merged_policy)

    payload = {
        "policy_hash": hashlib.sha256(json.dumps(merged_policy, sort_keys=True).encode()).hexdigest(),
        "scope_chain": scope_chain,
        "policy": merged_policy,
        "authorization_summary": {
            "default_effects": default_effects,
            "rule_count": len(authorization_rules),
        },
        "policy_contract_versions": contract_versions,
        "contract_count": len(contract_ids),
        "conflicts": conflicts,
        "resolved_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_files": source_files,
        "extensions": _resolve_extensions(repo_root=repo_root, scope_chain=scope_chain, contract_ids=contract_ids),
    }
    return payload


def hash_policy_sources(source_files: list[Path]) -> str:
    """Compute SHA-256 over sorted existing file contents."""
    h = hashlib.sha256()
    for path in sorted(source_files):
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()
