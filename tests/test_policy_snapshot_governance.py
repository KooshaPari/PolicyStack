#!/usr/bin/env python3
"""Tests for deterministic policy snapshot governance script."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

import yaml

EXIT_CHECK_FAILED = 11
EXIT_MISSING_SNAPSHOT = 12
EXIT_INVALID = 13


class TestPolicySnapshotGovernanceScript(TestCase):
    @staticmethod
    def _script_path() -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "scripts"
            / "generate_policy_snapshot.py"
        )

    @staticmethod
    def _write_policy(path: Path, scope: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "policy_version": "v1",
            "scope": scope,
            "commands": {"allow": [], "deny": [], "require": []},
        }
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _seed_policy_config(self, root: Path) -> None:
        config_root = root / "policy-contract" / "policy-config"
        self._write_policy(config_root / "system.yaml", "system")
        self._write_policy(config_root / "user.yaml", "user")
        self._write_policy(config_root / "repo.yaml", "repo")
        self._write_policy(config_root / "harness" / "unit.yaml", "harness")
        self._write_policy(config_root / "task-domain" / "unit.yaml", "task_domain")

    def _seed_empty_policy_config(self, root: Path) -> None:
        config_root = root / "policy-contract" / "policy-config"
        for rel_path in (
            "system.yaml",
            "user.yaml",
            "repo.yaml",
            "harness/unit.yaml",
            "task-domain/unit.yaml",
        ):
            target = config_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")

    def test_snapshot_write_and_check_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            config_root = root / "policy-contract" / "policy-config"
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(
                config_root / "task-domain" / "deployment.yaml", "task_domain",
            )
            self._write_policy(
                config_root / "task-domain" / "query.yaml", "task_domain",
            )
            snapshot_path = root / "snapshots" / "unit.json"

            write = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--output",
                    str(snapshot_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert write.returncode == 0, write.stdout + write.stderr
            assert snapshot_path.exists()

            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            assert "policy_hash" in payload
            assert "scopes" in payload
            assert payload["scopes"][0]["scope"] == "system"
            assert payload["scopes"][0]["path"] == "policy-contract/policy-config/system.yaml"

            check = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--output",
                    str(snapshot_path),
                    "--check-existing",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert check.returncode == 0, check.stdout + check.stderr
            assert "[ok] snapshot matches" in check.stdout

    def test_snapshot_json_success_payloads_include_deterministic_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            snapshot_path = root / "snapshots" / "unit.json"

            write = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--output",
                    str(snapshot_path),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert write.returncode == 0, write.stdout + write.stderr
            write_payload = json.loads(write.stdout)
            assert write_payload["status"] == "ok"
            assert write_payload["kind"] == "write"
            assert write_payload["message"] == "wrote snapshot"
            assert write_payload["scope_count"] == 5
            assert write_payload["chain_length"] == 5
            assert write_payload["output_path"] == "snapshots/unit.json"

            check = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--output",
                    str(snapshot_path),
                    "--check-existing",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert check.returncode == 0, check.stdout + check.stderr
            check_payload = json.loads(check.stdout)
            assert check_payload["status"] == "ok"
            assert check_payload["kind"] == "check_existing"
            assert check_payload["message"] == "snapshot matches"
            assert check_payload["scope_count"] == 5
            assert check_payload["chain_length"] == 5
            assert check_payload["output_path"] == "snapshots/unit.json"

    def test_snapshot_write_canonical_and_check_existing_from_clean_repo_context(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            config_root = root / "policy-contract" / "policy-config"
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(
                config_root / "task-domain" / "deployment.yaml", "task_domain",
            )
            self._write_policy(
                config_root / "task-domain" / "query.yaml", "task_domain",
            )

            write_canonical = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--write-canonical",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert write_canonical.returncode == 0, write_canonical.stdout + write_canonical.stderr
            write_payload = json.loads(write_canonical.stdout)
            assert set(write_payload.keys()) == {"status", "kind", "message", "snapshot_count", "output_paths"}
            assert write_payload["status"] == "ok"
            assert write_payload["kind"] == "write_canonical"
            assert write_payload["message"] == "wrote canonical snapshots"
            assert write_payload["snapshot_count"] == 2
            assert isinstance(write_payload["output_paths"], list)
            assert len(write_payload["output_paths"]) == 2
            assert write_payload["output_paths"] == sorted(write_payload["output_paths"])
            assert write_payload["output_paths"] == ["policy-contract/policy-config/snapshots/policy_snapshot_codex_deployment.json", "policy-contract/policy-config/snapshots/policy_snapshot_codex_query.json"]

            for task_domain in ("deployment", "query"):
                output_rel = (
                    f"policy-contract/policy-config/snapshots/"
                    f"policy_snapshot_codex_{task_domain}.json"
                )
                check = subprocess.run(
                    [
                        sys.executable,
                        str(self._script_path()),
                        "--root",
                        ".",
                        "--harness",
                        "codex",
                        "--task-domain",
                        task_domain,
                        "--output",
                        output_rel,
                        "--check-existing",
                        "--json",
                    ],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert check.returncode == 0, check.stdout + check.stderr
                payload = json.loads(check.stdout)
                assert payload["status"] == "ok"
                assert payload["kind"] == "check_existing"
                assert payload["message"] == "snapshot matches"
                assert payload["output_path"] == output_rel

    def test_snapshot_validate_canonical_success_with_custom_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            config_root = root / "policy-contract" / "policy-config"
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(
                config_root / "task-domain" / "deployment.yaml", "task_domain",
            )
            self._write_policy(
                config_root / "task-domain" / "query.yaml", "task_domain",
            )
            canonical_dir = root / "custom-snapshots"

            write_canonical = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--write-canonical",
                    "--canonical-dir",
                    str(canonical_dir),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert write_canonical.returncode == 0, write_canonical.stdout + write_canonical.stderr

            validate = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--validate-canonical",
                    "--canonical-dir",
                    str(canonical_dir),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert validate.returncode == 0, validate.stdout + validate.stderr
            payload = json.loads(validate.stdout)
            assert set(payload.keys()) == {"status", "kind", "message", "snapshot_count", "output_paths"}
            assert payload["status"] == "ok"
            assert payload["kind"] == "validate_canonical"
            assert payload["message"] == "canonical snapshots match"
            assert payload["snapshot_count"] == 2
            assert isinstance(payload["output_paths"], list)
            assert len(payload["output_paths"]) == 2
            assert payload["output_paths"] == sorted(payload["output_paths"])
            assert payload["output_paths"] == ["custom-snapshots/policy_snapshot_codex_deployment.json", "custom-snapshots/policy_snapshot_codex_query.json"]

    def test_snapshot_validate_canonical_fails_when_snapshot_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            config_root = root / "policy-contract" / "policy-config"
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(
                config_root / "task-domain" / "deployment.yaml", "task_domain",
            )
            self._write_policy(
                config_root / "task-domain" / "query.yaml", "task_domain",
            )

            validate = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--validate-canonical",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert validate.returncode == EXIT_MISSING_SNAPSHOT
            payload = json.loads(validate.stdout)
            assert payload["status"] == "error"
            assert payload["kind"] == "drift"
            assert payload["message"] == "canonical snapshot missing"
            assert "output_path" in payload
            assert "harness" in payload
            assert "task_domain" in payload

    def test_snapshot_write_fails_for_empty_resolved_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_empty_policy_config(root)
            snapshot_path = root / "snapshots" / "unit.json"

            write = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--output",
                    str(snapshot_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert write.returncode == EXIT_INVALID
            assert "[error] resolved policy is empty" in write.stdout
            assert not snapshot_path.exists()

    def test_snapshot_check_existing_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            snapshot_path = root / "snapshots" / "unit.json"

            _ = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--output",
                    str(snapshot_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            original_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            expected_hash = original_snapshot["policy_hash"]

            # mutate a merged command field so policy hash deterministically changes
            repo_file = root / "policy-contract" / "policy-config" / "repo.yaml"
            payload = yaml.safe_load(repo_file.read_text(encoding="utf-8"))
            payload.setdefault("commands", {})
            payload["commands"].setdefault("allow", [])
            payload["commands"]["allow"].append("deterministic-drift-command")
            repo_file.write_text(
                yaml.safe_dump(payload, sort_keys=False), encoding="utf-8",
            )

            check = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--output",
                    str(snapshot_path),
                    "--check-existing",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert check.returncode == EXIT_CHECK_FAILED
            assert "[drift] snapshot differs" in check.stdout
            assert f"expected_hash={expected_hash}" in check.stdout
            assert "first_differing_key=policy_hash" in check.stdout
            actual_hash_match = re.search(r"actual_hash=([0-9a-f]{64})", check.stdout)
            assert actual_hash_match is not None, check.stdout
            assert actual_hash_match.group(1) != expected_hash

    def test_snapshot_check_existing_detects_drift_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            snapshot_path = root / "snapshots" / "unit.json"

            _ = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--output",
                    str(snapshot_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            original_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            expected_hash = original_snapshot["policy_hash"]

            repo_file = root / "policy-contract" / "policy-config" / "repo.yaml"
            payload = yaml.safe_load(repo_file.read_text(encoding="utf-8"))
            payload.setdefault("commands", {})
            payload["commands"].setdefault("allow", [])
            payload["commands"]["allow"].append("deterministic-drift-command")
            repo_file.write_text(
                yaml.safe_dump(payload, sort_keys=False), encoding="utf-8",
            )

            check = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path()),
                    "--root",
                    str(root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--output",
                    str(snapshot_path),
                    "--check-existing",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert check.returncode == EXIT_CHECK_FAILED
            payload = json.loads(check.stdout)
            assert payload["kind"] == "drift"
            assert payload["exit_code"] == EXIT_CHECK_FAILED
            assert payload["message"] == "snapshot differs"
            assert "first_differing_key" in payload
            assert payload["first_differing_key"] == "policy_hash"
            assert payload["expected_hash"] == expected_hash
            assert re.search(r"^[0-9a-f]{64}$", payload["actual_hash"])
            assert payload["actual_hash"] != expected_hash
