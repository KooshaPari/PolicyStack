#!/usr/bin/env python3
"""Check policy-version governance for policy contract YAML/JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from output_contract import emit_failure
from policy_common import (
    ALLOWED_POLICY_VERSIONS,
    discover_policy_paths,
    format_policy_path,
    normalize_input_paths,
    required_default_policy_paths,
)

EXIT_OK = 0
EXIT_MISSING_REQUIRED = 2
EXIT_NO_OBSERVED = 3
EXIT_INVALID = 4
EXIT_MIXED = 5
EXIT_INTERNAL = 10


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="policy-contract root (default: repository root)",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="input file path (repeatable). if omitted, validates policy-config scope files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit structured JSON output",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="downgrade missing required default files from failure to skip",
    )
    return parser


def _load_payload(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(raw)
    else:
        payload = yaml.safe_load(raw) or {}
    if not isinstance(payload, dict):
        raise ValueError("payload must be a mapping")
    return payload


def _load_version(path: Path) -> str:
    payload = _load_payload(path)
    version = payload.get("policy_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("policy_version missing or invalid")
    return version.strip()


def _json_mode_requested(argv: list[str]) -> bool:
    return "--json" in argv


def _run() -> int:
    args = _build_parser().parse_args()
    root = Path(args.root).resolve()

    if args.input:
        policy_files = normalize_input_paths(Path(item) for item in args.input)
        required_paths: set[Path] = set()
    else:
        policy_files = discover_policy_paths(root)
        required_paths = required_default_policy_paths(root)

    if not policy_files:
        if args.json:
            emit_failure(
                json_mode=True,
                code="no-observed",
                message="no policy files found under policy-config",
                details={
                    "policy_files": [],
                    "summary": {
                        "checked": 0,
                        "missing_required": 0,
                        "invalid_versions": 0,
                    },
                },
                sort_keys=True,
            )
        else:
            print("no policy files found under policy-config")
        return EXIT_NO_OBSERVED

    policy_file_paths = [format_policy_path(path, root=root) for path in policy_files]
    versions: dict[str, str] = {}
    observed_versions: set[str] = set()
    missing_required: list[str] = []
    invalid_details: list[dict[str, str]] = []
    report_lines: list[str] = []
    for path in policy_files:
        rel = format_policy_path(path, root=root)
        if not path.exists():
            if path in required_paths:
                missing_required.append(rel)
                if args.allow_missing:
                    report_lines.append(f"[skip-required] {rel} (missing)")
                else:
                    report_lines.append(f"[missing-required] {rel}")
            else:
                report_lines.append(f"[skip] {rel} (missing)")
            continue
        try:
            version = _load_version(path)
            observed_versions.add(version)
            if version not in ALLOWED_POLICY_VERSIONS:
                invalid_details.append(
                    {
                        "path": rel,
                        "reason": (
                            f"{version} (allowed: {', '.join(sorted(ALLOWED_POLICY_VERSIONS))})"
                        ),
                    }
                )
                report_lines.append(
                    f"[invalid-version] {rel}: {version} "
                    f"(allowed: {', '.join(sorted(ALLOWED_POLICY_VERSIONS))})"
                )
                continue
            versions[rel] = version
            report_lines.append(f"[ok] {rel}: {version}")
        except Exception as exc:
            invalid_details.append({"path": rel, "reason": str(exc)})
            report_lines.append(f"[error] {rel}: {exc}")

    unique_versions = sorted(observed_versions)
    if missing_required:
        report_lines.append(
            "missing required default policy files: "
            + ", ".join(sorted(missing_required))
        )
        if args.allow_missing:
            report_lines.append(
                "allow-missing enabled: required default policy files were skipped"
            )

    has_missing_required = bool(missing_required) and not args.allow_missing
    has_invalid = bool(invalid_details)
    has_no_observed = not unique_versions
    has_mixed = len(unique_versions) > 1

    if not unique_versions:
        report_lines.append("[no-observed-versions] no valid policy_version values were observed")
    elif len(unique_versions) != 1:
        report_lines.append(
            "[mixed-version-chain] inconsistent policy_version values; versions="
            + repr(unique_versions)
        )

    if has_missing_required or has_invalid or has_no_observed or has_mixed:
        if has_missing_required:
            failure_code = "missing-required"
            exit_code = EXIT_MISSING_REQUIRED
            message = "missing required default policy files"
        elif has_no_observed:
            failure_code = "no-observed"
            exit_code = EXIT_NO_OBSERVED
            message = "no valid policy_version values were observed"
        elif has_mixed:
            failure_code = "mixed"
            exit_code = EXIT_MIXED
            message = "inconsistent policy_version values were observed"
        else:
            failure_code = "invalid"
            exit_code = EXIT_INVALID
            message = "encountered invalid policy versions or malformed policy payloads"

        summary = {
            "checked": len(policy_files),
            "missing_required": len(missing_required),
            "invalid_versions": len(invalid_details),
        }
        details = {
            "allowed_versions": sorted(ALLOWED_POLICY_VERSIONS),
            "invalid": invalid_details,
            "missing_required": sorted(missing_required),
            "observed_versions": unique_versions,
            "policy_files": policy_file_paths,
            "summary": summary,
            "versions": unique_versions,
        }
        if args.json:
            emit_failure(
                json_mode=True,
                code=failure_code,
                message=message,
                details=details,
                sort_keys=True,
            )
        else:
            for line in report_lines:
                print(line)
            failure_count = len(invalid_details) + len(missing_required)
            if has_no_observed:
                failure_count += 1
            if has_mixed:
                failure_count += 1
            print(f"policy version governance failed: {failure_count} file(s) invalid")
        return exit_code

    summary = {
        "checked": len(policy_files),
        "missing_required": len(missing_required),
        "invalid_versions": len(invalid_details),
    }
    if args.json:
        emit_failure(
            json_mode=True,
            code="ok",
            message="policy version governance passed",
            details={
                "allowed_versions": sorted(ALLOWED_POLICY_VERSIONS),
                "missing_required": sorted(missing_required),
                "observed_versions": unique_versions,
                "policy_files": policy_file_paths,
                "summary": summary,
                "version": unique_versions[0],
                "versions": unique_versions,
            },
            sort_keys=True,
        )
    else:
        for line in report_lines:
            print(line)
        print(f"policy version governance passed: {unique_versions[0]}")
    return EXIT_OK


def main() -> int:
    try:
        return _run()
    except Exception as exc:
        if _json_mode_requested(sys.argv[1:]):
            emit_failure(
                json_mode=True,
                code="internal-error",
                message="unexpected internal error",
                details={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                sort_keys=True,
            )
        else:
            print(f"[internal] unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    sys.exit(main())
