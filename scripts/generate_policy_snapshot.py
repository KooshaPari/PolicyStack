#!/usr/bin/env python3
"""Generate a deterministic policy snapshot for governance checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from resolve import _build_chain, _resolve_config_root, resolve

EXIT_OK = 0
EXIT_WRITE_FAILED = 10
EXIT_CHECK_FAILED = 11
EXIT_MISSING_SNAPSHOT = 12
EXIT_INVALID = 13
EXIT_INTERNAL = 14
CANONICAL_SNAPSHOT_PAIRS: tuple[tuple[str, str], ...] = (
    ("codex", "deployment"),
    ("codex", "query"),
)


def _normalize_scope_path(path_value: str | Path, root: Path) -> str:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_output_path(root: Path, output: str) -> Path:
    output_path = Path(output).expanduser()
    if not output_path.is_absolute():
        output_path = root / output_path
    return output_path.resolve()


def _canonical_snapshot_path(root: Path, harness: str, task_domain: str) -> Path:
    config_root = _resolve_config_root(root)
    return (
        config_root
        / "snapshots"
        / f"policy_snapshot_{harness}_{task_domain}.json"
    ).resolve()


def _canonical_snapshot_dir(root: Path, canonical_dir: str | None) -> Path:
    if canonical_dir is None:
        return (_resolve_config_root(root) / "snapshots").resolve()
    target = Path(canonical_dir).expanduser()
    if not target.is_absolute():
        target = root / target
    return target.resolve()


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    chain = _build_chain(args)
    if not chain:
        raise ValueError("resolved policy chain is empty")

    scopes = [
        {
            "scope": scope_name,
            "path": _normalize_scope_path(scope_path, root),
        }
        for scope_name, scope_path in chain
    ]
    merged_policy = resolve(chain, output=None)
    if not isinstance(merged_policy, dict):
        raise ValueError("resolved policy is invalid")
    if not merged_policy:
        raise ValueError("resolved policy is empty")
    if not isinstance(merged_policy.get("policy_version"), str):
        raise ValueError("resolved policy missing valid policy_version")
    if not isinstance(merged_policy.get("scope"), str):
        raise ValueError("resolved policy missing valid scope")

    payload_hash = hashlib.sha256(
        json.dumps(merged_policy, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return {
        "policy_hash": payload_hash,
        "scopes": scopes,
    }


def _load_snapshot(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("snapshot file must contain a JSON object")
    return data


def _first_differing_key(existing: Any, current: Any, prefix: str = "") -> str | None:
    if type(existing) is not type(current):
        return prefix or "<root>"

    if isinstance(existing, dict):
        keys = sorted(set(existing) | set(current))
        for key in keys:
            key_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key not in existing or key not in current:
                return key_prefix
            diff = _first_differing_key(existing[key], current[key], key_prefix)
            if diff is not None:
                return diff
        return None

    if isinstance(existing, list):
        shared_len = min(len(existing), len(current))
        for idx in range(shared_len):
            key_prefix = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            diff = _first_differing_key(existing[idx], current[idx], key_prefix)
            if diff is not None:
                return diff
        if len(existing) != len(current):
            return f"{prefix}[{shared_len}]" if prefix else f"[{shared_len}]"
        return None

    if existing != current:
        return prefix or "<root>"
    return None


def _print_failure(args: argparse.Namespace, kind: str, message: str, exit_code: int, **details: Any) -> int:
    if args.json:
        payload = {
            "status": "error",
            "kind": kind,
            "message": message,
            "exit_code": exit_code,
            **details,
        }
        print(json.dumps(payload, sort_keys=True))
    else:
        detail_chunks = [f"{key}={value}" for key, value in details.items()]
        suffix = f" {' '.join(detail_chunks)}" if detail_chunks else ""
        print(f"[{kind}] {message}{suffix}")
    return exit_code


def _print_success(args: argparse.Namespace, kind: str, message: str, **details: Any) -> int:
    if args.json:
        payload = {
            "status": "ok",
            "kind": kind,
            "message": message,
            **details,
        }
        print(json.dumps(payload, sort_keys=True))
    else:
        detail_chunks = [f"{key}={value}" for key, value in details.items()]
        suffix = f" {' '.join(detail_chunks)}" if detail_chunks else ""
        print(f"[ok] {message}{suffix}")
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repo root containing policy-contract.")
    parser.add_argument("--harness", help="harness identifier")
    parser.add_argument("--task-domain", help="task domain identifier")
    parser.add_argument("--task-instance", help="optional task-instance policy file")
    parser.add_argument("--system", help="optional absolute or relative system policy path")
    parser.add_argument("--user", help="optional absolute or relative user policy path")
    parser.add_argument("--output", help="output snapshot path")
    parser.add_argument(
        "--check-existing",
        action="store_true",
        help="fail if existing snapshot content drifts from current policy resolution",
    )
    parser.add_argument(
        "--write-canonical",
        action="store_true",
        help=(
            "write committed canonical snapshots for codex/deployment and codex/query "
            "under policy-config/snapshots"
        ),
    )
    parser.add_argument(
        "--validate-canonical",
        action="store_true",
        help=(
            "verify committed canonical snapshots for codex/deployment and codex/query "
            "exist and match current policy resolution"
        ),
    )
    parser.add_argument(
        "--canonical-dir",
        help=(
            "directory used by --write-canonical and --validate-canonical "
            "(defaults to policy-config/snapshots)"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON payloads for drift/failure outputs",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    root = Path(args.root).resolve()
    if args.write_canonical and args.validate_canonical:
        return _print_failure(
            args,
            "error",
            "--write-canonical and --validate-canonical cannot be used together",
            EXIT_INVALID,
        )
    if (args.write_canonical or args.validate_canonical) and args.output:
        return _print_failure(
            args,
            "error",
            "--output cannot be used with --write-canonical or --validate-canonical",
            EXIT_INVALID,
        )
    if not args.write_canonical and not args.validate_canonical and not args.output:
        return _print_failure(
            args,
            "error",
            "--output is required unless --write-canonical or --validate-canonical is set",
            EXIT_INVALID,
        )
    if (args.write_canonical or args.validate_canonical) and args.check_existing:
        return _print_failure(
            args,
            "error",
            "--check-existing cannot be used with --write-canonical or --validate-canonical",
            EXIT_INVALID,
        )
    if not args.write_canonical and not args.validate_canonical and (not args.harness or not args.task_domain):
        return _print_failure(
            args,
            "error",
            "--harness and --task-domain are required unless --write-canonical or --validate-canonical is set",
            EXIT_INVALID,
        )

    if args.write_canonical:
        canonical_dir = _canonical_snapshot_dir(root, args.canonical_dir)
        written_paths: list[str] = []
        for harness, task_domain in CANONICAL_SNAPSHOT_PAIRS:
            canonical_args = argparse.Namespace(**vars(args))
            canonical_args.harness = harness
            canonical_args.task_domain = task_domain
            try:
                snapshot = build_snapshot(canonical_args)
            except (TypeError, ValueError) as exc:
                return _print_failure(args, "error", str(exc), EXIT_INVALID)
            except Exception as exc:  # pragma: no cover - defensive guard
                return _print_failure(args, "error", str(exc), EXIT_INTERNAL)
            output = canonical_dir / f"policy_snapshot_{harness}_{task_domain}.json"
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            except OSError as exc:
                return _print_failure(
                    args,
                    "error",
                    "failed writing snapshot",
                    EXIT_WRITE_FAILED,
                    output_path=_normalize_scope_path(output, root),
                    detail=str(exc),
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                return _print_failure(args, "error", str(exc), EXIT_INTERNAL)
            written_paths.append(_normalize_scope_path(output, root))
        return _print_success(
            args,
            "write_canonical",
            "wrote canonical snapshots",
            snapshot_count=len(written_paths),
            output_paths=sorted(written_paths),
        )

    if args.validate_canonical:
        canonical_dir = _canonical_snapshot_dir(root, args.canonical_dir)
        checked_paths: list[str] = []
        for harness, task_domain in CANONICAL_SNAPSHOT_PAIRS:
            canonical_args = argparse.Namespace(**vars(args))
            canonical_args.harness = harness
            canonical_args.task_domain = task_domain
            try:
                snapshot = build_snapshot(canonical_args)
            except (TypeError, ValueError) as exc:
                return _print_failure(args, "error", str(exc), EXIT_INVALID)
            except Exception as exc:  # pragma: no cover - defensive guard
                return _print_failure(args, "error", str(exc), EXIT_INTERNAL)

            output = canonical_dir / f"policy_snapshot_{harness}_{task_domain}.json"
            output_path = _normalize_scope_path(output, root)
            if not output.exists():
                return _print_failure(
                    args,
                    "drift",
                    "canonical snapshot missing",
                    EXIT_MISSING_SNAPSHOT,
                    output_path=output_path,
                    harness=harness,
                    task_domain=task_domain,
                )
            try:
                existing = _load_snapshot(output)
            except (TypeError, ValueError) as exc:
                return _print_failure(
                    args,
                    "error",
                    str(exc),
                    EXIT_INVALID,
                    output_path=output_path,
                    harness=harness,
                    task_domain=task_domain,
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                return _print_failure(
                    args,
                    "error",
                    str(exc),
                    EXIT_INTERNAL,
                    output_path=output_path,
                    harness=harness,
                    task_domain=task_domain,
                )
            if existing != snapshot:
                drift_details: dict[str, Any] = {
                    "output_path": output_path,
                    "harness": harness,
                    "task_domain": task_domain,
                    "expected_hash": existing.get("policy_hash"),
                    "actual_hash": snapshot.get("policy_hash"),
                }
                first_key = _first_differing_key(existing, snapshot)
                if first_key is not None:
                    drift_details["first_differing_key"] = first_key
                return _print_failure(
                    args,
                    "drift",
                    "canonical snapshot differs",
                    EXIT_CHECK_FAILED,
                    **drift_details,
                )
            checked_paths.append(output_path)
        return _print_success(
            args,
            "validate_canonical",
            "canonical snapshots match",
            snapshot_count=len(checked_paths),
            output_paths=sorted(checked_paths),
        )

    output = _resolve_output_path(root, args.output)
    output_path = _normalize_scope_path(output, root)
    try:
        snapshot = build_snapshot(args)
    except (TypeError, ValueError) as exc:
        return _print_failure(args, "error", str(exc), EXIT_INVALID)
    except Exception as exc:  # pragma: no cover - defensive guard
        return _print_failure(args, "error", str(exc), EXIT_INTERNAL)

    scope_count = len(snapshot.get("scopes", []))
    chain_length = scope_count

    if args.check_existing:
        if not output.exists():
            return _print_failure(
                args,
                "drift",
                "snapshot missing",
                EXIT_MISSING_SNAPSHOT,
                output_path=output_path,
                scope_count=scope_count,
                chain_length=chain_length,
            )
        try:
            existing = _load_snapshot(output)
        except (TypeError, ValueError) as exc:
            return _print_failure(
                args,
                "error",
                str(exc),
                EXIT_INVALID,
                output_path=output_path,
                scope_count=scope_count,
                chain_length=chain_length,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            return _print_failure(
                args,
                "error",
                str(exc),
                EXIT_INTERNAL,
                output_path=output_path,
                scope_count=scope_count,
                chain_length=chain_length,
            )

        if existing != snapshot:
            expected_hash = existing.get("policy_hash")
            actual_hash = snapshot.get("policy_hash")
            first_key = _first_differing_key(existing, snapshot)
            drift_details: dict[str, Any] = {
                "output_path": output_path,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
                "scope_count": scope_count,
                "chain_length": chain_length,
            }
            if first_key is not None:
                drift_details["first_differing_key"] = first_key
            return _print_failure(
                args,
                "drift",
                "snapshot differs",
                EXIT_CHECK_FAILED,
                **drift_details,
            )
        return _print_success(
            args,
            "check_existing",
            "snapshot matches",
            output_path=output_path,
            scope_count=scope_count,
            chain_length=chain_length,
        )

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return _print_failure(
            args,
            "error",
            "failed writing snapshot",
            EXIT_WRITE_FAILED,
            output_path=output_path,
            scope_count=scope_count,
            chain_length=chain_length,
            detail=str(exc),
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return _print_failure(
            args,
            "error",
            str(exc),
            EXIT_INTERNAL,
            output_path=output_path,
            scope_count=scope_count,
            chain_length=chain_length,
        )

    return _print_success(
        args,
        "write",
        "wrote snapshot",
        output_path=output_path,
        scope_count=scope_count,
        chain_length=chain_length,
    )


if __name__ == "__main__":
    sys.exit(main())
