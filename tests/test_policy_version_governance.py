#!/usr/bin/env python3
"""Tests for policy version governance checks."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

import yaml

EXIT_MISSING_REQUIRED = 2
EXIT_INVALID = 4
EXIT_MIXED = 5


class TestPolicyVersionGovernanceScript(TestCase):
    @staticmethod
    def _script_path() -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "scripts"
            / "check_policy_versions.py"
        )

    @staticmethod
    def _write_policy(path: Path, policy_version: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "policy_version": policy_version,
            "scope": "system",
            "commands": {"allow": [], "deny": [], "require": []},
        }
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _write_policy_json(path: Path, policy_version: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "policy_version": policy_version,
            "scope": "system",
            "commands": {"allow": [], "deny": [], "require": []},
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_accepts_allowed_policy_version_v1(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            policy_file = root / "single.yaml"
            self._write_policy(policy_file, "v1")

            result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--input",
                    str(policy_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == 0, result.stdout + result.stderr
            assert "policy version governance passed" in result.stdout

            json_result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--input",
                    str(policy_file),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert json_result.returncode == 0, json_result.stdout + json_result.stderr
            payload = json.loads(json_result.stdout)
            assert set(payload.keys()) == {"code", "message", "details"}
            assert payload["code"] == "ok"
            assert payload["message"] == "policy version governance passed"
            assert payload["details"]["version"] == "v1"
            assert payload["details"]["summary"] == {"checked": 1, "missing_required": 0, "invalid_versions": 0}

    def test_rejects_disallowed_policy_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            policy_file = root / "single.yaml"
            self._write_policy(policy_file, "v2")

            result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--input",
                    str(policy_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == EXIT_INVALID
            assert "[invalid-version]" in result.stdout

            json_result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--input",
                    str(policy_file),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert json_result.returncode == EXIT_INVALID
            payload = json.loads(json_result.stdout)
            assert set(payload.keys()) == {"code", "message", "details"}
            assert payload["code"] == "invalid"
            assert "message" in payload
            assert "details" in payload
            assert payload["details"]["versions"] == ["v2"]

    def test_detects_mixed_versions_in_default_policy_config_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"

            self._write_policy(config_root / "system.yaml", "v1")
            self._write_policy(config_root / "user.yaml", "v1")
            self._write_policy(config_root / "repo.yaml", "v1")
            self._write_policy(config_root / "harness" / "codex.yaml", "v1")
            self._write_policy_json(
                config_root / "task-domain" / "deployment.json", "v2",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == EXIT_MIXED
            assert "[mixed-version-chain]" in result.stdout
            assert "versions=['v1', 'v2']" in result.stdout
            assert "policy-config/task-domain/deployment.json" in result.stdout

    def test_default_discovery_includes_yaml_and_json_scope_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"

            self._write_policy(config_root / "system.yaml", "v1")
            self._write_policy(config_root / "user.yaml", "v1")
            self._write_policy(config_root / "repo.yaml", "v1")
            self._write_policy_json(config_root / "harness" / "codex.json", "v1")
            self._write_policy(config_root / "task-domain" / "deployment.yaml", "v1")
            self._write_policy_json(
                config_root / "task-instance" / "daily-sync.json", "v1",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == 0, result.stdout + result.stderr
            assert "policy-config/harness/codex.json" in result.stdout
            assert "policy-config/task-domain/deployment.yaml" in result.stdout
            assert "policy-config/task-instance/daily-sync.json" in result.stdout
            assert "policy version governance passed: v1" in result.stdout

    def test_missing_required_default_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"

            self._write_policy(config_root / "user.yaml", "v1")
            self._write_policy(config_root / "repo.yaml", "v1")

            result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == EXIT_MISSING_REQUIRED
            assert "[missing-required] policy-config/system.yaml" in result.stdout
            assert "missing required default policy files:" in result.stdout

            json_result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert json_result.returncode == EXIT_MISSING_REQUIRED
            payload = json.loads(json_result.stdout)
            assert payload["code"] == "missing-required"
            assert "message" in payload
            assert "details" in payload
            assert "policy-config/system.yaml" in payload["details"]["missing_required"]

    def test_missing_required_default_file_can_be_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"

            self._write_policy(config_root / "user.yaml", "v1")
            self._write_policy(config_root / "repo.yaml", "v1")

            result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--allow-missing",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == 0, result.stdout + result.stderr
            assert "[skip-required] policy-config/system.yaml (missing)" in result.stdout
            assert "policy version governance passed: v1" in result.stdout

            json_result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--allow-missing",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert json_result.returncode == 0, json_result.stdout + json_result.stderr
            payload = json.loads(json_result.stdout)
            assert payload["code"] == "ok"
            assert payload["details"]["version"] == "v1"
            assert payload["details"]["summary"] == {"checked": 3, "missing_required": 1, "invalid_versions": 0}
            assert "policy-config/system.yaml" in payload["details"]["missing_required"]

    def test_allow_missing_json_success_envelope_includes_json_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"

            self._write_policy(config_root / "user.yaml", "v1")
            self._write_policy(config_root / "repo.yaml", "v1")
            self._write_policy_json(config_root / "harness" / "codex.json", "v1")

            json_result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--allow-missing",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert json_result.returncode == 0, json_result.stdout + json_result.stderr
            payload = json.loads(json_result.stdout)
            assert payload["code"] == "ok"
            assert payload["message"] == "policy version governance passed"
            assert payload["details"]["version"] == "v1"
            assert payload["details"]["summary"] == {"checked": 4, "missing_required": 1, "invalid_versions": 0}
            assert "policy-config/system.yaml" in payload["details"]["missing_required"]

    def test_default_discovery_order_is_deterministic_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"

            self._write_policy(config_root / "system.yaml", "v1")
            self._write_policy(config_root / "user.yaml", "v1")
            self._write_policy(config_root / "repo.yaml", "v1")

            self._write_policy_json(config_root / "harness" / "beta.json", "v1")
            self._write_policy(config_root / "harness" / "beta.yaml", "v1")
            self._write_policy_json(config_root / "task-domain" / "alpha.json", "v1")
            self._write_policy(config_root / "task-domain" / "zeta.yaml", "v1")
            self._write_policy_json(config_root / "task-instance" / "item.json", "v1")
            self._write_policy(config_root / "task-instance" / "item.yaml", "v1")

            json_result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            assert json_result.returncode == 0, json_result.stdout + json_result.stderr
            payload = json.loads(json_result.stdout)
            assert payload["code"] == "ok"
            assert payload["details"]["policy_files"] == ["policy-config/system.yaml", "policy-config/user.yaml", "policy-config/repo.yaml", "policy-config/harness/beta.yaml", "policy-config/task-domain/alpha.json", "policy-config/task-domain/zeta.yaml", "policy-config/task-instance/item.yaml"]
            assert payload["details"]["summary"] == {"checked": 7, "missing_required": 0, "invalid_versions": 0}
