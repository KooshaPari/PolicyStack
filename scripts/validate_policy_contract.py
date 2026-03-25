#!/usr/bin/env python3
"""Validate policy YAML/JSON files against the canonical policy contract schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from output_contract import emit_failure, emit_result, emit_status, emit_summary
from policy_common import (
    discover_policy_paths,
    normalize_input_paths,
    required_default_policy_paths,
)

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError as exc:
    raise SystemExit(
        "jsonschema is required for policy validation. Install with: uv pip install jsonschema"
    ) from exc


EXIT_OK = 0
EXIT_ARG = 2
EXIT_SCHEMA = 3
EXIT_MISSING = 4
EXIT_VALIDATION = 5
EXIT_INTERNAL = 10


class ArgumentParsingError(ValueError):
    """Raised when CLI argument parsing fails."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # noqa: D401
        raise ArgumentParsingError(message)


def _load_payload(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: payload must be a mapping")
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="policy-contract root (default: repository root)",
    )
    parser.add_argument(
        "--schema",
        default="agent-scope/policy_contract.schema.json",
        help="schema path relative to --root or absolute",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="input file path (repeatable). if omitted, validates policy-config scope files",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="skip missing files (default: missing required defaults fail validation)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON objects for all output",
    )
    return parser


def main() -> int:
    try:
        args = _build_parser().parse_args()
    except ArgumentParsingError as exc:
        emit_failure(
            json_mode=False, code="arg", message=f"argument parsing failed: {exc}"
        )
        print("  id=arg-parse-error")
        return EXIT_ARG

    root = Path(args.root).resolve()
    checked = 0
    missing = 0
    invalid = 0

    try:
        schema_path = Path(args.schema)
        if not schema_path.is_absolute():
            schema_path = root / schema_path
        if not schema_path.exists():
            emit_failure(
                json_mode=args.json,
                code="schema",
                message="schema not found",
                path=schema_path,
            )
            return EXIT_SCHEMA
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as exc:
            emit_failure(
                json_mode=args.json,
                code="schema",
                message="failed to load schema",
                path=schema_path,
                details=str(exc),
            )
            return EXIT_SCHEMA
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            invalid += 1
            emit_failure(
                json_mode=args.json,
                code="schema",
                message="schema self-validation failed",
                path=schema_path,
                details=str(exc),
            )
            if not args.json:
                print("  id=schema-invalid")
            emit_summary(
                json_mode=args.json, checked=checked, missing=missing, invalid=invalid
            )
            return EXIT_SCHEMA
        validator = Draft202012Validator(schema)

        if args.input:
            inputs = normalize_input_paths(Path(item) for item in args.input)
            required_paths = set(inputs)
        else:
            inputs = discover_policy_paths(root)
            required_paths = required_default_policy_paths(root)

        missing_failures = 0
        validation_failures = 0
        for path in inputs:
            if not path.exists():
                missing += 1
                if args.allow_missing:
                    emit_result(
                        json_mode=args.json, status="skip", path=path, details="missing"
                    )
                elif path in required_paths:
                    missing_failures += 1
                    emit_failure(
                        json_mode=args.json,
                        code="missing",
                        message="required input missing",
                        path=path,
                        details={"identifier": "missing-required-input"},
                    )
                    if not args.json:
                        print("  id=missing-required-input")
                else:
                    emit_result(
                        json_mode=args.json,
                        status="skip",
                        path=path,
                        details="missing optional",
                    )
                continue
            checked += 1
            try:
                payload = _load_payload(path)
            except Exception as exc:
                validation_failures += 1
                invalid += 1
                emit_failure(
                    json_mode=args.json,
                    code="validation",
                    message="failed to load/parse input",
                    path=path,
                    details=str(exc),
                )
                continue

            errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
            if errors:
                validation_failures += 1
                invalid += 1
                if args.json:
                    details = [
                        {
                            "location": ".".join(str(part) for part in err.path)
                            or "<root>",
                            "message": err.message,
                        }
                        for err in errors
                    ]
                    emit_failure(
                        json_mode=True,
                        code="validation",
                        message="schema validation failed",
                        path=path,
                        details=details,
                    )
                else:
                    print(f"[invalid] {path}")
                    print("  id=validation-invalid")
                    for err in errors:
                        loc = ".".join(str(part) for part in err.path) or "<root>"
                        print(f"  - {loc}: {err.message}")
                continue

            emit_result(json_mode=args.json, status="ok", path=path)

        if validation_failures:
            emit_status(
                json_mode=args.json,
                code="validation",
                message=f"validation failed: {validation_failures} file(s) invalid",
            )
            emit_summary(
                json_mode=args.json, checked=checked, missing=missing, invalid=invalid
            )
            return EXIT_VALIDATION
        if missing_failures:
            emit_status(
                json_mode=args.json,
                code="missing",
                message=f"validation failed: {missing_failures} required file(s) missing",
            )
            emit_summary(
                json_mode=args.json, checked=checked, missing=missing, invalid=invalid
            )
            return EXIT_MISSING
        emit_status(json_mode=args.json, code="ok", message="validation passed")
        emit_summary(
            json_mode=args.json, checked=checked, missing=missing, invalid=invalid
        )
        return EXIT_OK
    except Exception as exc:  # pragma: no cover
        emit_failure(
            json_mode=args.json,
            code="internal",
            message="unexpected internal error",
            details=str(exc),
        )
        return EXIT_INTERNAL


if __name__ == "__main__":
    sys.exit(main())
