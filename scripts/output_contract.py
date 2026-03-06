#!/usr/bin/env python3
"""Shared output helpers for policy contract scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _as_path_text(path: Path | str | None) -> str | None:
    if path is None:
        return None
    if isinstance(path, Path):
        return str(path)
    return path


def build_status_envelope(*, code: str, message: str) -> dict[str, Any]:
    return {"type": "status", "code": code, "message": message}


def build_result_envelope(
    *,
    status: str,
    path: Path | str,
    details: Any | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "result", "status": status, "path": str(path)}
    if details is not None:
        payload["details"] = details
    return payload


def build_summary_envelope(*, checked: int, missing: int, invalid: int) -> dict[str, Any]:
    return {"type": "summary", "checked": checked, "missing": missing, "invalid": invalid}


def build_failure_envelope(
    *,
    code: str,
    message: str,
    path: Path | str | None = None,
    details: Any | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    path_text = _as_path_text(path)
    if path_text is not None:
        payload["path"] = path_text
    if details is not None:
        payload["details"] = details
    return payload


def emit_json(payload: dict[str, Any], *, sort_keys: bool = False) -> None:
    print(json.dumps(payload, ensure_ascii=True, sort_keys=sort_keys))


def emit_status(*, json_mode: bool, code: str, message: str, text: str | None = None) -> None:
    if json_mode:
        emit_json(build_status_envelope(code=code, message=message))
        return
    print(text if text is not None else message)


def emit_result(
    *,
    json_mode: bool,
    status: str,
    path: Path | str,
    details: Any | None = None,
) -> None:
    if json_mode:
        emit_json(build_result_envelope(status=status, path=path, details=details))
        return
    if status == "ok":
        print(f"[ok] {path}")
        return
    if status == "skip":
        print(f"[skip] {path} ({details})")
        return
    print(f"[{status}] {path}")


def emit_summary(*, json_mode: bool, checked: int, missing: int, invalid: int) -> None:
    if json_mode:
        emit_json(build_summary_envelope(checked=checked, missing=missing, invalid=invalid))
        return
    print(f"summary checked={checked} missing={missing} invalid={invalid}")


def emit_failure(
    *,
    json_mode: bool,
    code: str,
    message: str,
    path: Path | str | None = None,
    details: Any | None = None,
    text: str | None = None,
    sort_keys: bool = False,
) -> None:
    if json_mode:
        emit_json(
            build_failure_envelope(code=code, message=message, path=path, details=details),
            sort_keys=sort_keys,
        )
        return
    if text is not None:
        print(text)
        return
    parts = [f"[{code}]", message]
    path_text = _as_path_text(path)
    if path_text is not None:
        parts.append(path_text)
    if details is not None:
        parts.append(str(details))
    print(" ".join(parts))
