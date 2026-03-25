from __future__ import annotations

from pathlib import Path
from typing import Any

MANAGED_MARKER_START = "# POLICY_CONTRACT_MANAGED_START"
MANAGED_MARKER_END = "# POLICY_CONTRACT_MANAGED_END"
JSON_MANAGED_MARKER_START = "__POLICY_CONTRACT_MANAGED_START__"
JSON_MANAGED_MARKER_END = "__POLICY_CONTRACT_MANAGED_END__"


def find_managed_segment(
    existing: list[Any],
    start_marker: Any,
    end_marker: Any,
    *,
    path: Path,
    key: str,
) -> tuple[int | None, int | None]:
    start_positions = [
        index for index, item in enumerate(existing) if item == start_marker
    ]
    end_positions = [index for index, item in enumerate(existing) if item == end_marker]
    if not start_positions and not end_positions:
        return None, None
    if (
        len(start_positions) == 1
        and len(end_positions) == 1
        and start_positions[0] < end_positions[0]
    ):
        return start_positions[0], end_positions[0]
    raise ValueError(f"{path}: invalid managed marker layout for '{key}'")


def replace_managed_entries(
    existing: list[Any],
    generated: list[str],
    path: Path,
    key: str,
) -> list[Any]:
    start, end = find_managed_segment(
        existing,
        JSON_MANAGED_MARKER_START,
        JSON_MANAGED_MARKER_END,
        path=path,
        key=key,
    )
    if start is None or end is None:
        prefix = existing
        suffix: list[Any] = []
    else:
        prefix = existing[:start]
        suffix = existing[end + 1 :]

    return [
        *prefix,
        JSON_MANAGED_MARKER_START,
        *generated,
        JSON_MANAGED_MARKER_END,
        *suffix,
    ]


def count_policy_entries(items: list[Any]) -> int:
    return sum(
        1
        for item in items
        if item not in {JSON_MANAGED_MARKER_START, JSON_MANAGED_MARKER_END}
    )


def ensure_prefix_rules_file(path: Path, generated_lines: list[str]) -> tuple[int, int]:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    start = existing.find(MANAGED_MARKER_START)
    end = existing.find(MANAGED_MARKER_END)
    generated_block = "\n".join(generated_lines)
    if not generated_block:
        generated_block = ""

    new_block = (
        f"{MANAGED_MARKER_START}\n" + generated_block + f"\n{MANAGED_MARKER_END}\n"
    )

    if start != -1 and end != -1 and end > start:
        before = existing[:start]
        after = existing[end + len(MANAGED_MARKER_END) :]
        if before and not before.endswith("\n"):
            before += "\n"
        if after and not after.startswith("\n"):
            after = "\n" + after.lstrip("\n")
        updated = before + new_block + after
    else:
        spacer = "\n\n" if existing and not existing.endswith("\n") else "\n"
        updated = existing + spacer + new_block

    old_count = len(
        [
            line
            for line in existing.splitlines()
            if line.strip().startswith("prefix_rule(")
        ]
    )
    new_count = len(generated_lines)
    path.write_text(updated, encoding="utf-8")
    return old_count, new_count
