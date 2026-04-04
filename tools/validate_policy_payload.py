#!/usr/bin/env python3
"""Validate effective policy and extension manifests with schema support."""

from __future__ import annotations

import argparse
import hashlib
import json
import hmac
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate policy payload artifacts.")
    parser.add_argument("--payload", required=True, help="Path to effective-policy.json")
    parser.add_argument(
        "--policy-schema",
        default="schemas/policy-resolution.schema.json",
        help="Policy schema file",
    )
    parser.add_argument(
        "--manifest-schema",
        default="schemas/extension-manifest.schema.json",
        help="Extension manifest schema file",
    )
    parser.add_argument(
        "--manifest-dir",
        default="extensions/manifests",
        help="Directory containing extension manifests",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat schema fallback and missing files as hard failures",
    )
    parser.add_argument(
        "--sign-key",
        default="",
        help="Verify audit.policy_signature against policy_digest",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def hash_payload(payload: dict) -> str:
    encoded = json.dumps(
        {
            "scope": payload["scope"],
            "policy": payload["policy"],
            "applied_layers": payload["applied_layers"],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_schema(payload: dict, schema: dict, strict: bool) -> tuple[list[str], list[str]]:
    missing = []
    warnings: list[str] = []
    try:
        import jsonschema
    except Exception as exc:  # pragma: no cover - optional dependency
        if strict:
            missing.append(f"jsonschema import unavailable: {exc}")
        else:
            warnings.append(f"jsonschema import unavailable: {exc}")
        return missing, warnings

    try:
        jsonschema.validate(payload, schema)
    except Exception as exc:  # pragma: no cover - exercised at runtime
        missing.append(f"schema validation failed: {exc}")
    return missing, warnings


def validate_minimal_policy(payload: dict) -> list[str]:
    errs = []
    required = ["resolver_version", "scope", "policy", "applied_layers", "audit"]
    for key in required:
        if key not in payload:
            errs.append(f"missing required payload key: {key}")

    scope = payload.get("scope") if isinstance(payload.get("scope"), dict) else None
    if scope is None:
        errs.append("scope must be an object")
    else:
        for key in ["system", "user", "harness", "repo", "task_domain", "extensions"]:
            if key not in scope:
                errs.append(f"missing scope key: {key}")

    audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else None
    if audit is None:
        errs.append("audit must be an object")
    else:
        if "generated_at" not in audit:
            errs.append("missing audit.generated_at")
        if "policy_digest" not in audit:
            errs.append("missing audit.policy_digest")
        if "files" not in audit:
            errs.append("missing audit.files")
        elif not isinstance(audit["files"], list):
            errs.append("audit.files must be a list")

    if payload.get("policy", None) is None or not isinstance(payload["policy"], dict):
        errs.append("policy must be an object")

    if not isinstance(payload.get("applied_layers", None), list):
        errs.append("applied_layers must be a list")

    policy_digest = payload.get("audit", {}).get("policy_digest")
    if isinstance(policy_digest, str) and payload.get("applied_layers") is not None:
        expected = hash_payload(payload)
        if policy_digest != expected:
            errs.append("audit.policy_digest does not match computed digest")
    return errs


def validate_manifest(path: Path, manifest_schema: dict, strict: bool) -> list[str]:
    data = load_json(path)
    errors = []
    errs, warnings = validate_schema(data, manifest_schema, strict)
    errors.extend(errs)
    for warning in warnings:
        print(f"WARN: {warning}")

    for required in ["name", "version", "kind", "scope", "targets", "fragment"]:
        if required not in data:
            errors.append(f"{path}: missing required manifest key {required}")

    if "targets" in data and not isinstance(data["targets"], list):
        errors.append(f"{path}: targets must be a list")
    if "fragment" in data and not isinstance(data["fragment"], dict):
        errors.append(f"{path}: fragment must be an object")
    return errors


def validate_signature(payload: dict, sign_key: str) -> list[str]:
    if not sign_key:
        return []

    audit = payload.get("audit", {})
    expected = payload.get("audit", {}).get("policy_signature")
    if not expected:
        return ["sign-key provided but policy_signature missing from audit"]

    digest = payload.get("audit", {}).get("policy_digest", "")
    if not isinstance(digest, str):
        return ["policy_digest missing or not string"]

    computed = hmac.new(
        sign_key.encode("utf-8"),
        digest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if computed != expected:
        return ["policy_signature mismatch"]
    return []


def main() -> None:
    args = parse_args()
    payload = load_json(Path(args.payload))
    policy_schema = load_json(Path(args.policy_schema))
    manifest_schema = load_json(Path(args.manifest_schema))

    manifest_dir = Path(args.manifest_dir)
    errors = []

    errors.extend(validate_minimal_policy(payload))
    errs, warnings = validate_schema(payload, policy_schema, args.strict)
    if warnings:
        for warning in warnings:
            print(f"WARN: {warning}")
    errors.extend(errs)

    for file_name in payload.get("audit", {}).get("files", []):
        if not isinstance(file_name, str):
            errors.append(f"invalid file entry: {file_name}")
            continue
        if not file_name.startswith("extensions/manifests/"):
            continue
        manifest_path = manifest_dir / file_name.split("/", 2)[-1]
        if not manifest_path.exists():
            if args.strict:
                errors.append(f"manifest not found: {manifest_path}")
            continue
        errors.extend(validate_manifest(manifest_path, manifest_schema, args.strict))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    sig_errors = validate_signature(payload, args.sign_key)
    if sig_errors:
        for error in sig_errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(
        "policy payload valid: "
        f"scope={payload['scope']['repo']} "
        f"extensions={len(payload['scope']['extensions'])} "
        f"digest={payload['audit']['policy_digest'][:12]}..."
    )


if __name__ == "__main__":
    main()
