"""Policy extension registry helpers."""
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

import yaml


def _load_extensions(repo_root: Path) -> list[dict]:
    registry_path = repo_root / "extensions" / "registry.yaml"
    if not registry_path.exists():
        return []

    with registry_path.open("r", encoding="utf-8") as f:
        registry = yaml.safe_load(f) or {}

    extensions = registry.get("extensions", [])
    if not isinstance(extensions, list):
        raise ValueError("extensions.registry.extensions must be a list")
    return extensions


def _extension_scope_matches(selector: str, scope_chain: list[str]) -> bool:
    for scope in scope_chain:
        if fnmatch(scope, selector):
            return True
    return False


def _resolve_extensions(repo_root: Path, scope_chain: list[str], contract_ids: list[str]) -> dict:
    manifests = _load_extensions(repo_root)
    enabled = []
    skipped = []

    for manifest in manifests:
        name = manifest.get("name")
        selectors = (manifest.get("scope_selector") or {}).get("includes", [])
        requires = manifest.get("requires", [])

        if not name or not isinstance(selectors, list):
            skipped.append(
                {
                    "name": name,
                    "reason": "Invalid registry entry",
                }
            )
            continue

        if manifest.get("enabled_by_default", False) is False:
            skipped.append({"name": name, "reason": "disabled_by_default"})
            continue

        include_ok = any(_extension_scope_matches(pattern, scope_chain) for pattern in selectors)
        if not include_ok:
            skipped.append({"name": name, "reason": "scope_selector_no_match"})
            continue

        required_ids = {
            req.get("id")
            for req in requires
            if isinstance(req, dict) and req.get("id")
        }
        if not all(req in contract_ids for req in required_ids):
            skipped.append(
                {
                    "name": name,
                    "reason": "requirements_not_met",
                    "missing": sorted(required_ids.difference(contract_ids)),
                }
            )
            continue

        enabled.append(name)

    return {"enabled": enabled, "disabled": skipped}

