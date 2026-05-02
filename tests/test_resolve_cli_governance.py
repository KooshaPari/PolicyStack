from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "resolve.py"

EXIT_OK = 0
EXIT_MISSING = 3
EXIT_INVALID = 4


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _write_policy(path: Path, scope: str, **extra: object) -> None:
    payload = {"policy_version": "v1", "scope": scope}
    payload.update(extra)
    _write_yaml(path, payload)


def _create_valid_layout(root: Path) -> None:
    _write_policy(
        root / "policy-config" / "system.yaml", "system", commands={"allow": ["python"]},
    )
    _write_policy(root / "policy-config" / "user.yaml", "user")
    _write_policy(root / "policy-config" / "repo.yaml", "repo")
    _write_policy(root / "policy-config" / "harness" / "local.yaml", "harness")
    _write_policy(
        root / "policy-config" / "task-domain" / "governance.yaml", "task_domain",
    )


def _run_resolver(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--root",
            str(root),
            "--harness",
            "local",
            "--task-domain",
            "governance",
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _policy_hash(policy: dict) -> str:
    return hashlib.sha256(
        json.dumps(policy, sort_keys=True).encode("utf-8"),
    ).hexdigest()


def test_json_success_envelope_contains_contract_and_deterministic_metadata(
    tmp_path: Path,
) -> None:
    _create_valid_layout(tmp_path)

    result = _run_resolver(tmp_path, "--json")

    assert result.returncode == EXIT_OK
    payload = json.loads(result.stdout)
    assert payload["code"] == "ok"
    assert payload["message"] == "policy resolved"
    assert "details" in payload
    assert payload["details"]["scope_count"] == 5
    assert payload["details"]["chain_length"] == 5
    assert (
        payload["details"]["scopes_ordering_assertion_path"] == "result.policy.scopes"
    )
    assert "emit_path" not in payload["details"]
    assert "result" in payload
    assert "policy" in payload["result"]
    assert "policy_hash" in payload["result"]["policy"]
    assert payload["result"]["policy"]["policy_hash"] == _policy_hash(
        payload["result"]["policy"]["policy"],
    )


def test_json_success_envelope_includes_emit_path_when_emit_is_set(
    tmp_path: Path,
) -> None:
    _create_valid_layout(tmp_path)
    emit_path = tmp_path / "resolved.json"

    result = _run_resolver(tmp_path, "--json", "--emit", str(emit_path))

    assert result.returncode == EXIT_OK
    payload = json.loads(result.stdout)
    assert payload["code"] == "ok"
    assert payload["details"]["scope_count"] == 5
    assert payload["details"]["chain_length"] == 5
    assert (
        payload["details"]["scopes_ordering_assertion_path"] == "result.policy.scopes"
    )
    assert payload["details"]["emit_path"] == str(emit_path.resolve())
    assert payload["result"]["policy"]["policy_hash"] == _policy_hash(
        payload["result"]["policy"]["policy"],
    )
    assert emit_path.exists()


def test_json_success_hash_and_scope_ordering_are_stable_across_runs(
    tmp_path: Path,
) -> None:
    _create_valid_layout(tmp_path)
    _write_policy(tmp_path / "policy-config" / "task-instance.yaml", "task_instance")

    first = _run_resolver(
        tmp_path,
        "--json",
        "--task-instance",
        str(tmp_path / "policy-config" / "task-instance.yaml"),
    )
    second = _run_resolver(
        tmp_path,
        "--json",
        "--task-instance",
        str(tmp_path / "policy-config" / "task-instance.yaml"),
    )

    assert first.returncode == EXIT_OK
    assert second.returncode == EXIT_OK
    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    first_policy = first_payload["result"]["policy"]
    second_policy = second_payload["result"]["policy"]
    assert first_policy["policy_hash"] == second_policy["policy_hash"]
    assert first_policy["policy_hash"] == _policy_hash(first_policy["policy"])
    assert [scope for scope, _ in first_policy["scopes"]] == [
        "system",
        "user",
        "repo",
        "harness",
        "task_domain",
        "task_instance",
    ]


def test_json_failure_envelope_for_invalid_policy_uses_stable_contract(
    tmp_path: Path,
) -> None:
    _create_valid_layout(tmp_path)
    _write_yaml(
        tmp_path / "policy-config" / "repo.yaml", {"policy_version": 1, "scope": "repo"},
    )

    result = _run_resolver(tmp_path, "--json")

    assert result.returncode == EXIT_INVALID
    payload = json.loads(result.stdout)
    assert payload["code"] == "invalid"
    assert payload["message"].endswith(": policy_version missing or invalid")
    assert payload.get("details") is None


def test_json_rejects_path_traversal_for_harness_and_task_domain_identifiers(
    tmp_path: Path,
) -> None:
    _create_valid_layout(tmp_path)

    result = _run_resolver(
        tmp_path,
        "--harness",
        "../evil",
        "--task-domain",
        "../governance",
    )

    assert result.returncode == 2
    assert "--harness must not contain path separators" in (
        result.stderr + result.stdout
    )


def test_json_rejects_mismatched_scope_for_harness_and_task_domain(
    tmp_path: Path,
) -> None:
    _create_valid_layout(tmp_path)
    _write_policy(tmp_path / "policy-config" / "harness" / "local.yaml", "repo")

    result = _run_resolver(tmp_path, "--json")

    assert result.returncode == EXIT_INVALID
    payload = json.loads(result.stdout)
    assert payload["code"] == "invalid"
    assert payload["message"] == (
        f"{tmp_path / 'policy-config' / 'harness' / 'local.yaml'}: scope mismatch in chain: "
        "expected harness, got repo"
    )


def test_json_rejects_duplicate_scopes_in_chain(tmp_path: Path) -> None:
    _create_valid_layout(tmp_path)
    _write_policy(
        tmp_path / "policy-config" / "task-domain" / "governance.yaml", "harness",
    )

    result = _run_resolver(tmp_path, "--json")

    assert result.returncode == EXIT_INVALID
    payload = json.loads(result.stdout)
    assert payload["code"] == "invalid"
    assert payload["message"] == "duplicate scope in chain: harness"


def test_json_rejects_non_list_payload_fields_for_append_only_paths(
    tmp_path: Path,
) -> None:
    _create_valid_layout(tmp_path)
    _write_policy(
        tmp_path / "policy-config" / "repo.yaml",
        "repo",
        commands={"allow": "not-a-list"},
    )

    result = _run_resolver(tmp_path, "--json")

    assert result.returncode == EXIT_INVALID
    payload = json.loads(result.stdout)
    assert payload["code"] == "invalid"
    assert payload["message"].endswith("commands.allow must be a list")


def test_json_rejects_non_mapping_parent_for_nested_list_payload_paths(
    tmp_path: Path,
) -> None:
    _create_valid_layout(tmp_path)
    _write_policy(
        tmp_path / "policy-config" / "repo.yaml",
        "repo",
        commands="not-a-dict",
    )

    result = _run_resolver(tmp_path, "--json")

    assert result.returncode == EXIT_INVALID
    payload = json.loads(result.stdout)
    assert payload["code"] == "invalid"
    assert payload["message"] == (
        f"{tmp_path / 'policy-config' / 'repo.yaml'}: "
        "commands.allow: expected mapping at commands"
    )


def test_json_missing_layout_failure_code_and_message_are_stable(
    tmp_path: Path,
) -> None:
    result = _run_resolver(tmp_path, "--json")

    assert result.returncode == EXIT_MISSING
    payload = json.loads(result.stdout)
    assert payload["code"] == "missing"
    assert payload["message"].startswith(
        "no supported config root layout exists; expected one of ",
    )
    assert "policy-config" in payload["message"]
