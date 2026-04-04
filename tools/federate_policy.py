#!/usr/bin/env python3
"""Resolve federated agent policy across scope layers."""

from __future__ import annotations

import argparse
import hashlib
import json
import hmac
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent.parent
POLICY_ROOT = ROOT / "policies"
EXT_ROOT = ROOT / "extensions" / "manifests"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve layered agent policy.")
    parser.add_argument("--repo", required=True, help="Repository key")
    parser.add_argument("--harness", required=True, help="Harness key")
    parser.add_argument("--user", default="core-operator", help="User key")
    parser.add_argument("--task-domain", default="agentops", help="Task domain key")
    parser.add_argument(
        "--extensions",
        default="",
        help="Comma-separated extension names",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output file for effective policy payload",
    )
    parser.add_argument(
        "--policy-dir",
        default=str(POLICY_ROOT),
        help="Base directory with policy layers",
    )
    parser.add_argument(
        "--manifest-dir",
        default=str(EXT_ROOT),
        help="Directory with extension manifests",
    )
    parser.add_argument(
        "--repo-default",
        default="default",
        help="Fallback repo policy file under policies/repo (default)",
    )
    parser.add_argument(
        "--sign-key",
        default="",
        help="Optional HMAC key to include policy_signature in audit",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any layer file is missing",
    )
    return parser.parse_args()


def load_json_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing policy file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def hash_payload(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def collect_files(
    repo: str,
    harness: str,
    user: str,
    task_domain: str,
    extensions: list[str],
    policy_dir: Path,
    manifest_dir: Path,
    repo_default: str,
    strict: bool,
) -> tuple[list[dict], list[str], list[str]]:
    policy_paths = [
        ("system", "base"),
        ("system", "security-guard"),
        ("user", user),
        ("harness", harness),
        ("repo", repo),
        ("task-domain", task_domain),
    ]

    layers: list[dict] = []
    files: list[str] = []
    missing: list[str] = []

    for scope, name in policy_paths:
        path = policy_dir / scope / f"{name}.json"
        if not path.exists():
            if scope == "repo":
                default_path = policy_dir / scope / f"{repo_default}.json"
                if default_path.exists():
                    path = default_path
                else:
                    missing.append(f"{scope}/{name}.json")
            else:
                missing.append(f"{scope}/{name}.json")

            if not path.exists():
                continue

            layers.append(load_json_file(path))
            files.append(f"{scope}/{path.name}")
            continue

        payload = load_json_file(path)
        layers.append(payload)
        files.append(f"{scope}/{name}.json")

    # Optional extension manifests can be injected as policy fragments.
    for ext in extensions:
        manifest_path = manifest_dir / f"{ext}.json"
        if not manifest_path.exists():
            missing.append(f"extensions/manifests/{ext}.json")
            continue
        manifest = load_json_file(manifest_path)
        fragment = manifest.get("fragment", {})
        if fragment:
            layers.append({"policy": {"extensions": {ext: fragment}}})
        else:
            layers.append({"policy": {}})
        files.append(f"extensions/manifests/{ext}.json")

    return layers, files, missing


def main() -> None:
    args = parse_args()
    policy_dir = Path(args.policy_dir)
    manifest_dir = Path(args.manifest_dir)
    extension_list = [item.strip() for item in args.extensions.split(",") if item.strip()]

    layers, files, missing = collect_files(
        repo=args.repo,
        harness=args.harness,
        user=args.user,
        task_domain=args.task_domain,
        extensions=extension_list,
        policy_dir=policy_dir,
        manifest_dir=manifest_dir,
        repo_default=args.repo_default,
        strict=args.strict,
    )

    if missing and args.strict:
        raise FileNotFoundError(
            "Missing required layer files: " + ", ".join(sorted(missing))
        )

    effective: dict = {}
    applied_layers = []
    for layer in layers:
        effective = deep_merge(effective, layer)
        applied_layers.append(layer)

    payload = {
        "resolver_version": "agent-devops-setups/federation-v1",
        "scope": {
            "system": "base,security-guard",
            "user": args.user,
            "harness": args.harness,
            "repo": args.repo,
            "task_domain": args.task_domain,
            "extensions": extension_list,
        },
        "policy": effective.get("policy", {}),
        "applied_layers": applied_layers,
        "audit": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "policy_digest": "",
            "policy_signature": "",
            "files": files,
        },
    }

    payload["audit"]["policy_digest"] = hash_payload(
        {
            "scope": payload["scope"],
            "policy": payload["policy"],
            "applied_layers": applied_layers,
        }
    )
    if args.sign_key:
        signature = hmac.new(
            args.sign_key.encode("utf-8"),
            payload["audit"]["policy_digest"].encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        payload["audit"]["policy_signature"] = signature

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote {out_path} ({len(files)} layers)")


if __name__ == "__main__":
    main()
