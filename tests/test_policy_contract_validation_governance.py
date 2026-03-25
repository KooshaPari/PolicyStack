from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_policy_contract.py"

EXIT_SCHEMA = 3
EXIT_MISSING = 4
EXIT_VALIDATION = 5


def _write_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_valid_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "additionalProperties": True,
    }
    path.write_text(json.dumps(schema), encoding="utf-8")


def _run_validator(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--root", str(tmp_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_missing_schema_fails_with_clear_output(tmp_path: Path) -> None:
    result = _run_validator(tmp_path)

    assert result.returncode == EXIT_SCHEMA
    assert "[schema] schema not found" in result.stdout


def test_missing_required_defaults_fail_by_default(tmp_path: Path) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)

    result = _run_validator(tmp_path)

    assert result.returncode == EXIT_MISSING
    assert "[missing]" in result.stdout
    assert "policy-config/system.yaml" in result.stdout
    assert "policy-config/user.yaml" in result.stdout
    assert "policy-config/repo.yaml" in result.stdout
    assert "id=missing-required-input" in result.stdout
    assert "summary checked=0 missing=3 invalid=0" in result.stdout


def test_allow_missing_downgrades_missing_required_defaults_to_skips(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)

    result = _run_validator(tmp_path, "--allow-missing")

    assert result.returncode == 0
    assert "[skip]" in result.stdout
    assert "policy-config/system.yaml" in result.stdout
    assert "policy-config/user.yaml" in result.stdout
    assert "policy-config/repo.yaml" in result.stdout
    assert "validation passed" in result.stdout
    assert "summary checked=0 missing=3 invalid=0" in result.stdout


def test_allow_missing_downgrades_missing_required_explicit_input_to_skip(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)
    missing_path = tmp_path / "policy-config" / "system.yaml"

    result = _run_validator(tmp_path, "--allow-missing", "--input", str(missing_path))

    assert result.returncode == 0
    assert f"[skip] {missing_path} (missing)" in result.stdout
    assert "validation passed" in result.stdout
    assert "summary checked=0 missing=1 invalid=0" in result.stdout


def test_invalid_schema_fails_via_schema_self_validation(tmp_path: Path) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {"name": {"type": "not-a-real-jsonschema-type"}},
            }
        ),
        encoding="utf-8",
    )

    _write_file(tmp_path / "policy-config" / "system.yaml", {"name": "system"})
    _write_file(tmp_path / "policy-config" / "user.yaml", {"name": "user"})
    _write_file(tmp_path / "policy-config" / "repo.yaml", {"name": "repo"})

    result = _run_validator(tmp_path)

    assert result.returncode == EXIT_SCHEMA
    assert "[schema] schema self-validation failed" in result.stdout
    assert "id=schema-invalid" in result.stdout


def test_text_validation_failure_includes_stable_error_id(tmp_path: Path) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)
    _write_file(tmp_path / "policy-config" / "system.yaml", {"name": "system"})
    _write_file(tmp_path / "policy-config" / "user.yaml", {"name": "user"})
    _write_file(tmp_path / "policy-config" / "repo.yaml", {"name": 123})

    result = _run_validator(tmp_path)

    assert result.returncode == EXIT_VALIDATION
    assert "[invalid]" in result.stdout
    assert "id=validation-invalid" in result.stdout
    assert "summary checked=3 missing=0 invalid=1" in result.stdout


def test_parser_error_contract_uses_stable_exit_code_and_machine_readable_id(
    tmp_path: Path,
) -> None:
    result = _run_validator(tmp_path, "--no-such-flag")

    assert result.returncode == 2
    assert "[arg] argument parsing failed:" in result.stdout
    assert "id=arg-parse-error" in result.stdout


def test_json_error_payload_for_missing_required_defaults(tmp_path: Path) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)

    result = _run_validator(tmp_path, "--json")

    assert result.returncode == EXIT_MISSING
    error_lines = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    assert len(error_lines) >= 3
    for payload in error_lines[:3]:
        assert payload["code"] == "missing"
        assert payload["message"] == "required input missing"
        assert "path" in payload
        assert payload.get("details", {}).get("identifier") == "missing-required-input"


def test_json_error_payload_for_validation_failures(tmp_path: Path) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)
    _write_file(tmp_path / "policy-config" / "system.yaml", {"name": "system"})
    _write_file(tmp_path / "policy-config" / "user.yaml", {"name": "user"})
    _write_file(tmp_path / "policy-config" / "repo.yaml", {"name": 123})

    result = _run_validator(tmp_path, "--json")

    assert result.returncode == EXIT_VALIDATION
    payloads = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    validation_payloads = [
        payload for payload in payloads if payload.get("code") == "validation"
    ]
    assert validation_payloads
    payload = validation_payloads[0]
    assert set(payload.keys()) == {"code", "message", "path", "details"}
    assert payload["message"] == "schema validation failed"
    assert "path" in payload
    assert isinstance(payload.get("details"), list)
    assert payload["details"]
    assert "message" in payload["details"][0]


def test_json_success_payload_contains_results_and_summary_counters(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)
    _write_file(tmp_path / "policy-config" / "system.yaml", {"name": "system"})
    _write_file(tmp_path / "policy-config" / "user.yaml", {"name": "user"})
    _write_file(tmp_path / "policy-config" / "repo.yaml", {"name": "repo"})

    result = _run_validator(tmp_path, "--json")

    assert result.returncode == 0
    payloads = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]

    result_payloads = [
        payload
        for payload in payloads
        if payload.get("type") == "result" and payload.get("status") == "ok"
    ]
    assert len(result_payloads) == 3
    assert set(result_payloads[0].keys()) == {"type", "status", "path"}

    summary_payloads = [
        payload for payload in payloads if payload.get("type") == "summary"
    ]
    assert summary_payloads
    assert set(summary_payloads[-1].keys()) == {"type", "checked", "missing", "invalid"}
    assert summary_payloads[-1]["checked"] == 3
    assert summary_payloads[-1]["missing"] == 0
    assert summary_payloads[-1]["invalid"] == 0

    status_payloads = [
        payload for payload in payloads if payload.get("type") == "status"
    ]
    assert status_payloads
    assert status_payloads[-1] == {
        "type": "status",
        "code": "ok",
        "message": "validation passed",
    }


def test_json_success_payload_for_mixed_yaml_and_json_default_discovery(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)
    _write_file(tmp_path / "policy-config" / "system.yaml", {"name": "system"})
    _write_file(tmp_path / "policy-config" / "user.yaml", {"name": "user"})
    _write_file(tmp_path / "policy-config" / "repo.yaml", {"name": "repo"})
    _write_file(
        tmp_path / "policy-config" / "harness" / "harness.yaml", {"name": "harness"}
    )
    _write_json_file(
        tmp_path / "policy-config" / "task-domain" / "domain.json", {"name": "domain"}
    )
    _write_json_file(
        tmp_path / "policy-config" / "task-instance" / "instance.json",
        {"name": "instance"},
    )

    result = _run_validator(tmp_path, "--json")

    assert result.returncode == 0
    payloads = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    ok_results = [
        payload
        for payload in payloads
        if payload.get("type") == "result" and payload.get("status") == "ok"
    ]
    assert len(ok_results) == 6
    summary_payloads = [
        payload for payload in payloads if payload.get("type") == "summary"
    ]
    assert summary_payloads
    assert summary_payloads[-1]["checked"] == 6
    assert summary_payloads[-1]["missing"] == 0
    assert summary_payloads[-1]["invalid"] == 0


def test_json_failure_payload_for_mixed_yaml_and_json_default_discovery(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)
    _write_file(tmp_path / "policy-config" / "system.yaml", {"name": "system"})
    _write_file(tmp_path / "policy-config" / "user.yaml", {"name": "user"})
    _write_file(tmp_path / "policy-config" / "repo.yaml", {"name": "repo"})
    _write_file(
        tmp_path / "policy-config" / "harness" / "harness.yaml", {"name": "harness"}
    )
    _write_json_file(
        tmp_path / "policy-config" / "task-domain" / "domain.json", {"name": "domain"}
    )
    _write_json_file(
        tmp_path / "policy-config" / "task-instance" / "instance.json",
        {"name": 123},
    )

    result = _run_validator(tmp_path, "--json")

    assert result.returncode == EXIT_VALIDATION
    payloads = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    validation_payloads = [
        payload for payload in payloads if payload.get("code") == "validation"
    ]
    assert validation_payloads
    summary_payloads = [
        payload for payload in payloads if payload.get("type") == "summary"
    ]
    assert summary_payloads
    assert summary_payloads[-1]["checked"] == 6
    assert summary_payloads[-1]["missing"] == 0
    assert summary_payloads[-1]["invalid"] == 1


def test_default_discovery_order_is_deterministic_and_deduplicated(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "agent-scope" / "policy_contract.schema.json"
    _write_valid_schema(schema_path)

    _write_file(tmp_path / "policy-config" / "system.yaml", {"name": "system"})
    _write_file(tmp_path / "policy-config" / "user.yaml", {"name": "user"})
    _write_file(tmp_path / "policy-config" / "repo.yaml", {"name": "repo"})

    _write_json_file(
        tmp_path / "policy-config" / "harness" / "beta.json", {"name": "beta"}
    )
    _write_file(tmp_path / "policy-config" / "harness" / "beta.yaml", {"name": "beta"})
    _write_json_file(
        tmp_path / "policy-config" / "task-domain" / "alpha.json", {"name": "alpha"}
    )
    _write_file(
        tmp_path / "policy-config" / "task-domain" / "zeta.yaml", {"name": "zeta"}
    )
    _write_json_file(
        tmp_path / "policy-config" / "task-instance" / "item.json", {"name": "item"}
    )
    _write_file(
        tmp_path / "policy-config" / "task-instance" / "item.yaml", {"name": "item"}
    )

    result = _run_validator(tmp_path, "--json")

    assert result.returncode == 0
    payloads = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    discovered = [
        Path(payload["path"]).relative_to(tmp_path).as_posix()
        for payload in payloads
        if payload.get("type") == "result" and payload.get("status") == "ok"
    ]
    assert discovered == [
        "policy-config/system.yaml",
        "policy-config/user.yaml",
        "policy-config/repo.yaml",
        "policy-config/harness/beta.yaml",
        "policy-config/task-domain/alpha.json",
        "policy-config/task-domain/zeta.yaml",
        "policy-config/task-instance/item.yaml",
    ]
    assert len(discovered) == len(set(discovered))
