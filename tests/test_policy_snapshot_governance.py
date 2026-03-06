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
            self._write_policy(config_root / "task-domain" / "deployment.yaml", "task_domain")
            self._write_policy(config_root / "task-domain" / "query.yaml", "task_domain")
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
            self.assertEqual(write.returncode, 0, write.stdout + write.stderr)
            self.assertTrue(snapshot_path.exists())

            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertIn("policy_hash", payload)
            self.assertIn("scopes", payload)
            self.assertEqual(payload["scopes"][0]["scope"], "system")
            self.assertEqual(
                payload["scopes"][0]["path"],
                "policy-contract/policy-config/system.yaml",
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
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertIn("[ok] snapshot matches", check.stdout)

    def test_snapshot_json_success_payloads_include_deterministic_metadata(self) -> None:
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
            self.assertEqual(write.returncode, 0, write.stdout + write.stderr)
            write_payload = json.loads(write.stdout)
            self.assertEqual(write_payload["status"], "ok")
            self.assertEqual(write_payload["kind"], "write")
            self.assertEqual(write_payload["message"], "wrote snapshot")
            self.assertEqual(write_payload["scope_count"], 5)
            self.assertEqual(write_payload["chain_length"], 5)
            self.assertEqual(write_payload["output_path"], "snapshots/unit.json")

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
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            check_payload = json.loads(check.stdout)
            self.assertEqual(check_payload["status"], "ok")
            self.assertEqual(check_payload["kind"], "check_existing")
            self.assertEqual(check_payload["message"], "snapshot matches")
            self.assertEqual(check_payload["scope_count"], 5)
            self.assertEqual(check_payload["chain_length"], 5)
            self.assertEqual(check_payload["output_path"], "snapshots/unit.json")

    def test_snapshot_write_canonical_and_check_existing_from_clean_repo_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            config_root = root / "policy-contract" / "policy-config"
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(config_root / "task-domain" / "deployment.yaml", "task_domain")
            self._write_policy(config_root / "task-domain" / "query.yaml", "task_domain")

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
            self.assertEqual(
                write_canonical.returncode,
                0,
                write_canonical.stdout + write_canonical.stderr,
            )
            write_payload = json.loads(write_canonical.stdout)
            self.assertEqual(
                set(write_payload.keys()),
                {"status", "kind", "message", "snapshot_count", "output_paths"},
            )
            self.assertEqual(write_payload["status"], "ok")
            self.assertEqual(write_payload["kind"], "write_canonical")
            self.assertEqual(write_payload["message"], "wrote canonical snapshots")
            self.assertEqual(write_payload["snapshot_count"], 2)
            self.assertIsInstance(write_payload["output_paths"], list)
            self.assertEqual(len(write_payload["output_paths"]), 2)
            self.assertEqual(
                write_payload["output_paths"],
                sorted(write_payload["output_paths"]),
            )
            self.assertEqual(
                write_payload["output_paths"],
                [
                    "policy-contract/policy-config/snapshots/policy_snapshot_codex_deployment.json",
                    "policy-contract/policy-config/snapshots/policy_snapshot_codex_query.json",
                ],
            )

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
                self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
                payload = json.loads(check.stdout)
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["kind"], "check_existing")
                self.assertEqual(payload["message"], "snapshot matches")
                self.assertEqual(payload["output_path"], output_rel)

    def test_snapshot_validate_canonical_success_with_custom_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            config_root = root / "policy-contract" / "policy-config"
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(config_root / "task-domain" / "deployment.yaml", "task_domain")
            self._write_policy(config_root / "task-domain" / "query.yaml", "task_domain")
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
            self.assertEqual(
                write_canonical.returncode,
                0,
                write_canonical.stdout + write_canonical.stderr,
            )

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
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
            payload = json.loads(validate.stdout)
            self.assertEqual(
                set(payload.keys()),
                {"status", "kind", "message", "snapshot_count", "output_paths"},
            )
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["kind"], "validate_canonical")
            self.assertEqual(payload["message"], "canonical snapshots match")
            self.assertEqual(payload["snapshot_count"], 2)
            self.assertIsInstance(payload["output_paths"], list)
            self.assertEqual(len(payload["output_paths"]), 2)
            self.assertEqual(
                payload["output_paths"],
                sorted(payload["output_paths"]),
            )
            self.assertEqual(
                payload["output_paths"],
                [
                    "custom-snapshots/policy_snapshot_codex_deployment.json",
                    "custom-snapshots/policy_snapshot_codex_query.json",
                ],
            )

    def test_snapshot_validate_canonical_fails_when_snapshot_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._seed_policy_config(root)
            config_root = root / "policy-contract" / "policy-config"
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(config_root / "task-domain" / "deployment.yaml", "task_domain")
            self._write_policy(config_root / "task-domain" / "query.yaml", "task_domain")

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
            self.assertEqual(validate.returncode, EXIT_MISSING_SNAPSHOT)
            payload = json.loads(validate.stdout)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["kind"], "drift")
            self.assertEqual(payload["message"], "canonical snapshot missing")
            self.assertIn("output_path", payload)
            self.assertIn("harness", payload)
            self.assertIn("task_domain", payload)

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
            self.assertEqual(write.returncode, EXIT_INVALID)
            self.assertIn("[error] resolved policy is empty", write.stdout)
            self.assertFalse(snapshot_path.exists())

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
            repo_file.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

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
            self.assertEqual(check.returncode, EXIT_CHECK_FAILED)
            self.assertIn("[drift] snapshot differs", check.stdout)
            self.assertIn(f"expected_hash={expected_hash}", check.stdout)
            self.assertIn("first_differing_key=policy_hash", check.stdout)
            actual_hash_match = re.search(r"actual_hash=([0-9a-f]{64})", check.stdout)
            self.assertIsNotNone(actual_hash_match, check.stdout)
            self.assertNotEqual(actual_hash_match.group(1), expected_hash)

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
            repo_file.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

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
            self.assertEqual(check.returncode, EXIT_CHECK_FAILED)
            payload = json.loads(check.stdout)
            self.assertEqual(payload["kind"], "drift")
            self.assertEqual(payload["exit_code"], EXIT_CHECK_FAILED)
            self.assertEqual(payload["message"], "snapshot differs")
            self.assertIn("first_differing_key", payload)
            self.assertEqual(payload["first_differing_key"], "policy_hash")
            self.assertEqual(payload["expected_hash"], expected_hash)
            self.assertRegex(payload["actual_hash"], r"^[0-9a-f]{64}$")
            self.assertNotEqual(payload["actual_hash"], expected_hash)
