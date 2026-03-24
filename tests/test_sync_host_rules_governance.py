from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.host_rules_managed import (
    ensure_prefix_rules_file,
    find_managed_segment,
    replace_managed_entries,
)
from scripts import sync_host_rules
from scripts.sync_host_rules import (
    JSON_MANAGED_MARKER_END,
    JSON_MANAGED_MARKER_START,
    MANAGED_MARKER_END,
    MANAGED_MARKER_START,
    _validate_policy_json_path,
    apply_host_artifacts,
    render_platform_payload,
)


def test_validate_policy_json_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--policy-json does not exist"):
        _validate_policy_json_path(str(tmp_path / "missing-policy.json"))


def test_validate_policy_json_rejects_directory(tmp_path: Path) -> None:
    policy_dir = tmp_path / "policy-dir"
    policy_dir.mkdir()
    with pytest.raises(ValueError, match="--policy-json must be a file"):
        _validate_policy_json_path(str(policy_dir))


def test_validate_policy_json_rejects_unreadable_file(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.json"
    policy_file.write_text("{}", encoding="utf-8")

    if os.name == "nt":
        pytest.skip("chmod unreadable semantics are platform-dependent on Windows")

    policy_file.chmod(0)
    try:
        with pytest.raises(ValueError, match="--policy-json is not readable"):
            _validate_policy_json_path(str(policy_file))
    finally:
        policy_file.chmod(0o600)


def test_replace_managed_entries_replaces_existing_segment_and_preserves_user_items() -> None:
    existing = [
        "Shell(user allow prefix)",
        JSON_MANAGED_MARKER_START,
        "Shell(stale)",
        JSON_MANAGED_MARKER_END,
        "Shell(user allow suffix)",
    ]

    updated = replace_managed_entries(
        existing,
        ["Shell(generated allow)"],
        Path("/tmp/cursor.json"),
        "allow",
    )

    assert updated == [
        "Shell(user allow prefix)",
        JSON_MANAGED_MARKER_START,
        "Shell(generated allow)",
        JSON_MANAGED_MARKER_END,
        "Shell(user allow suffix)",
    ]


def test_replace_managed_entries_clear_semantics_keep_markers_with_empty_generated() -> None:
    updated = replace_managed_entries(
        [
            JSON_MANAGED_MARKER_START,
            "Shell(stale)",
            JSON_MANAGED_MARKER_END,
        ],
        [],
        Path("/tmp/cursor.json"),
        "allow",
    )

    assert updated == [JSON_MANAGED_MARKER_START, JSON_MANAGED_MARKER_END]


def test_find_managed_segment_boundaries_and_absence() -> None:
    path = Path("/tmp/managed.json")
    start, end = find_managed_segment(
        ["user", JSON_MANAGED_MARKER_START, "generated", JSON_MANAGED_MARKER_END, "tail"],
        JSON_MANAGED_MARKER_START,
        JSON_MANAGED_MARKER_END,
        path=path,
        key="allow",
    )
    assert start == 1
    assert end == 3

    missing_start, missing_end = find_managed_segment(
        ["user", "tail"],
        JSON_MANAGED_MARKER_START,
        JSON_MANAGED_MARKER_END,
        path=path,
        key="allow",
    )
    assert missing_start is None
    assert missing_end is None


def test_ensure_prefix_rules_file_clear_semantics_preserve_user_text(tmp_path: Path) -> None:
    target = tmp_path / "default.rules"
    target.write_text(
        "\n".join(
            [
                "# user preface",
                MANAGED_MARKER_START,
                'prefix_rule(pattern=["git", "status"], decision="allow")',
                MANAGED_MARKER_END,
                "# user suffix",
                "",
            ]
        ),
        encoding="utf-8",
    )

    before_count, after_count = ensure_prefix_rules_file(target, [])
    updated = target.read_text(encoding="utf-8")

    assert before_count == 1
    assert after_count == 0
    assert MANAGED_MARKER_START in updated
    assert MANAGED_MARKER_END in updated
    assert "prefix_rule(" not in updated
    assert "# user preface" in updated
    assert "# user suffix" in updated


def test_apply_host_artifacts_clears_managed_codex_block_on_zero_rules(tmp_path: Path) -> None:
    codex_rules_path = tmp_path / "default.rules"
    codex_rules_path.write_text(
        "\n".join(
            [
                "# user preface",
                MANAGED_MARKER_START,
                'prefix_rule(pattern=["git", "status"], decision="allow")',
                MANAGED_MARKER_END,
                "# user suffix",
                "",
            ]
        ),
        encoding="utf-8",
    )

    rendered = render_platform_payload(
        {"policy": {"commands": {"allow": [], "deny": [], "require": []}}},
        include_conditional=False,
        cwd=tmp_path,
    )

    result = apply_host_artifacts(rendered, codex_path=codex_rules_path)
    updated = codex_rules_path.read_text(encoding="utf-8")

    assert result["applied"]["codex"]["before"] == 1
    assert result["applied"]["codex"]["after"] == 0
    assert MANAGED_MARKER_START in updated
    assert MANAGED_MARKER_END in updated
    assert "prefix_rule(" not in updated
    assert "# user preface" in updated
    assert "# user suffix" in updated


def test_main_uses_explicit_cwd_for_rendering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps({"policy": {"commands": {"allow": [], "deny": [], "require": []}}}),
        encoding="utf-8",
    )

    explicit_cwd = tmp_path / "deterministic-cwd"
    explicit_cwd.mkdir()
    captured: dict[str, Path | None] = {"cwd": None}

    def fake_render_platform_payload(
        policy_payload: dict[str, object],
        include_conditional: bool = False,
        cwd: Path | None = None,
    ) -> dict[str, object]:
        captured["cwd"] = cwd
        return {
            "policy": {
                "cursor": {"allow": [], "deny": []},
                "claude": {"allow": [], "deny": [], "ask": []},
                "droid": {
                    "commandAllowlist": [],
                    "commandRequestlist": [],
                    "commandDenylist": [],
                },
                "codex": {"rules": []},
                "policy_wrapper": {
                    "schema_version": 1,
                    "required_conditions": [],
                    "commands": [],
                },
            },
            "conditional_rules": [],
            "wrapper_rules": [],
            "wrapper_condition_set": [],
            "unconditional_count": 0,
            "conditional_count": 0,
        }

    monkeypatch.setattr(sync_host_rules, "render_platform_payload", fake_render_platform_payload)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_host_rules.py",
            "--policy-json",
            str(policy_path),
            "--cwd",
            str(explicit_cwd),
        ],
    )

    exit_code = sync_host_rules.main()

    assert exit_code == 0
    assert captured["cwd"] == explicit_cwd.resolve()


def test_main_json_failure_response_for_render_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps({"policy": {"commands": {"allow": [], "deny": [], "require": []}}}),
        encoding="utf-8",
    )

    def failing_render(
        policy_payload: dict[str, object],
        include_conditional: bool = False,
        cwd: Path | None = None,
    ) -> dict[str, object]:
        raise RuntimeError("render boom")

    monkeypatch.setattr(sync_host_rules, "render_platform_payload", failing_render)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_host_rules.py",
            "--policy-json",
            str(policy_path),
            "--json",
        ],
    )

    exit_code = sync_host_rules.main()
    output = capsys.readouterr().out
    parsed = json.loads(output)

    assert exit_code == sync_host_rules.EXIT_RENDER_FAILURE
    assert parsed["ok"] is False
    assert parsed["error"]["code"] == sync_host_rules.EXIT_RENDER_FAILURE
    assert "render failed" in parsed["error"]["message"]


def test_main_json_success_payload_contains_platform_targets_and_rule_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "policy": {
                    "commands": {
                        "allow": ["git status"],
                        "deny": ["rm -rf /"],
                        "require": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_host_rules.py",
            "--policy-json",
            str(policy_path),
            "--cwd",
            str(tmp_path),
            "--json",
        ],
    )

    exit_code = sync_host_rules.main()
    output = capsys.readouterr().out
    parsed = json.loads(output)

    assert exit_code == sync_host_rules.EXIT_SUCCESS
    assert parsed["ok"] is True
    assert parsed["mode"] == "preview"
    assert parsed["summary"]["unconditional_rules"] == 2
    assert parsed["summary"]["conditional_rules"] == 0
    assert parsed["summary"]["total_rules"] == 2
    assert isinstance(parsed["platforms"], list)
    assert {entry["platform"] for entry in parsed["platforms"]} == {
        "codex",
        "cursor",
        "claude",
        "droid",
    }
    for entry in parsed["platforms"]:
        assert entry["mode"] == "preview"
        assert isinstance(entry["target_path"], str)
        assert isinstance(entry["rule_count"], int)
        assert entry["rule_count"] >= 0
        assert isinstance(entry["had_managed_segment_before"], bool)
        assert isinstance(entry["managed_segment_length_after"], int)
        assert entry["managed_segment_length_after"] >= 0


def test_main_json_success_payload_managed_diagnostics_are_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "policy": {
                    "commands": {
                        "allow": ["git status"],
                        "deny": ["rm -rf /"],
                        "require": ["docker push"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    codex_path = tmp_path / "default.rules"
    codex_path.write_text(
        "\n".join(
            [
                "# user before",
                MANAGED_MARKER_START,
                'prefix_rule(pattern=["stale"], decision="allow")',
                MANAGED_MARKER_END,
                "# user after",
                "",
            ]
        ),
        encoding="utf-8",
    )
    cursor_path = tmp_path / "cursor.json"
    cursor_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [JSON_MANAGED_MARKER_START, "Shell(stale)", JSON_MANAGED_MARKER_END],
                    "deny": [],
                }
            }
        ),
        encoding="utf-8",
    )
    claude_path = tmp_path / "claude.json"
    claude_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [],
                    "deny": [],
                    "ask": [JSON_MANAGED_MARKER_START, "Bash(stale)", JSON_MANAGED_MARKER_END],
                }
            }
        ),
        encoding="utf-8",
    )
    droid_path = tmp_path / "droid.json"
    droid_path.write_text(
        json.dumps(
            {
                "commandAllowlist": [],
                "commandRequestlist": [JSON_MANAGED_MARKER_START, "stale", JSON_MANAGED_MARKER_END],
                "commandDenylist": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_host_rules.py",
            "--policy-json",
            str(policy_path),
            "--cwd",
            str(tmp_path),
            "--json",
            "--codex-rules",
            str(codex_path),
            "--cursor-config",
            str(cursor_path),
            "--claude-settings",
            str(claude_path),
            "--factory-settings",
            str(droid_path),
        ],
    )

    exit_code = sync_host_rules.main()
    parsed = json.loads(capsys.readouterr().out)

    assert exit_code == sync_host_rules.EXIT_SUCCESS
    entries = {entry["platform"]: entry for entry in parsed["platforms"]}
    assert entries["codex"]["had_managed_segment_before"] is True
    assert entries["cursor"]["had_managed_segment_before"] is True
    assert entries["claude"]["had_managed_segment_before"] is True
    assert entries["droid"]["had_managed_segment_before"] is True
    assert entries["codex"]["managed_segment_length_after"] == 3
    assert entries["cursor"]["managed_segment_length_after"] == 3
    assert entries["claude"]["managed_segment_length_after"] == 3
    assert entries["droid"]["managed_segment_length_after"] == 3


def test_main_json_failure_response_for_apply_error_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps({"policy": {"commands": {"allow": [], "deny": [], "require": []}}}),
        encoding="utf-8",
    )

    def failing_apply(*args: object, **kwargs: object) -> dict[str, object]:
        raise OSError("apply boom")

    monkeypatch.setattr(sync_host_rules, "apply_host_artifacts", failing_apply)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_host_rules.py",
            "--policy-json",
            str(policy_path),
            "--cwd",
            str(tmp_path),
            "--json",
            "--apply",
        ],
    )

    exit_code = sync_host_rules.main()
    output = capsys.readouterr().out
    parsed = json.loads(output)

    assert exit_code == sync_host_rules.EXIT_APPLY_FAILURE
    assert parsed["ok"] is False
    assert parsed["error"]["code"] == sync_host_rules.EXIT_APPLY_FAILURE
    assert parsed["error"]["message"] == "apply failed: apply boom"


def test_main_json_failure_response_for_write_error_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps({"policy": {"commands": {"allow": [], "deny": [], "require": []}}}),
        encoding="utf-8",
    )

    def failing_write(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(sync_host_rules, "write_host_artifacts", failing_write)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_host_rules.py",
            "--policy-json",
            str(policy_path),
            "--cwd",
            str(tmp_path),
            "--json",
            "--out-dir",
            str(tmp_path / "out"),
        ],
    )

    exit_code = sync_host_rules.main()
    output = capsys.readouterr().out
    parsed = json.loads(output)

    assert exit_code == sync_host_rules.EXIT_APPLY_FAILURE
    assert parsed["ok"] is False
    assert parsed["error"]["code"] == sync_host_rules.EXIT_APPLY_FAILURE
    assert parsed["error"]["message"] == "write failed: disk full"


def test_main_json_failure_response_for_internal_error_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps({"policy": {"commands": {"allow": [], "deny": [], "require": []}}}),
        encoding="utf-8",
    )

    def failing_success_entries(*args: object, **kwargs: object) -> list[dict[str, object]]:
        raise RuntimeError("manifest boom")

    monkeypatch.setattr(sync_host_rules, "_build_success_entries", failing_success_entries)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_host_rules.py",
            "--policy-json",
            str(policy_path),
            "--json",
        ],
    )

    exit_code = sync_host_rules.main()
    output = capsys.readouterr().out
    parsed = json.loads(output)

    assert exit_code == sync_host_rules.EXIT_INTERNAL_ERROR
    assert parsed["ok"] is False
    assert parsed["error"]["code"] == sync_host_rules.EXIT_INTERNAL_ERROR
    assert parsed["error"]["message"] == "internal error: manifest boom"


def test_apply_host_artifacts_fails_on_malformed_json_config(tmp_path: Path) -> None:
    cursor_path = tmp_path / "cursor.json"
    cursor_path.write_text("{", encoding="utf-8")
    rendered = render_platform_payload(
        {"policy": {"commands": {"allow": ["git status"], "deny": [], "require": []}}},
        include_conditional=False,
        cwd=tmp_path,
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        apply_host_artifacts(rendered, cursor_path=cursor_path)


def test_apply_host_artifacts_fails_on_non_object_json_config(tmp_path: Path) -> None:
    cursor_path = tmp_path / "cursor.json"
    cursor_path.write_text("[]", encoding="utf-8")
    rendered = render_platform_payload(
        {"policy": {"commands": {"allow": ["git status"], "deny": [], "require": []}}},
        include_conditional=False,
        cwd=tmp_path,
    )

    with pytest.raises(ValueError, match="host config must be a JSON object"):
        apply_host_artifacts(rendered, cursor_path=cursor_path)


def test_apply_host_artifacts_replaces_managed_sections_and_converges_on_rerun(tmp_path: Path) -> None:
    cursor_path = tmp_path / "cursor.json"
    claude_path = tmp_path / "claude.json"
    droid_path = tmp_path / "droid.json"

    cursor_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [
                        "Shell(user cursor allow)",
                        JSON_MANAGED_MARKER_START,
                        "Shell(stale cursor allow)",
                        JSON_MANAGED_MARKER_END,
                        "Shell(user cursor allow suffix)",
                    ],
                    "deny": [
                        JSON_MANAGED_MARKER_START,
                        "Shell(stale cursor deny)",
                        JSON_MANAGED_MARKER_END,
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    claude_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [JSON_MANAGED_MARKER_START, "Bash(stale claude allow)", JSON_MANAGED_MARKER_END],
                    "deny": [JSON_MANAGED_MARKER_START, "Bash(stale claude deny)", JSON_MANAGED_MARKER_END],
                    "ask": [
                        "Bash(user claude ask)",
                        JSON_MANAGED_MARKER_START,
                        "Bash(stale claude ask)",
                        JSON_MANAGED_MARKER_END,
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    droid_path.write_text(
        json.dumps(
            {
                "commandAllowlist": [JSON_MANAGED_MARKER_START, "stale droid allow", JSON_MANAGED_MARKER_END],
                "commandRequestlist": [JSON_MANAGED_MARKER_START, "stale droid request", JSON_MANAGED_MARKER_END],
                "commandDenylist": [
                    "user droid deny",
                    JSON_MANAGED_MARKER_START,
                    "stale droid deny",
                    JSON_MANAGED_MARKER_END,
                ],
            }
        ),
        encoding="utf-8",
    )

    first_rendered = render_platform_payload(
        {
            "policy": {
                "commands": {
                    "allow": ["git status"],
                    "deny": ["rm -rf /"],
                    "require": ["docker push"],
                }
            }
        },
        include_conditional=False,
        cwd=tmp_path,
    )
    second_rendered = render_platform_payload(
        {
            "policy": {
                "commands": {
                    "allow": ["git log"],
                    "deny": [],
                    "require": ["npm publish"],
                }
            }
        },
        include_conditional=False,
        cwd=tmp_path,
    )

    apply_host_artifacts(
        first_rendered,
        cursor_path=cursor_path,
        claude_path=claude_path,
        droid_path=droid_path,
    )
    apply_host_artifacts(
        second_rendered,
        cursor_path=cursor_path,
        claude_path=claude_path,
        droid_path=droid_path,
    )

    cursor_after_second = json.loads(cursor_path.read_text(encoding="utf-8"))
    claude_after_second = json.loads(claude_path.read_text(encoding="utf-8"))
    droid_after_second = json.loads(droid_path.read_text(encoding="utf-8"))

    assert "Shell(stale cursor allow)" not in cursor_after_second["permissions"]["allow"]
    assert "Shell(stale cursor deny)" not in cursor_after_second["permissions"]["deny"]
    assert "Bash(stale claude allow)" not in claude_after_second["permissions"]["allow"]
    assert "Bash(stale claude deny)" not in claude_after_second["permissions"]["deny"]
    assert "Bash(stale claude ask)" not in claude_after_second["permissions"]["ask"]
    assert "stale droid allow" not in droid_after_second["commandAllowlist"]
    assert "stale droid request" not in droid_after_second["commandRequestlist"]
    assert "stale droid deny" not in droid_after_second["commandDenylist"]

    assert "Shell(user cursor allow)" in cursor_after_second["permissions"]["allow"]
    assert "Shell(user cursor allow suffix)" in cursor_after_second["permissions"]["allow"]
    assert "Bash(user claude ask)" in claude_after_second["permissions"]["ask"]
    assert "user droid deny" in droid_after_second["commandDenylist"]

    assert cursor_after_second["permissions"]["allow"].count(JSON_MANAGED_MARKER_START) == 1
    assert cursor_after_second["permissions"]["allow"].count(JSON_MANAGED_MARKER_END) == 1
    assert claude_after_second["permissions"]["allow"].count(JSON_MANAGED_MARKER_START) == 1
    assert claude_after_second["permissions"]["allow"].count(JSON_MANAGED_MARKER_END) == 1
    assert droid_after_second["commandAllowlist"].count(JSON_MANAGED_MARKER_START) == 1
    assert droid_after_second["commandAllowlist"].count(JSON_MANAGED_MARKER_END) == 1

    cursor_snapshot = cursor_path.read_text(encoding="utf-8")
    claude_snapshot = claude_path.read_text(encoding="utf-8")
    droid_snapshot = droid_path.read_text(encoding="utf-8")

    apply_host_artifacts(
        second_rendered,
        cursor_path=cursor_path,
        claude_path=claude_path,
        droid_path=droid_path,
    )

    assert cursor_path.read_text(encoding="utf-8") == cursor_snapshot
    assert claude_path.read_text(encoding="utf-8") == claude_snapshot
    assert droid_path.read_text(encoding="utf-8") == droid_snapshot


def test_apply_host_artifacts_apply_rerun_is_idempotent_after_refactor(tmp_path: Path) -> None:
    codex_path = tmp_path / "default.rules"
    cursor_path = tmp_path / "cursor.json"
    claude_path = tmp_path / "claude.json"
    droid_path = tmp_path / "droid.json"

    codex_path.write_text(
        "\n".join(
            [
                "# user codex preface",
                MANAGED_MARKER_START,
                'prefix_rule(pattern=["stale"], decision="allow")',
                MANAGED_MARKER_END,
                "# user codex suffix",
                "",
            ]
        ),
        encoding="utf-8",
    )
    cursor_path.write_text(json.dumps({"permissions": {"allow": [], "deny": []}}), encoding="utf-8")
    claude_path.write_text(
        json.dumps({"permissions": {"allow": [], "deny": [], "ask": []}}),
        encoding="utf-8",
    )
    droid_path.write_text(
        json.dumps({"commandAllowlist": [], "commandRequestlist": [], "commandDenylist": []}),
        encoding="utf-8",
    )

    rendered = render_platform_payload(
        {
            "policy": {
                "commands": {
                    "allow": ["git status"],
                    "deny": ["rm -rf /"],
                    "require": [],
                }
            }
        },
        include_conditional=False,
        cwd=tmp_path,
    )

    first = apply_host_artifacts(
        rendered,
        codex_path=codex_path,
        cursor_path=cursor_path,
        claude_path=claude_path,
        droid_path=droid_path,
    )
    codex_snapshot_lines = codex_path.read_text(encoding="utf-8").splitlines()
    cursor_snapshot = cursor_path.read_text(encoding="utf-8")
    claude_snapshot = claude_path.read_text(encoding="utf-8")
    droid_snapshot = droid_path.read_text(encoding="utf-8")

    second = apply_host_artifacts(
        rendered,
        codex_path=codex_path,
        cursor_path=cursor_path,
        claude_path=claude_path,
        droid_path=droid_path,
    )

    assert first["applied"]["codex"]["after"] == second["applied"]["codex"]["after"]
    assert first["applied"]["cursor"]["after"] == second["applied"]["cursor"]["after"]
    assert first["applied"]["claude"]["after"] == second["applied"]["claude"]["after"]
    assert first["applied"]["droid"]["after"] == second["applied"]["droid"]["after"]
    codex_after_lines = codex_path.read_text(encoding="utf-8").splitlines()
    assert [line for line in codex_after_lines if line.strip().startswith("prefix_rule(")] == [
        line for line in codex_snapshot_lines if line.strip().startswith("prefix_rule(")
    ]
    assert cursor_path.read_text(encoding="utf-8") == cursor_snapshot
    assert claude_path.read_text(encoding="utf-8") == claude_snapshot
    assert droid_path.read_text(encoding="utf-8") == droid_snapshot


def test_codex_clear_apply_cycle_preserves_unmanaged_text_before_and_after(tmp_path: Path) -> None:
    codex_path = tmp_path / "default.rules"
    codex_path.write_text(
        "\n".join(
            [
                "# unmanaged before",
                MANAGED_MARKER_START,
                'prefix_rule(pattern=["stale"], decision="allow")',
                MANAGED_MARKER_END,
                "# unmanaged after",
                "",
            ]
        ),
        encoding="utf-8",
    )

    clear_rendered = render_platform_payload(
        {"policy": {"commands": {"allow": [], "deny": [], "require": []}}},
        include_conditional=False,
        cwd=tmp_path,
    )
    apply_rendered = render_platform_payload(
        {"policy": {"commands": {"allow": ["git status"], "deny": ["rm -rf /"], "require": []}}},
        include_conditional=False,
        cwd=tmp_path,
    )

    apply_host_artifacts(clear_rendered, codex_path=codex_path)
    apply_host_artifacts(apply_rendered, codex_path=codex_path)
    updated = codex_path.read_text(encoding="utf-8")

    assert "# unmanaged before" in updated
    assert "# unmanaged after" in updated
    assert updated.count(MANAGED_MARKER_START) == 1
    assert updated.count(MANAGED_MARKER_END) == 1
    assert 'prefix_rule(pattern=["git", "status"], decision="allow")' in updated
    assert 'prefix_rule(pattern=["rm", "-rf", "/"], decision="forbidden")' in updated
    assert 'prefix_rule(pattern=["stale"], decision="allow")' not in updated


def test_cli_invalid_cwd_is_parser_error_without_traceback(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps({"policy": {"commands": {"allow": [], "deny": [], "require": []}}}),
        encoding="utf-8",
    )
    missing_cwd = tmp_path / "missing-cwd"

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "sync_host_rules.py"),
            "--policy-json",
            str(policy_path),
            "--cwd",
            str(missing_cwd),
        ],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == sync_host_rules.EXIT_INVALID_INPUT
    assert "--cwd does not exist" in result.stderr
    assert "Traceback" not in result.stderr
