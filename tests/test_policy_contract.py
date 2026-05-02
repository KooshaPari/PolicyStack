#!/usr/bin/env python3
"""Regression tests for policy-contract policy evaluation and sync mapping."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest import TestCase, main
from unittest.mock import patch

import yaml

try:
    from jsonschema import validate as _validate_schema
except ModuleNotFoundError:
    _validate_schema = None

from policy_lib import Condition, ConditionGroup, evaluate_policy, normalize_payload
from resolve import (
    EXIT_CODE_INVALID,
    EXIT_CODE_MISSING,
    MERGE_STRATEGY,
    _validate_host_artifacts,
)
from scripts.sync_host_rules import (
    apply_host_artifacts,
    render_platform_payload,
    write_host_artifacts,
)


class TestConditionGroupAnySemantics(TestCase):
    def test_condition_dict_without_name_rejects_in_parse(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "missing-name",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {"required": False},
                    },
                ],
            },
        }

        with self.assertRaisesRegex(ValueError, "condition dict must include name"):
            evaluate_policy(payload, "git status")

    def test_mode_condition_with_unknown_mode_rejects_in_parse(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "bad-mode",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {
                            "mode": "maybe",
                            "conditions": [],
                        },
                    },
                ],
            },
        }

        with self.assertRaisesRegex(ValueError, "unsupported condition mode"):
            evaluate_policy(payload, "git status")

    def test_unknown_condition_name_rejects_in_parse(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "unknown-condition-name",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {"name": "unknown_condition"},
                    },
                ],
            },
        }

        with self.assertRaisesRegex(
            ValueError, "unsupported condition: unknown_condition",
        ):
            evaluate_policy(payload, "git status")

    def test_invalid_condition_type_rejected_during_parse(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "bad-condition-type",
                        "action": "allow",
                        "match": "git status",
                        "conditions": 123,
                    },
                ],
            },
        }

        with self.assertRaisesRegex(ValueError, "unsupported condition type"):
            evaluate_policy(payload, "git status")

    def test_invalid_on_mismatch_rejected_during_parse(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "bad-on-mismatch",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {
                            "all": [{"name": "git_is_worktree"}],
                        },
                        "on_mismatch": "maybe",
                    },
                ],
            },
        }

        with self.assertRaisesRegex(ValueError, "invalid on_mismatch action"):
            evaluate_policy(payload, "git status")

    def test_condition_group_requires_mode_condition_list(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "bad-mode",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {"mode": "all", "conditions": "not-a-list"},
                    },
                ],
            },
        }

        with self.assertRaisesRegex(ValueError, "'conditions' must be a list"):
            evaluate_policy(payload, "git status")

    def test_condition_group_any_requires_required_match(self) -> None:
        group = ConditionGroup(
            mode="any",
            items=(
                Condition("required", required=True),
                Condition("optional", required=False),
            ),
        )
        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {
                "required": lambda _cwd: (False, "required-false"),
                "optional": lambda _cwd: (True, "optional-true"),
            },
            clear=False,
        ):
            ok, reasons = group.evaluate(Path.cwd())
            self.assertFalse(ok)
            self.assertEqual(reasons, ["required-false", "optional-true"])

    def test_condition_group_any_with_optional_conditions_allows_match(self) -> None:
        group = ConditionGroup(
            mode="any",
            items=(
                Condition("optional-a", required=False),
                Condition("optional-b", required=False),
            ),
        )
        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {
                "optional-a": lambda _cwd: (False, "optional-a-false"),
                "optional-b": lambda _cwd: (True, "optional-b-true"),
            },
            clear=False,
        ):
            ok, reasons = group.evaluate(Path.cwd())
            self.assertTrue(ok)
            self.assertEqual(reasons, ["optional-a-false", "optional-b-true"])

    def test_condition_group_nested_required_children_flow_as_expected(self) -> None:
        group = ConditionGroup(
            mode="all",
            items=(
                ConditionGroup(
                    mode="all",
                    items=(
                        Condition("required-parent", required=True),
                        Condition("optional-child", required=False),
                    ),
                ),
                ConditionGroup(
                    mode="any",
                    items=(
                        Condition("required-sibling", required=True),
                        Condition("optional-sibling", required=False),
                    ),
                ),
            ),
        )
        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {
                "required-parent": lambda _cwd: (True, "required-parent-true"),
                "optional-child": lambda _cwd: (False, "optional-child-false"),
                "required-sibling": lambda _cwd: (False, "required-sibling-false"),
                "optional-sibling": lambda _cwd: (True, "optional-sibling-true"),
            },
            clear=False,
        ):
            ok, reasons = group.evaluate(Path.cwd())
            self.assertFalse(ok)
            self.assertEqual(
                reasons,
                [
                    "required-parent-true",
                    "optional-child-false",
                    "required-sibling-false",
                    "optional-sibling-true",
                ],
            )

    def test_condition_group_nested_optional_any_passes_without_required(self) -> None:
        group = ConditionGroup(
            mode="all",
            items=(
                ConditionGroup(
                    mode="any",
                    items=(
                        Condition("optional-a", required=False),
                        Condition("optional-b", required=False),
                    ),
                ),
            ),
        )
        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {
                "optional-a": lambda _cwd: (False, "optional-a-false"),
                "optional-b": lambda _cwd: (True, "optional-b-true"),
            },
            clear=False,
        ):
            ok, reasons = group.evaluate(Path.cwd())
            self.assertTrue(ok)
            self.assertEqual(
                reasons,
                ["optional-a-false", "optional-b-true"],
            )

    def test_condition_group_nested_any_required_false_optional_true_conflict(
        self,
    ) -> None:
        group = ConditionGroup(
            mode="all",
            items=(
                ConditionGroup(
                    mode="any",
                    items=(
                        Condition("inner-required", required=True),
                        Condition("inner-optional", required=False),
                    ),
                ),
                Condition("outer-optional", required=False),
            ),
        )
        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {
                "inner-required": lambda _cwd: (False, "inner-required-false"),
                "inner-optional": lambda _cwd: (True, "inner-optional-true"),
                "outer-optional": lambda _cwd: (False, "outer-optional-false"),
            },
            clear=False,
        ):
            ok, reasons = group.evaluate(Path.cwd())
            self.assertFalse(ok)
            self.assertEqual(
                reasons,
                [
                    "inner-required-false",
                    "inner-optional-true",
                    "outer-optional-false",
                ],
            )

    def test_any_mode_with_required_and_optional_failure(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "mixed-any",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {
                            "any": [
                                {"name": "git_is_worktree", "required": True},
                                {"name": "git_clean_worktree", "required": False},
                                {"name": "git_synced_to_upstream", "required": False},
                            ],
                        },
                    },
                ],
            },
        }

        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {
                "git_is_worktree": lambda _cwd: (False, "git_is_worktree"),
                "git_clean_worktree": lambda _cwd: (True, "git_clean_worktree"),
                "git_synced_to_upstream": lambda _cwd: (True, "git_synced_to_upstream"),
            },
            clear=False,
        ):
            decision, _, rule = evaluate_policy(payload, "git status")

        self.assertEqual(decision, "request")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "mixed-any")

        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {
                "git_is_worktree": lambda _cwd: (True, "git_is_worktree"),
                "git_clean_worktree": lambda _cwd: (False, "git_clean_worktree"),
                "git_synced_to_upstream": lambda _cwd: (
                    False,
                    "git_synced_to_upstream",
                ),
            },
            clear=False,
        ):
            decision, _, rule = evaluate_policy(payload, "git status")

        self.assertEqual(decision, "allow")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "mixed-any")

    def test_root_string_condition_in_policy_lib_defaults_to_required(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "root-string",
                        "action": "allow",
                        "match": "git status",
                        "conditions": "git_clean_worktree",
                        "on_mismatch": "request",
                    },
                ],
            },
        }

        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {"git_clean_worktree": lambda _cwd: (True, "git_clean_worktree")},
            clear=False,
        ):
            decision, reason, rule = evaluate_policy(payload, "git status")

        self.assertEqual(decision, "allow")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "root-string")
        self.assertEqual(
            rule.conditions, normalize_payload(payload, Path.cwd())[0].conditions,
        )

        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {"git_clean_worktree": lambda _cwd: (False, "git_clean_worktree")},
            clear=False,
        ):
            decision, reason, rule = evaluate_policy(payload, "git status")

        self.assertEqual(decision, "request")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "root-string")

    def test_command_matcher_validation_is_enforced_by_parser(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "bad-matcher",
                        "action": "allow",
                        "match": {"fuzzy": "git status"},
                    },
                ],
            },
        }

        with self.assertRaisesRegex(ValueError, "unsupported matcher"):
            evaluate_policy(payload, "git status")

    def test_conditional_exact_and_prefix_matcher_with_on_mismatch_end_to_end(
        self,
    ) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "exact-block",
                        "action": "deny",
                        "match": "git status",
                        "on_mismatch": "request",
                    },
                    {
                        "id": "prefix-fallback",
                        "action": "allow",
                        "match": {"prefix": "git checkout"},
                        "conditions": {"all": ["git_is_worktree"]},
                        "on_mismatch": "request",
                    },
                ],
            },
        }

        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {"git_is_worktree": lambda _cwd: (False, "git_is_worktree")},
            clear=False,
        ):
            decision, _, rule = evaluate_policy(payload, "git status")
            self.assertEqual(decision, "deny")
            self.assertEqual(rule.rule_id, "exact-block")

            decision, _, rule = evaluate_policy(payload, "git checkout main")
            self.assertEqual(decision, "request")
            self.assertEqual(rule.rule_id, "prefix-fallback")

    def test_root_condition_without_on_mismatch_allows_lower_rule_precedence(
        self,
    ) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "nested-allow-omitted-on-mismatch",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {
                            "all": [
                                {"name": "git_is_worktree"},
                                {
                                    "name": "git_clean_worktree",
                                    "required": False,
                                },
                            ],
                        },
                    },
                    {
                        "id": "deny-fallback",
                        "action": "deny",
                        "match": "git status",
                    },
                ],
            },
        }

        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {
                "git_is_worktree": lambda _cwd: (False, "git_is_worktree"),
                "git_clean_worktree": lambda _cwd: (True, "git_clean_worktree"),
            },
            clear=False,
        ):
            decision, reason, rule = evaluate_policy(payload, "git status")

        self.assertEqual(decision, "deny")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "deny-fallback")


class TestPolicyLibNormalizationValidation(TestCase):
    def test_normalize_payload_requires_mapping_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "policy payload must be a mapping"):
            normalize_payload([], Path.cwd())

    def test_normalize_payload_rejects_non_mapping_policy_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "'policy' must be a mapping"):
            normalize_payload({"policy": []}, Path.cwd())

    def test_normalize_payload_rejects_non_mapping_commands(self) -> None:
        payload = {"policy": {"commands": []}}
        with self.assertRaisesRegex(ValueError, "policy.commands must be a map"):
            normalize_payload(payload, Path.cwd())

    def test_normalize_payload_rejects_non_list_command_rule_entry(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": "not-a-list",
            },
        }
        with self.assertRaisesRegex(ValueError, "policy.command_rules must be a list"):
            normalize_payload(payload, Path.cwd())

    def test_normalize_payload_rejects_non_map_command_rule_item(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [1, {}],
            },
        }
        with self.assertRaisesRegex(ValueError, "command_rule\\[0\\] must be a map"):
            normalize_payload(payload, Path.cwd())

    def test_normalize_payload_rejects_non_string_command_entry(self) -> None:
        payload = {
            "policy": {
                "commands": {
                    "allow": ["git status", 123],
                    "deny": [],
                    "require": [],
                },
            },
        }
        with self.assertRaisesRegex(
            ValueError, "policy.commands.allow\\[1] must be a non-empty string",
        ):
            normalize_payload(payload, Path.cwd())

    def test_normalize_payload_rejects_non_list_command_allow(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": "git status", "deny": [], "require": []},
            },
        }
        with self.assertRaisesRegex(ValueError, "policy.commands.allow must be a list"):
            normalize_payload(payload, Path.cwd())

    def test_normalize_payload_rejects_empty_command_entry(self) -> None:
        payload = {
            "policy": {
                "commands": {
                    "allow": ["   "],
                    "deny": [],
                    "require": [],
                },
            },
        }
        with self.assertRaisesRegex(
            ValueError, "policy.commands.allow\\[0] must be a non-empty string",
        ):
            normalize_payload(payload, Path.cwd())

    def test_normalize_payload_rejects_empty_command_rule_pattern(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "bad-pattern",
                        "action": "allow",
                        "match": "   ",
                    },
                ],
            },
        }
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            normalize_payload(payload, Path.cwd())

    def test_normalize_payload_rejects_empty_command_rule_pattern_key(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "bad-pattern-key",
                        "action": "allow",
                        "pattern": "   ",
                    },
                ],
            },
        }
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            normalize_payload(payload, Path.cwd())

    def test_normalize_payload_rejects_non_string_command_rule_pattern(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "bad-pattern-type",
                        "action": "allow",
                        "match": 123,
                    },
                ],
            },
        }
        with self.assertRaisesRegex(
            ValueError,
            "matcher pattern must be string|match or pattern must be a non-empty string",
        ):
            normalize_payload(payload, Path.cwd())


class TestWrapperConditionSemanticsParity(TestCase):
    fixtures_path = (
        Path(__file__).parent / "fixtures" / "condition_semantics_cases.json"
    )
    command = "policy-wrapper-condition-fixture-probe"

    @staticmethod
    def _predict_decision(expect: dict[str, object]) -> str:
        return (
            "request"
            if expect.get("has_error") or not expect.get("passed")
            else "allow"
        )

    @staticmethod
    def _load_schema() -> dict[str, Any] | None:
        if _validate_schema is None:
            return None
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "agent-scope"
            / "policy_wrapper.schema.json"
        )
        with schema_path.open(encoding="utf-8") as handle:
            return json.loads(handle.read())

    @staticmethod
    def _validate_wrapper_bundle(
        payload: dict[str, object], schema: dict[str, Any],
    ) -> None:
        assert _validate_schema is not None
        _validate_schema(payload, schema)

    def _build_go_binary(self, binary: Path) -> bool:
        if binary.exists():
            return True

        go_source = binary.parent
        if shutil.which("go") is None:
            return False

        build = subprocess.run(
            ["go", "build", "-o", str(binary), "."],
            cwd=str(go_source),
            capture_output=True,
            text=True,
        )
        if build.returncode != 0:
            return False
        return binary.exists()

    @staticmethod
    def _build_rust_binary(root: Path) -> bool:
        binary = root / "wrappers" / "rust" / "target" / "debug" / "policy-wrapper"
        if binary.exists():
            return True
        if shutil.which("cargo") is None:
            return False

        build = subprocess.run(
            ["cargo", "build", "--locked"],
            cwd=str(root / "wrappers" / "rust"),
            capture_output=True,
            text=True,
            check=False,
        )
        if build.returncode != 0:
            return False
        return binary.exists()

    @staticmethod
    def _build_zig_binary(root: Path) -> bool:
        binary = root / "wrappers" / "zig" / "zig-out" / "bin" / "policy-wrapper"
        if binary.exists():
            return True
        if shutil.which("zig") is None:
            return False

        build = subprocess.run(
            ["zig", "build"],
            cwd=str(root / "wrappers" / "zig"),
            capture_output=True,
            text=True,
            check=False,
        )
        if build.returncode != 0:
            return False
        return binary.exists()

    @staticmethod
    def _smoke_wrapper(
        binary: Path, command: str = "policy-wrapper-condition-fixture-probe",
    ) -> bool:
        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-smoke-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            bundle = {
                "schema_version": 1,
                "required_conditions": [],
                "commands": [
                    {
                        "id": "smoke",
                        "source": "smoke",
                        "action": "allow",
                        "on_mismatch": "request",
                        "matcher": "exact",
                        "pattern": command,
                        "normalized_pattern": command,
                        "conditions": {"all": []},
                        "platform_action": "allow",
                        "shell_entry": f"Shell({command})",
                        "bash_entry": f"Bash({command})",
                    },
                ],
            }
            json.dump(bundle, handle)
            handle.flush()

            completed = subprocess.run(
                [str(binary), "--bundle", handle.name, "--command", command, "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            return completed.returncode == 0

    def _load_fixture(self) -> dict[str, object]:
        with self.fixtures_path.open(encoding="utf-8") as handle:
            return json.loads(handle.read())

    def _resolve_wrapper_binaries(self) -> dict[str, Path]:
        root = Path(__file__).resolve().parent.parent
        wrappers = {
            "go": [
                root / "wrappers" / "go" / "policy-wrapper",
                root / "wrappers" / "go" / "policy-wrapper.exe",
            ],
            "rust": [
                root / "wrappers" / "rust" / "target" / "release" / "policy-wrapper",
                root / "wrappers" / "rust" / "target" / "debug" / "policy-wrapper",
            ],
            "zig": [
                root / "wrappers" / "zig" / "zig-out" / "bin" / "policy-wrapper",
                root / "wrappers" / "zig" / "zig-out" / "bin" / "policy-wrapper.exe",
            ],
        }

        resolved: dict[str, Path] = {}
        for name, candidates in wrappers.items():
            executable = next(
                (candidate for candidate in candidates if candidate.exists()), None,
            )
            if executable is not None:
                if self._smoke_wrapper(executable):
                    resolved[name] = executable
                continue
            if name == "go" and self._build_go_binary(candidates[0]):
                candidate = candidates[0]
            elif name == "rust":
                candidate = (
                    root / "wrappers" / "rust" / "target" / "debug" / "policy-wrapper"
                    if self._build_rust_binary(root)
                    else None
                )
            elif name == "zig":
                candidate = (
                    root / "wrappers" / "zig" / "zig-out" / "bin" / "policy-wrapper"
                    if self._build_zig_binary(root)
                    else None
                )
            else:
                candidate = None

            if candidate is not None and self._smoke_wrapper(candidate):
                resolved[name] = candidate
        return resolved

    def _run_wrapper(self, binary: Path, bundle_path: Path) -> dict[str, object]:
        return self._run_wrapper_with_command(binary, bundle_path, self.command, None)

    def _run_wrapper_with_command(
        self,
        binary: Path,
        bundle_path: Path,
        command: str,
        env: dict[str, str] | None,
    ) -> dict[str, object]:
        completed = subprocess.run(
            [
                str(binary),
                "--bundle",
                str(bundle_path),
                "--command",
                command,
                "--json",
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"{binary} returned {completed.returncode}: {completed.stderr.strip()}",
        )
        self.assertGreater(
            len(completed.stdout),
            0,
            f"{binary} returned empty JSON stdout for command {command}: {completed.stderr.strip()}",
        )
        return json.loads(completed.stdout)

    @staticmethod
    def _run_wrapper_failure(
        binary: Path,
        bundle_path: Path,
        command: str,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                str(binary),
                "--bundle",
                str(bundle_path),
                "--command",
                command,
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def _dispatch_script_path() -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "wrappers"
            / "policy-wrapper-dispatch.sh"
        )

    @staticmethod
    def _write_fake_dispatch_binary(root: Path, body: str) -> Path:
        binary = root / "policy-wrapper-fake"
        binary.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n" + body + "\n",
            encoding="utf-8",
        )
        binary.chmod(0o755)
        return binary

    def _run_dispatch_script(
        self,
        args: list[str],
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [str(self._dispatch_script_path()), *args]
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    @staticmethod
    def _write_bundle(path: Path, body: dict[str, Any]) -> None:
        path.write_text(json.dumps(body), encoding="utf-8")

    @staticmethod
    def _write_fake_git(path: Path, rev_list_output: str) -> Path:
        script = path / "git"
        script.write_text(
            f"""#!/usr/bin/env bash
set -euo pipefail

if [[ \"$1\" == \"rev-parse\" && \"$2\" == \"--abbrev-ref\" && \"$3\" == \"--symbolic-full-name\" && \"$4\" == \"@{{u}}\" ]]; then
  echo \"upstream/main\"
  exit 0
fi

if [[ \"$1\" == \"rev-list\" ]]; then
  printf '%s\\n' \"{rev_list_output}\"
  exit 0
fi

echo \"unexpected git call: $@\" >&2
exit 1
""",
            encoding="utf-8",
        )
        script.chmod(0o755)
        return script

    def test_wrapper_semantics_case_parity_across_languages(self) -> None:
        fixture = self._load_fixture()
        wrappers = self._resolve_wrapper_binaries()
        if not wrappers:
            self.skipTest(
                "Wrapper binaries missing; run go build / cargo build / zig build first",
            )

        cases = fixture["cases"]
        base_rule = {
            "schema_version": 1,
            "required_conditions": [],
            "commands": [],
        }

        for case in cases:
            command_rule = {
                "id": f"fixture-{case['id']}",
                "source": "condition-fixture",
                "action": "allow",
                "on_mismatch": "request",
                "matcher": "exact",
                "pattern": self.command,
                "normalized_pattern": self.command,
                "conditions": case["conditions"],
                "platform_action": "allow",
                "shell_entry": f"Shell({self.command})",
                "bash_entry": f"Bash({self.command})",
            }

            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="policy-wrapper-case-",
                suffix=".json",
                encoding="utf-8",
            ) as handle:
                bundle = {**base_rule, "commands": [command_rule]}
                json.dump(bundle, handle)
                handle.flush()
                results = {
                    name: self._run_wrapper(binary, Path(handle.name))
                    for name, binary in wrappers.items()
                }

            decisions = {name: result["decision"] for name, result in results.items()}
            self.assertEqual(
                len(set(decisions.values())),
                1,
                f"Case {case['id']} produced divergent decisions: {decisions}",
            )

            expected = case["expect"]
            expectation = self._predict_decision(expected)
            for name, result in results.items():
                self.assertEqual(
                    result["decision"], expectation, f"{case['id']}-{name}",
                )
                self.assertTrue(result["matched"], f"{case['id']}-{name}")
                self.assertEqual(
                    result["condition_passed"],
                    expected["passed"],
                    f"{case['id']}-{name}",
                )
                self.assertEqual(
                    result["has_required"],
                    expected["has_required"],
                    f"{case['id']}-{name}",
                )
                self.assertEqual(
                    bool(result.get("error")),
                    bool(expected["has_error"]),
                    f"{case['id']}-{name}",
                )
                self.assertEqual(
                    len(result.get("condition_reasons", [])),
                    expected["reason_count"],
                    f"{case['id']}-{name}",
                )
                if "error_contains" in expected:
                    self.assertIn(
                        expected["error_contains"],
                        result.get("error", ""),
                        f"{case['id']}-{name}",
                    )

    def test_wrapper_precedence_remains_deny_request_allow(self) -> None:
        wrappers = self._resolve_wrapper_binaries()
        if not wrappers:
            self.skipTest(
                "Wrapper binaries missing; run go build / cargo build / zig build first",
            )

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-precedence-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            bundle = {
                "schema_version": 1,
                "required_conditions": [],
                "commands": [
                    {
                        "id": "precedence-allow",
                        "source": "condition-fixture",
                        "action": "allow",
                        "on_mismatch": "request",
                        "matcher": "exact",
                        "pattern": self.command,
                        "normalized_pattern": self.command,
                        "conditions": {"all": []},
                        "platform_action": "allow",
                        "shell_entry": f"Shell({self.command})",
                        "bash_entry": f"Bash({self.command})",
                    },
                    {
                        "id": "precedence-request",
                        "source": "condition-fixture",
                        "action": "allow",
                        "on_mismatch": "request",
                        "matcher": "exact",
                        "pattern": self.command,
                        "normalized_pattern": self.command,
                        "conditions": {
                            "all": ["unsupported_condition_request_precedence"],
                        },
                        "platform_action": "allow",
                        "shell_entry": f"Shell({self.command})",
                        "bash_entry": f"Bash({self.command})",
                    },
                    {
                        "id": "precedence-deny",
                        "source": "condition-fixture",
                        "action": "deny",
                        "on_mismatch": None,
                        "matcher": "exact",
                        "pattern": self.command,
                        "normalized_pattern": self.command,
                        "conditions": {"all": []},
                        "platform_action": "deny",
                        "shell_entry": f"Shell({self.command})",
                        "bash_entry": f"Bash({self.command})",
                    },
                ],
            }
            json.dump(bundle, handle)
            handle.flush()
            results = {
                name: self._run_wrapper(binary, Path(handle.name))
                for name, binary in wrappers.items()
            }

        for name, result in results.items():
            self.assertEqual(result["decision"], "deny", name)
            self.assertTrue(result["matched"], name)
            self.assertEqual(
                result["rule_id"],
                "precedence-deny",
                name,
            )

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-precedence-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            bundle["commands"] = bundle["commands"][:-1]
            json.dump(bundle, handle)
            handle.flush()
            results = {
                name: self._run_wrapper(binary, Path(handle.name))
                for name, binary in wrappers.items()
            }

        for name, result in results.items():
            self.assertEqual(result["decision"], "request", name)
            self.assertTrue(result["matched"], name)
            self.assertEqual(
                result["rule_id"],
                "precedence-request",
                name,
            )

    def test_wrapper_allow_and_request_rule_parity(self) -> None:
        wrappers = self._resolve_wrapper_binaries()
        if not wrappers:
            self.skipTest(
                "Wrapper binaries missing; run go build / cargo build / zig build first",
            )

        command = "policy-wrapper-allow-request-parity"
        allow_rule: dict[str, Any] = {
            "id": "allow-vs-request-allow",
            "source": "condition-fixture",
            "action": "allow",
            "matcher": "exact",
            "pattern": command,
            "normalized_pattern": command,
            "conditions": {"all": []},
            "platform_action": "allow",
            "shell_entry": f"Shell({command})",
            "bash_entry": f"Bash({command})",
        }
        request_rule: dict[str, Any] = {
            "id": "allow-vs-request-request",
            "source": "condition-fixture",
            "action": "request",
            "matcher": "exact",
            "pattern": command,
            "normalized_pattern": command,
            "conditions": {"all": []},
            "platform_action": "request",
            "shell_entry": f"Shell({command})",
            "bash_entry": f"Bash({command})",
        }

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-allow-request-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            json.dump(
                {
                    "schema_version": 1,
                    "required_conditions": [],
                    "commands": [allow_rule, request_rule],
                },
                handle,
            )
            handle.flush()
            results = {
                name: self._run_wrapper_with_command(
                    binary, Path(handle.name), command, None,
                )
                for name, binary in wrappers.items()
            }

        for name, result in results.items():
            self.assertEqual(result["decision"], "request", name)
            self.assertEqual(result.get("rule_id"), "allow-vs-request-request", name)
            self.assertTrue(result["matched"], name)
            self.assertTrue(result["condition_passed"], name)

    def test_wrapper_empty_condition_group_behavior(self) -> None:
        wrappers = self._resolve_wrapper_binaries()
        if not wrappers:
            self.skipTest(
                "Wrapper binaries missing; run go build / cargo build / zig build first",
            )

        command_all = "policy-wrapper-empty-all"
        command_any = "policy-wrapper-empty-any"
        command_mode_all = "policy-wrapper-empty-mode-all"
        command_mode_any = "policy-wrapper-empty-mode-any"
        command_root_array = "policy-wrapper-empty-root-array"

        rules: list[dict[str, Any]] = [
            {
                "id": "empty-all",
                "source": "condition-fixture",
                "action": "request",
                "on_mismatch": "deny",
                "matcher": "exact",
                "pattern": command_all,
                "normalized_pattern": command_all,
                "conditions": {"all": []},
                "platform_action": "request",
                "shell_entry": f"Shell({command_all})",
                "bash_entry": f"Bash({command_all})",
            },
            {
                "id": "empty-any",
                "source": "condition-fixture",
                "action": "deny",
                "on_mismatch": "allow",
                "matcher": "exact",
                "pattern": command_any,
                "normalized_pattern": command_any,
                "conditions": {"any": []},
                "platform_action": "deny",
                "shell_entry": f"Shell({command_any})",
                "bash_entry": f"Bash({command_any})",
            },
            {
                "id": "empty-mode-all",
                "source": "condition-fixture",
                "action": "allow",
                "matcher": "exact",
                "pattern": command_mode_all,
                "normalized_pattern": command_mode_all,
                "conditions": {"mode": "all", "conditions": []},
                "platform_action": "allow",
                "shell_entry": f"Shell({command_mode_all})",
                "bash_entry": f"Bash({command_mode_all})",
            },
            {
                "id": "empty-mode-any",
                "source": "condition-fixture",
                "action": "allow",
                "on_mismatch": "request",
                "matcher": "exact",
                "pattern": command_mode_any,
                "normalized_pattern": command_mode_any,
                "conditions": {"mode": "any", "conditions": []},
                "platform_action": "allow",
                "shell_entry": f"Shell({command_mode_any})",
                "bash_entry": f"Bash({command_mode_any})",
            },
            {
                "id": "empty-root-array",
                "source": "condition-fixture",
                "action": "allow",
                "matcher": "exact",
                "pattern": command_root_array,
                "normalized_pattern": command_root_array,
                "conditions": [],
                "platform_action": "allow",
                "shell_entry": f"Shell({command_root_array})",
                "bash_entry": f"Bash({command_root_array})",
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-empty-group-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            json.dump(
                {
                    "schema_version": 1,
                    "required_conditions": [],
                    "commands": rules,
                },
                handle,
            )
            handle.flush()
            expected = {
                command_all: ("request", False),
                command_any: ("deny", False),
                command_mode_all: ("allow", False),
                command_mode_any: ("allow", False),
                command_root_array: ("allow", True),
            }
            for name, binary in wrappers.items():
                for command, (decision, has_required) in expected.items():
                    result = self._run_wrapper_with_command(
                        binary, Path(handle.name), command, None,
                    )
                    self.assertEqual(result["decision"], decision, f"{name}-{command}")
                    self.assertTrue(result["matched"], f"{name}-{command}")
                    self.assertEqual(
                        result["has_required"], has_required, f"{name}-{command}",
                    )
                    self.assertEqual(
                        len(result.get("condition_reasons", [])),
                        0,
                        f"{name}-{command}",
                    )
                    self.assertEqual(result.get("error", ""), "", f"{name}-{command}")
                    if command == command_all:
                        self.assertEqual(
                            result.get("rule_id"), "empty-all", f"{name}-{command}",
                        )
                    elif command == command_any:
                        self.assertEqual(
                            result.get("rule_id"), "empty-any", f"{name}-{command}",
                        )
                    elif command == command_mode_all:
                        self.assertEqual(
                            result.get("rule_id"),
                            "empty-mode-all",
                            f"{name}-{command}",
                        )
                    elif command == command_mode_any:
                        self.assertEqual(
                            result.get("rule_id"),
                            "empty-mode-any",
                            f"{name}-{command}",
                        )
                    else:
                        self.assertEqual(
                            result.get("rule_id"),
                            "empty-root-array",
                            f"{name}-{command}",
                        )

    def test_wrapper_rejects_malformed_bundle_with_non_zero_exit(self) -> None:
        wrappers = self._resolve_wrapper_binaries()
        if not wrappers:
            self.skipTest(
                "Wrapper binaries missing; run go build / cargo build / zig build first",
            )

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-malformed-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            handle.write("{")
            handle.flush()
            results = {
                name: self._run_wrapper_failure(binary, Path(handle.name), self.command)
                for name, binary in wrappers.items()
            }

        for name, completed in results.items():
            self.assertNotEqual(
                completed.returncode,
                0,
                f"{name} returned success for malformed bundle",
            )
            self.assertTrue(
                completed.stderr.strip(),
                f"{name} did not emit parse error for malformed bundle",
            )
        self.assertEqual(
            len({result.returncode for result in results.values()}),
            1,
            "Malformed bundle exit codes diverged across wrappers",
        )

    def test_wrapper_precedence_does_not_rely_on_eval_errors(self) -> None:
        wrappers = self._resolve_wrapper_binaries()
        if not wrappers:
            self.skipTest(
                "Wrapper binaries missing; run go build / cargo build / zig build first",
            )

        command = "policy-wrapper-no-eval-error-precedence"
        allow_rule: dict[str, Any] = {
            "id": "allow-no-eval-error",
            "source": "condition-fixture",
            "action": "allow",
            "on_mismatch": "request",
            "matcher": "exact",
            "pattern": command,
            "normalized_pattern": command,
            "conditions": {"all": []},
            "platform_action": "allow",
            "shell_entry": f"Shell({command})",
            "bash_entry": f"Bash({command})",
        }
        request_rule: dict[str, Any] = {
            "id": "request-no-eval-error",
            "source": "condition-fixture",
            "action": "request",
            "matcher": "exact",
            "pattern": command,
            "normalized_pattern": command,
            "conditions": {"all": []},
            "platform_action": "request",
            "shell_entry": f"Shell({command})",
            "bash_entry": f"Bash({command})",
        }
        deny_rule: dict[str, Any] = {
            "id": "deny-no-eval-error",
            "source": "condition-fixture",
            "action": "deny",
            "matcher": "exact",
            "pattern": command,
            "normalized_pattern": command,
            "conditions": {"all": []},
            "platform_action": "deny",
            "shell_entry": f"Shell({command})",
            "bash_entry": f"Bash({command})",
        }

        with tempfile.TemporaryDirectory() as fake_git_dir:
            fake_git_dir = Path(fake_git_dir)
            self._write_fake_git(fake_git_dir, "0 0 1")
            env = os.environ.copy()
            env["PATH"] = f"{fake_git_dir}:{env['PATH']}"

            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="policy-wrapper-precedence-no-error-",
                suffix=".json",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    {
                        "schema_version": 1,
                        "required_conditions": [],
                        "commands": [allow_rule, request_rule, deny_rule],
                    },
                    handle,
                )
                handle.flush()
                results = {
                    name: self._run_wrapper_with_command(
                        binary,
                        Path(handle.name),
                        command,
                        env,
                    )
                    for name, binary in wrappers.items()
                }

            for name, result in results.items():
                self.assertEqual(result["decision"], "deny", name)
                self.assertTrue(result["matched"], name)
                self.assertEqual(result.get("rule_id"), "deny-no-eval-error", name)
                self.assertEqual(result.get("error", ""), "", name)

            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="policy-wrapper-precedence-no-error-",
                suffix=".json",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    {
                        "schema_version": 1,
                        "required_conditions": [],
                        "commands": [allow_rule, request_rule],
                    },
                    handle,
                )
                handle.flush()
                results = {
                    name: self._run_wrapper_with_command(
                        binary,
                        Path(handle.name),
                        command,
                        env,
                    )
                    for name, binary in wrappers.items()
                }

            for name, result in results.items():
                self.assertEqual(result["decision"], "request", name)
                self.assertTrue(result["matched"], name)
                self.assertEqual(result.get("rule_id"), "request-no-eval-error", name)
                self.assertEqual(result.get("error", ""), "", name)

            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="policy-wrapper-precedence-no-error-",
                suffix=".json",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    {
                        "schema_version": 1,
                        "required_conditions": [],
                        "commands": [allow_rule],
                    },
                    handle,
                )
                handle.flush()
                results = {
                    name: self._run_wrapper_with_command(
                        binary,
                        Path(handle.name),
                        command,
                        env,
                    )
                    for name, binary in wrappers.items()
                }

            for name, result in results.items():
                self.assertEqual(result["decision"], "allow", name)
                self.assertTrue(result["matched"], name)
                self.assertEqual(result.get("rule_id"), "allow-no-eval-error", name)
                self.assertEqual(result.get("error", ""), "", name)

    def test_wrapper_action_precedence_with_omitted_on_mismatch_fields(self) -> None:
        wrappers = self._resolve_wrapper_binaries()
        if not wrappers:
            self.skipTest(
                "Wrapper binaries missing; run go build / cargo build / zig build first",
            )

        command = "policy-wrapper-omit-on-mismatch"
        rule_allow: dict[str, Any] = {
            "id": "omit-on-mismatch-allow",
            "source": "condition-fixture",
            "action": "allow",
            "matcher": "exact",
            "pattern": command,
            "normalized_pattern": command,
            "conditions": {"all": ["unsupported_condition_omit_on_mismatch"]},
            "platform_action": "allow",
            "shell_entry": f"Shell({command})",
            "bash_entry": f"Bash({command})",
        }
        request_rule: dict[str, Any] = {
            "id": "omit-on-mismatch-request",
            "source": "condition-fixture",
            "action": "request",
            "matcher": "exact",
            "pattern": command,
            "normalized_pattern": command,
            "conditions": {"all": []},
            "platform_action": "request",
            "shell_entry": f"Shell({command})",
            "bash_entry": f"Bash({command})",
        }
        deny_rule: dict[str, Any] = {
            "id": "omit-on-mismatch-deny",
            "source": "condition-fixture",
            "action": "deny",
            "matcher": "exact",
            "pattern": command,
            "normalized_pattern": command,
            "conditions": {"all": []},
            "platform_action": "deny",
            "shell_entry": f"Shell({command})",
            "bash_entry": f"Bash({command})",
        }

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-omit-on-mismatch-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            json.dump(
                {
                    "schema_version": 1,
                    "required_conditions": [],
                    "commands": [rule_allow, request_rule, deny_rule],
                },
                handle,
            )
            handle.flush()
            results = {
                name: self._run_wrapper_with_command(
                    binary, Path(handle.name), command, None,
                )
                for name, binary in wrappers.items()
            }

        for name, result in results.items():
            self.assertEqual(result["decision"], "deny", name)
            self.assertTrue(result["matched"], name)
            self.assertEqual(result.get("rule_id"), "omit-on-mismatch-deny", name)
            self.assertEqual(result.get("error", ""), "", name)

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-omit-on-mismatch-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            json.dump(
                {
                    "schema_version": 1,
                    "required_conditions": [],
                    "commands": [request_rule, deny_rule],
                },
                handle,
            )
            handle.flush()
            results = {
                name: self._run_wrapper_with_command(
                    binary, Path(handle.name), command, None,
                )
                for name, binary in wrappers.items()
            }

        for name, result in results.items():
            self.assertEqual(result["decision"], "deny", name)
            self.assertTrue(result["matched"], name)
            self.assertEqual(result.get("rule_id"), "omit-on-mismatch-deny", name)
            self.assertEqual(result.get("error", ""), "", name)

    def test_dispatch_script_prefers_debug_rust_after_release(self) -> None:
        script_path = (
            Path(__file__).resolve().parent.parent
            / "wrappers"
            / "policy-wrapper-dispatch.sh"
        )
        script = script_path.read_text(encoding="utf-8")
        release_candidate = "${script_dir}/rust/target/release/policy-wrapper"
        debug_candidate = "${script_dir}/rust/target/debug/policy-wrapper"
        self.assertIn(release_candidate, script)
        self.assertIn(debug_candidate, script)
        self.assertLess(
            script.index(release_candidate),
            script.index(debug_candidate),
        )

    def test_dispatch_script_missing_binary_uses_missing_default_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            bundle = {"schema_version": 1, "required_conditions": [], "commands": []}
            bundle_path = tmpdir / "policy-wrapper-rules.json"
            self._write_bundle(bundle_path, bundle)
            result = self._run_dispatch_script(
                [
                    "--bundle",
                    str(bundle_path),
                    "--command",
                    "policy-wrapper-check",
                    "--json",
                    "--binary",
                    str(tmpdir / "does-not-exist"),
                    "--missing-policy-default",
                    "request",
                    "--malformed-bundle-default",
                    "allow",
                    "--condition-eval-error-default",
                    "allow",
                ],
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["decision"], "request")
            self.assertEqual(payload["fallback"], "request")
            self.assertEqual(payload["fallback_reason"], "missing-binary")

    def test_dispatch_script_require_binary_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            bundle_path = tmpdir / "policy-wrapper-rules.json"
            self._write_bundle(bundle_path, {"schema_version": 1, "commands": []})
            result = self._run_dispatch_script(
                [
                    "--bundle",
                    str(bundle_path),
                    "--command",
                    "policy-wrapper-check",
                    "--binary",
                    str(tmpdir / "does-not-exist"),
                    "--require-binary",
                    "--missing-policy-default",
                    "request",
                ],
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "required policy wrapper binary not found or unusable", result.stderr,
            )

    def test_dispatch_script_uses_specific_fallback_for_malformed_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            bundle = tmpdir / "policy-wrapper-rules.json"
            self._write_bundle(bundle, {"schema_version": 1, "commands": []})
            binary = self._write_fake_dispatch_binary(
                tmpdir,
                "echo not-json",
            )
            result = self._run_dispatch_script(
                [
                    "--bundle",
                    str(bundle),
                    "--command",
                    "policy-wrapper-check",
                    "--json",
                    "--binary",
                    str(binary),
                    "--malformed-bundle-default",
                    "deny",
                ],
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["decision"], "deny")
            self.assertEqual(payload["fallback"], "deny")
            self.assertEqual(payload["fallback_reason"], "wrapper-json-parse-failed")

    def test_dispatch_script_uses_condition_eval_fallback_on_condition_errors(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            bundle = tmpdir / "policy-wrapper-rules.json"
            self._write_bundle(bundle, {"schema_version": 1, "commands": []})
            wrapper_payload = {
                "decision": "allow",
                "matched": False,
                "condition_passed": False,
                "condition_reasons": ["git_synced_to_upstream"],
                "error": "git_synced_to_upstream: malformed upstream counts",
            }
            binary = self._write_fake_dispatch_binary(
                tmpdir,
                "echo '" + json.dumps(wrapper_payload) + "'",
            )
            result = self._run_dispatch_script(
                [
                    "--bundle",
                    str(bundle),
                    "--command",
                    "policy-wrapper-check",
                    "--json",
                    "--binary",
                    str(binary),
                    "--condition-eval-error-default",
                    "request",
                ],
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["decision"], "request")
            self.assertEqual(payload["fallback"], "request")
            self.assertEqual(
                payload["fallback_reason"],
                "wrapper-condition-eval-error:git_synced_to_upstream: malformed upstream counts",
            )

    def test_wrapper_glob_character_class_matches_across_languages(self) -> None:
        wrappers = self._resolve_wrapper_binaries()
        if not wrappers:
            self.skipTest(
                "Wrapper binaries missing; run go build / cargo build / zig build first",
            )

        command = "policy-wrapper-charclass-a"
        bundle = {
            "schema_version": 1,
            "required_conditions": [],
            "commands": [
                {
                    "id": "charclass",
                    "source": "condition-fixture",
                    "action": "allow",
                    "on_mismatch": "request",
                    "matcher": "glob",
                    "pattern": command,
                    "normalized_pattern": command,
                    "conditions": {"all": []},
                    "platform_action": "allow",
                    "shell_entry": f"Shell({command})",
                    "bash_entry": f"Bash({command})",
                },
            ],
        }
        pattern = "policy-wrapper-charclass-[ab]"
        bundle["commands"][0]["pattern"] = pattern
        bundle["commands"][0]["normalized_pattern"] = "policy-wrapper-charclass-[ab]"

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-glob-class-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            json.dump(bundle, handle)
            handle.flush()
            results = {
                name: self._run_wrapper_with_command(
                    binary,
                    Path(handle.name),
                    "policy-wrapper-charclass-a",
                    None,
                )
                for name, binary in wrappers.items()
            }

        for name, result in results.items():
            self.assertEqual(result["decision"], "allow", name)
            self.assertTrue(result["matched"], name)

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-glob-class-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            json.dump(bundle, handle)
            handle.flush()
            results = {
                name: self._run_wrapper_with_command(
                    binary,
                    Path(handle.name),
                    "policy-wrapper-charclass-c",
                    None,
                )
                for name, binary in wrappers.items()
            }

        for name, result in results.items():
            self.assertEqual(result["decision"], "allow")
            self.assertFalse(result["matched"], name)

        pattern = "policy-wrapper-charclass-[!a]"
        bundle["commands"][0]["pattern"] = pattern
        bundle["commands"][0]["normalized_pattern"] = pattern

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-glob-class-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            json.dump(bundle, handle)
            handle.flush()
            results = {
                name: self._run_wrapper_with_command(
                    binary,
                    Path(handle.name),
                    "policy-wrapper-charclass-a",
                    None,
                )
                for name, binary in wrappers.items()
            }

        for name, result in results.items():
            self.assertEqual(result["decision"], "allow", name)
            self.assertTrue(result["matched"], name)

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="policy-wrapper-glob-class-",
            suffix=".json",
            encoding="utf-8",
        ) as handle:
            json.dump(bundle, handle)
            handle.flush()
            results = {
                name: self._run_wrapper_with_command(
                    binary,
                    Path(handle.name),
                    "policy-wrapper-charclass-c",
                    None,
                )
                for name, binary in wrappers.items()
            }

        for name, result in results.items():
            self.assertEqual(result["decision"], "allow")
            self.assertFalse(result["matched"], name)

    def test_git_synced_to_upstream_strict_count_parsing(self) -> None:
        wrappers = self._resolve_wrapper_binaries()
        if not wrappers:
            self.skipTest(
                "Wrapper binaries missing; run go build / cargo build / zig build first",
            )

        command = "policy-wrapper-upstream-check"
        base_rule = {
            "id": "upstream-strict",
            "source": "condition-fixture",
            "action": "allow",
            "on_mismatch": "request",
            "matcher": "exact",
            "pattern": command,
            "normalized_pattern": command,
            "conditions": {"name": "git_synced_to_upstream"},
            "platform_action": "allow",
            "shell_entry": f"Shell({command})",
            "bash_entry": f"Bash({command})",
        }

        with tempfile.TemporaryDirectory() as fake_git_dir:
            fake_git_dir = Path(fake_git_dir)
            self._write_fake_git(fake_git_dir, "0 0")
            env = os.environ.copy()
            env["PATH"] = f"{fake_git_dir}:{env['PATH']}"

            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="policy-wrapper-upstream-valid-",
                suffix=".json",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    {
                        "schema_version": 1,
                        "required_conditions": [],
                        "commands": [base_rule],
                    },
                    handle,
                )
                handle.flush()
                results = {
                    name: self._run_wrapper_with_command(
                        binary,
                        Path(handle.name),
                        command,
                        env,
                    )
                    for name, binary in wrappers.items()
                }

            for name, result in results.items():
                self.assertEqual(result["decision"], "allow", name)
                self.assertTrue(result["condition_passed"], name)

            self._write_fake_git(fake_git_dir, "0 0 1")
            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="policy-wrapper-upstream-invalid-",
                suffix=".json",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    {
                        "schema_version": 1,
                        "required_conditions": [],
                        "commands": [base_rule],
                    },
                    handle,
                )
                handle.flush()
                results = {
                    name: self._run_wrapper_with_command(
                        binary,
                        Path(handle.name),
                        command,
                        env,
                    )
                    for name, binary in wrappers.items()
                }

            for name, result in results.items():
                self.assertEqual(result["decision"], "request", name)
                self.assertFalse(result["condition_passed"], name)
                self.assertEqual(result.get("error", ""), "", name)

            self._write_fake_git(fake_git_dir, "x y")
            with tempfile.NamedTemporaryFile(
                mode="w",
                prefix="policy-wrapper-upstream-error-",
                suffix=".json",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    {
                        "schema_version": 1,
                        "required_conditions": [],
                        "commands": [base_rule],
                    },
                    handle,
                )
                handle.flush()
                results = {
                    name: self._run_wrapper_with_command(
                        binary,
                        Path(handle.name),
                        command,
                        env,
                    )
                    for name, binary in wrappers.items()
                }

            for name, result in results.items():
                self.assertEqual(result["decision"], "request", name)
                self.assertFalse(result["condition_passed"], name)
                self.assertNotEqual(result.get("error", ""), "")

    def test_rendered_wrapper_bundle_matches_schema(self) -> None:
        if _validate_schema is None:
            self.skipTest("jsonschema dependency is unavailable")

        schema = self._load_schema()
        assert schema is not None
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "schema-check",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {
                            "all": [
                                "git_is_worktree",
                                {"name": "git_clean_worktree", "required": False},
                            ],
                        },
                    },
                ],
            },
        }
        rendered = render_platform_payload(payload, include_conditional=True)
        self._validate_wrapper_bundle(rendered["policy"]["policy_wrapper"], schema)

    def test_wrapper_required_conditions_align_with_condition_set(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "wrapper-cond-align-1",
                        "action": "allow",
                        "match": {"prefix": "git checkout"},
                        "conditions": {
                            "all": [
                                {"name": "git_is_worktree", "required": True},
                                {"name": "git_clean_worktree", "required": False},
                            ],
                        },
                    },
                ],
            },
        }

        rendered = render_platform_payload(payload, include_conditional=True)
        wrapper_payload = rendered["policy"]["policy_wrapper"]
        expected_conditions = sorted(rendered["wrapper_condition_set"])

        self.assertEqual(wrapper_payload["required_conditions"], expected_conditions)
        self.assertEqual(
            wrapper_payload["required_conditions"],
            ["git_is_worktree"],
            "Only required conditions should be emitted in metadata",
        )
        self.assertEqual(
            rendered["wrapper_condition_set"],
            ["git_is_worktree"],
        )

        optional_only = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "wrapper-cond-align-2",
                        "action": "allow",
                        "match": {"prefix": "git status"},
                        "conditions": {
                            "all": [
                                {"name": "git_clean_worktree", "required": False},
                                {"name": "git_is_worktree", "required": False},
                            ],
                        },
                    },
                ],
            },
        }

        rendered_optional_only = render_platform_payload(
            optional_only, include_conditional=True,
        )
        self.assertEqual(
            rendered_optional_only["policy"]["policy_wrapper"]["required_conditions"],
            [],
        )
        self.assertEqual(rendered_optional_only["wrapper_condition_set"], [])

    def test_wrapper_required_conditions_deduplicated_and_sorted(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "wrapper-dup-1",
                        "action": "allow",
                        "match": {"prefix": "git checkout"},
                        "conditions": {
                            "all": [
                                {"name": "git_is_worktree"},
                                {"name": "git_synced_to_upstream"},
                                {"name": "git_is_worktree", "required": True},
                            ],
                        },
                    },
                    {
                        "id": "wrapper-dup-2",
                        "action": "allow",
                        "match": {"prefix": "git merge"},
                        "conditions": {
                            "any": [
                                {"name": "git_synced_to_upstream"},
                                {"name": "git_is_worktree", "required": False},
                            ],
                        },
                    },
                ],
            },
        }

        rendered = render_platform_payload(payload, include_conditional=True)
        required_conditions = rendered["policy"]["policy_wrapper"][
            "required_conditions"
        ]
        self.assertEqual(
            required_conditions, ["git_is_worktree", "git_synced_to_upstream"],
        )
        self.assertEqual(rendered["wrapper_condition_set"], required_conditions)


class TestHostRendering(TestCase):
    def test_droid_render_request_and_deny_are_separate(self) -> None:
        payload = {
            "commands": {
                "allow": ["git status"],
                "deny": ["git reset --hard"],
                "require": ["git checkout*"],
            },
        }

        rendered = render_platform_payload(payload, include_conditional=False)
        host_rules = rendered["policy"]

        self.assertEqual(
            host_rules["droid"]["commandRequestlist"],
            ["git checkout*"],
        )
        self.assertEqual(
            host_rules["droid"]["commandDenylist"],
            ["git reset --hard"],
        )

    def test_apply_host_rules_writes_droid_requestlist(self) -> None:
        payload = {
            "commands": {
                "allow": ["git status"],
                "deny": ["git reset --hard"],
                "require": ["git checkout*"],
            },
        }

        rendered = render_platform_payload(payload, include_conditional=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            droid_path = Path(tmpdir) / "factory.settings.json"
            droid_path.write_text(
                json.dumps(
                    {"commandAllowlist": ["ls"], "commandDenylist": ["rm -rf /"]},
                ),
                encoding="utf-8",
            )
            apply_host_artifacts(
                rendered,
                droid_path=droid_path,
            )
            updated = json.loads(droid_path.read_text(encoding="utf-8"))

            self.assertIn("git status", updated["commandAllowlist"])
            self.assertIn("git checkout*", updated["commandRequestlist"])
            self.assertIn("git reset --hard", updated["commandDenylist"])

    def test_conditional_export_does_not_mutate_unconditional_host_rules(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "uncond-allow",
                        "action": "allow",
                        "match": "git status",
                    },
                    {
                        "id": "uncond-deny",
                        "action": "deny",
                        "match": "git reset --hard",
                    },
                    {
                        "id": "cond-allow",
                        "action": "allow",
                        "match": {"prefix": "git checkout"},
                        "conditions": {"all": ["git_is_worktree"]},
                    },
                ],
            },
        }

        uncond = render_platform_payload(payload, include_conditional=False)
        with_conditional = render_platform_payload(payload, include_conditional=True)

        base_policy = uncond["policy"]
        conditional_policy = with_conditional["policy"]

        self.assertIn("Shell(git status)", base_policy["cursor"]["allow"])
        for rule in base_policy["cursor"]["allow"]:
            self.assertIn(rule, conditional_policy["cursor"]["allow"])
        self.assertIn("Shell(git checkout *)", conditional_policy["cursor"]["allow"])
        self.assertEqual(
            conditional_policy["cursor"]["deny"],
            base_policy["cursor"]["deny"],
        )
        self.assertIn("Shell(git reset --hard)", conditional_policy["cursor"]["deny"])
        self.assertIn("Shell(git reset --hard)", base_policy["cursor"]["deny"])

        for rule in base_policy["claude"]["allow"]:
            self.assertIn(rule, conditional_policy["claude"]["allow"])
        for rule in base_policy["claude"]["deny"]:
            self.assertIn(rule, conditional_policy["claude"]["deny"])
        for rule in base_policy["claude"]["ask"]:
            self.assertIn(rule, conditional_policy["claude"]["ask"])
        self.assertEqual(
            set(conditional_policy["claude"]["allow"])
            - set(base_policy["claude"]["allow"]),
            {"Bash(git checkout *)"},
        )
        self.assertEqual(
            conditional_policy["droid"]["commandAllowlist"],
            ["git status", "git checkout *"],
        )
        self.assertEqual(
            conditional_policy["droid"]["commandDenylist"],
            base_policy["droid"]["commandDenylist"],
        )
        self.assertEqual(
            conditional_policy["droid"]["commandRequestlist"],
            base_policy["droid"]["commandRequestlist"],
        )

        for rule in base_policy["codex"]["rules"]:
            self.assertIn(rule, conditional_policy["codex"]["rules"])

        self.assertIn(
            'prefix_rule(pattern=["git", "checkout", "*"], decision="allow")',
            conditional_policy["codex"]["rules"],
        )

    def test_conditional_request_export_does_not_pollute_static_deny_or_ask(
        self,
    ) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "uncond-allow",
                        "action": "allow",
                        "match": "git status",
                    },
                    {
                        "id": "uncond-deny",
                        "action": "deny",
                        "match": "git reset --hard",
                    },
                    {
                        "id": "cond-request",
                        "action": "request",
                        "match": {"prefix": "git checkout"},
                        "conditions": {"all": ["git_clean_worktree"]},
                    },
                    {
                        "id": "uncond-ask",
                        "action": "request",
                        "match": "git log",
                    },
                ],
            },
        }

        base = render_platform_payload(payload, include_conditional=False)["policy"]
        with_conditional = render_platform_payload(payload, include_conditional=True)[
            "policy"
        ]

        self.assertEqual(
            with_conditional["cursor"]["allow"],
            base["cursor"]["allow"],
        )
        self.assertIn("Shell(git checkout *)", with_conditional["cursor"]["deny"])
        self.assertEqual(len(with_conditional["cursor"]["deny"]), 3)
        self.assertIn("Shell(git reset --hard)", with_conditional["cursor"]["deny"])
        self.assertIn("Shell(git log)", with_conditional["cursor"]["deny"])

        for rule in base["claude"]["allow"]:
            self.assertIn(rule, with_conditional["claude"]["allow"])
        self.assertEqual(
            sorted(with_conditional["claude"]["ask"]),
            sorted(base["claude"]["ask"] + ["Bash(git checkout *)"]),
        )
        self.assertEqual(
            with_conditional["claude"]["deny"],
            base["claude"]["deny"],
        )

        self.assertEqual(
            with_conditional["droid"]["commandDenylist"],
            base["droid"]["commandDenylist"],
        )
        self.assertEqual(
            sorted(with_conditional["droid"]["commandRequestlist"]),
            sorted(base["droid"]["commandRequestlist"] + ["git checkout *"]),
        )

        for rule in base["codex"]["rules"]:
            self.assertIn(rule, with_conditional["codex"]["rules"])
        self.assertIn(
            'prefix_rule(pattern=["git", "checkout", "*"], decision="prompt")',
            with_conditional["codex"]["rules"],
        )

    def test_conditional_allow_request_deny_export_preserves_host_parity(self) -> None:
        payload = {
            "policy": {
                "commands": {
                    "allow": ["git status"],
                    "deny": ["git reset --hard"],
                    "require": [],
                },
                "command_rules": [
                    {
                        "id": "cond-allow",
                        "action": "allow",
                        "match": {"prefix": "git checkout"},
                        "conditions": {"all": ["git_is_worktree"]},
                    },
                    {
                        "id": "cond-request",
                        "action": "request",
                        "match": {"prefix": "git push"},
                        "conditions": {"all": ["git_clean_worktree"]},
                    },
                    {
                        "id": "cond-deny",
                        "action": "deny",
                        "match": {"prefix": "git log"},
                        "conditions": {"all": ["git_synced_to_upstream"]},
                    },
                ],
            },
        }

        base = render_platform_payload(payload, include_conditional=False)["policy"]
        with_conditional = render_platform_payload(payload, include_conditional=True)[
            "policy"
        ]

        self.assertEqual(
            sorted(with_conditional["cursor"]["allow"]),
            sorted(base["cursor"]["allow"] + ["Shell(git checkout *)"]),
        )
        self.assertEqual(
            sorted(with_conditional["cursor"]["deny"]),
            sorted(base["cursor"]["deny"] + ["Shell(git push *)", "Shell(git log *)"]),
        )

        self.assertEqual(
            sorted(with_conditional["claude"]["allow"]),
            sorted(base["claude"]["allow"] + ["Bash(git checkout *)"]),
        )
        self.assertEqual(
            sorted(with_conditional["claude"]["ask"]),
            sorted(base["claude"]["ask"] + ["Bash(git push *)"]),
        )
        self.assertEqual(
            sorted(with_conditional["claude"]["deny"]),
            sorted(base["claude"]["deny"] + ["Bash(git log *)"]),
        )

        self.assertEqual(
            sorted(with_conditional["droid"]["commandAllowlist"]),
            sorted(base["droid"]["commandAllowlist"] + ["git checkout *"]),
        )
        self.assertEqual(
            sorted(with_conditional["droid"]["commandRequestlist"]),
            sorted(base["droid"]["commandRequestlist"] + ["git push *"]),
        )
        self.assertEqual(
            sorted(with_conditional["droid"]["commandDenylist"]),
            sorted(base["droid"]["commandDenylist"] + ["git log *"]),
        )

        for rule in base["codex"]["rules"]:
            self.assertIn(rule, with_conditional["codex"]["rules"])
        self.assertIn(
            'prefix_rule(pattern=["git", "checkout", "*"], decision="allow")',
            with_conditional["codex"]["rules"],
        )
        self.assertIn(
            'prefix_rule(pattern=["git", "push", "*"], decision="prompt")',
            with_conditional["codex"]["rules"],
        )
        self.assertIn(
            'prefix_rule(pattern=["git", "log", "*"], decision="forbidden")',
            with_conditional["codex"]["rules"],
        )

    def test_commands_require_maps_to_request_host_fragments(self) -> None:
        payload = {
            "commands": {
                "allow": ["git status"],
                "deny": ["git reset --hard"],
                "require": ["python cli.py test run --scope integration"],
            },
        }

        rendered = render_platform_payload(payload, include_conditional=False)
        host_rules = rendered["policy"]
        codex_request = (
            "prefix_rule("
            'pattern=["python", "cli.py", "test", "run", "--scope", "integration"], '
            'decision="prompt")'
        )

        self.assertIn(
            codex_request,
            host_rules["codex"]["rules"],
        )
        self.assertIn(
            "Shell(python cli.py test run --scope integration)",
            host_rules["cursor"]["deny"],
        )
        self.assertIn(
            "Bash(python cli.py test run --scope integration)",
            host_rules["claude"]["ask"],
        )
        self.assertIn(
            "python cli.py test run --scope integration",
            host_rules["droid"]["commandRequestlist"],
        )
        self.assertNotIn(
            "python cli.py test run --scope integration",
            host_rules["droid"]["commandDenylist"],
        )

    def test_require_action_evaluates_to_request_in_evaluate_policy(self) -> None:
        payload = {
            "policy": {
                "commands": {
                    "allow": [],
                    "deny": [],
                    "require": ["policy_merge"],
                },
            },
        }
        decision, _, rule = evaluate_policy(payload, "policy_merge")

        self.assertEqual(decision, "request")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.action, "request")

    def test_wrapper_payload_uses_raw_prefix_pattern_for_prefix_matcher(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "prefix-prefix-check",
                        "action": "allow",
                        "match": {"prefix": "git checkout"},
                        "conditions": {
                            "all": [{"name": "git_is_worktree", "required": True}],
                        },
                    },
                ],
            },
        }

        rendered = render_platform_payload(payload, include_conditional=True)
        host_policy = rendered["policy"]
        wrapper_rule = rendered["wrapper_rules"][0]

        self.assertIn("Shell(git checkout *)", host_policy["cursor"]["allow"])
        self.assertEqual(wrapper_rule["normalized_pattern"], "git checkout")
        self.assertEqual(wrapper_rule["shell_entry"], "Shell(git checkout *)")

    def test_evaluate_policy_prefers_deny_over_allow_from_command_rules(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "allow-only-on-condition",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {
                            "any": [{"name": "git_clean_worktree", "required": False}],
                        },
                    },
                    {
                        "id": "deny-command",
                        "action": "deny",
                        "match": "git status",
                    },
                ],
            },
        }

        with patch.dict(
            "policy_lib.CONDITION_EVALUATORS",
            {
                "git_clean_worktree": lambda _cwd: (
                    False,
                    "git_clean_worktree",
                ),
            },
            clear=False,
        ):
            decision, _, rule = evaluate_policy(payload, "git status")

        self.assertEqual(decision, "deny")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_id, "deny-command")

    def test_recursive_condition_set_collects_nested_required_conditions(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "nested-condition-rule",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {
                            "all": [
                                {
                                    "mode": "any",
                                    "conditions": [
                                        {"name": "git_is_worktree"},
                                        {
                                            "name": "git_clean_worktree",
                                            "required": False,
                                        },
                                    ],
                                },
                                {"name": "git_synced_to_upstream"},
                            ],
                        },
                    },
                ],
            },
        }
        rendered = render_platform_payload(payload, include_conditional=True)
        self.assertEqual(
            rendered["wrapper_condition_set"],
            ["git_is_worktree", "git_synced_to_upstream"],
        )

    def test_recursive_wrapper_payload_exports_nested_conditions(self) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "nested-condition-rule",
                        "action": "allow",
                        "match": "git status",
                        "conditions": {
                            "all": [
                                {
                                    "all": [
                                        "git_is_worktree",
                                        {"name": "git_clean_worktree"},
                                    ],
                                },
                                {
                                    "mode": "any",
                                    "conditions": [
                                        {
                                            "name": "git_synced_to_upstream",
                                            "required": False,
                                        },
                                    ],
                                },
                            ],
                        },
                    },
                ],
            },
        }
        rendered = render_platform_payload(payload, include_conditional=True)
        wrapper_rule = rendered["wrapper_rules"][0]
        self.assertEqual(
            wrapper_rule["conditions"],
            {
                "mode": "all",
                "conditions": [
                    {
                        "mode": "all",
                        "conditions": [
                            "git_is_worktree",
                            {"name": "git_clean_worktree", "required": True},
                        ],
                    },
                    {
                        "mode": "any",
                        "conditions": [
                            {"name": "git_synced_to_upstream", "required": False},
                        ],
                    },
                ],
            },
        )

    def test_rendered_wrapper_payload_conditional_split_counts(self) -> None:
        payload = {
            "policy": {
                "commands": {"allow": [], "deny": [], "require": []},
                "command_rules": [
                    {
                        "id": "wrapper-cond-rule",
                        "action": "allow",
                        "match": {"prefix": "git checkout"},
                        "conditions": {
                            "all": [{"name": "git_is_worktree", "required": True}],
                        },
                    },
                    {
                        "id": "wrapper-uncond-rule",
                        "action": "deny",
                        "match": "git reset --hard",
                    },
                ],
            },
        }

        rendered_conditional_only = render_platform_payload(
            payload, include_conditional=False,
        )
        self.assertEqual(rendered_conditional_only["conditional_count"], 1)
        self.assertEqual(rendered_conditional_only["unconditional_count"], 1)
        self.assertEqual(len(rendered_conditional_only["wrapper_rules"]), 1)
        self.assertEqual(len(rendered_conditional_only["conditional_rules"]), 1)
        self.assertEqual(
            rendered_conditional_only["wrapper_rules"][0]["id"],
            "wrapper-cond-rule",
        )

        rendered_with_conditional = render_platform_payload(
            payload, include_conditional=True,
        )
        self.assertEqual(rendered_with_conditional["conditional_count"], 1)
        self.assertEqual(rendered_with_conditional["unconditional_count"], 1)
        self.assertEqual(len(rendered_with_conditional["wrapper_rules"]), 2)
        self.assertEqual(
            rendered_with_conditional["policy"]["policy_wrapper"][
                "required_conditions"
            ],
            ["git_is_worktree"],
        )

        wrapper_rules = rendered_with_conditional["policy"]["policy_wrapper"][
            "commands"
        ]
        self.assertEqual(wrapper_rules[0]["id"], "wrapper-cond-rule")
        self.assertEqual(
            wrapper_rules[0]["conditions"],
            {
                "mode": "all",
                "conditions": [{"name": "git_is_worktree", "required": True}],
            },
        )


class TestResolveCLI(TestCase):
    @staticmethod
    def _write_policy_file(path: Path, scope: str, policy: dict[str, Any]) -> None:
        payload = {
            "policy_version": "v1",
            "scope": scope,
            "commands": {"allow": [], "deny": [], "require": []},
        }
        payload.update(policy)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _normalize_path(value: str | Path) -> str:
        return os.path.realpath(os.fspath(value))

    def test_host_out_dir_requires_emit_host_rules(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            repo_root = Path(repo_root)
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "resolve.py"),
                    "--root",
                    str(repo_root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--host-out-dir",
                    str(repo_root / "host-out"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "--host-out-dir requires --emit-host-rules",
                result.stderr + result.stdout,
            )

    def test_include_conditional_host_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            repo_root = Path(repo_root)
            config_root = repo_root / "policy-contract" / "policy-config"
            self._write_policy_file(
                config_root / "system.yaml",
                "system",
                {"command_rules": []},
            )
            self._write_policy_file(
                config_root / "user.yaml",
                "user",
                {"command_rules": []},
            )
            self._write_policy_file(
                config_root / "repo.yaml",
                "repo",
                {"command_rules": []},
            )
            self._write_policy_file(
                config_root / "harness" / "unit.yaml",
                "harness",
                {
                    "command_rules": [
                        {
                            "id": "harness-conditional-checkout",
                            "action": "allow",
                            "match": {"prefix": "git checkout"},
                            "conditions": {"all": ["git_is_worktree"]},
                        },
                    ],
                },
            )
            self._write_policy_file(
                config_root / "task-domain" / "unit.yaml",
                "task_domain",
                {"command_rules": []},
            )

            host_out_dir = repo_root / "host-artifacts"
            resolved_out = repo_root / "resolved-policy.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "resolve.py"),
                    "--root",
                    str(repo_root),
                    "--harness",
                    "unit",
                    "--task-domain",
                    "unit",
                    "--emit",
                    str(resolved_out),
                    "--emit-host-rules",
                    "--include-conditional",
                    "--host-out-dir",
                    str(host_out_dir),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            output = json.loads(result.stdout)
            self.assertEqual(output["include_conditional"], True)
            self.assertEqual(
                self._normalize_path(output["host_artifacts_written_to"]),
                self._normalize_path(host_out_dir),
            )
            self.assertEqual(
                self._normalize_path(output["policy_wrapper_bundle"]),
                self._normalize_path(host_out_dir / "policy-wrapper-rules.json"),
            )
            self.assertEqual(output["wrapper_rule_count"], len(output["wrapper_rules"]))
            self.assertGreaterEqual(output["wrapper_rule_count"], 1)

            bundle_path = Path(output["policy_wrapper_bundle"])
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertGreater(len(bundle.get("commands", [])), 0)
            self.assertEqual(
                len(bundle.get("commands", [])), output["wrapper_rule_count"],
            )
            self.assertTrue(resolved_out.exists())

            manifest = json.loads(
                (host_out_dir / "policy-wrapper-dispatch.manifest.json").read_text(
                    encoding="utf-8",
                ),
            )
            self.assertEqual(
                self._normalize_path(manifest["bundle_path"]),
                self._normalize_path(bundle_path),
            )
            self.assertEqual(
                manifest["wrapper_rule_count"], output["wrapper_rule_count"],
            )
            self.assertEqual(manifest["fallback_missing_policy"], "allow")
            self.assertEqual(manifest["fallback_malformed_bundle"], "allow")
            self.assertEqual(manifest["fallback_condition_eval_error"], "request")
            dispatch_command = manifest["dispatch_command"]
            self.assertEqual(
                dispatch_command[0],
                str(
                    Path(__file__).resolve().parent.parent
                    / "wrappers"
                    / "policy-wrapper-dispatch.sh",
                ),
            )

            missing_idx = dispatch_command.index("--missing-policy-default")
            malformed_idx = dispatch_command.index("--malformed-bundle-default")
            condition_eval_idx = dispatch_command.index(
                "--condition-eval-error-default",
            )
            self.assertEqual(dispatch_command[missing_idx + 1], "allow")
            self.assertEqual(dispatch_command[malformed_idx + 1], "allow")
            self.assertEqual(dispatch_command[condition_eval_idx + 1], "request")

            for artifact in (
                "codex.rules",
                "cursor.cli-config.json",
                "claude.settings.json",
                "factory-droid.settings.json",
                "policy-wrapper-rules.json",
                "policy-wrapper-dispatch.manifest.json",
            ):
                self.assertTrue((host_out_dir / artifact).exists(), artifact)

    def test_include_conditional_host_artifacts_validate_without_wrapper_rule_count(
        self,
    ) -> None:
        payload = {
            "policy": {
                "command_rules": [
                    {
                        "id": "conditional-host-artifact-regression",
                        "action": "allow",
                        "match": {"prefix": "git checkout"},
                        "conditions": {"all": ["git_is_worktree"]},
                    },
                ],
            },
        }
        rendered = render_platform_payload(payload, include_conditional=True)
        rendered.pop("wrapper_rule_count", None)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            write_host_artifacts(rendered, out_dir)
            _validate_host_artifacts(out_dir, rendered)


class TestPolicyContractSchemaGovernance(TestCase):
    @staticmethod
    def _schema_path() -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "agent-scope"
            / "policy_contract.schema.json"
        )

    @staticmethod
    def _fixtures_dir() -> Path:
        return Path(__file__).resolve().parent / "fixtures" / "policy_contract"

    def _load_schema(self) -> dict[str, Any]:
        return json.loads(self._schema_path().read_text(encoding="utf-8"))

    def _schema_has_path(self, schema: dict[str, Any], dotted_path: str) -> bool:
        node: dict[str, Any] = schema
        for part in dotted_path.split("."):
            properties = node.get("properties", {})
            if part not in properties:
                return False
            child = properties[part]
            if not isinstance(child, dict):
                return False
            node = child
        return True

    def test_merge_strategy_paths_exist_in_contract_schema(self) -> None:
        schema = self._load_schema()
        for key in MERGE_STRATEGY:
            self.assertTrue(
                self._schema_has_path(schema, key),
                f"MERGE_STRATEGY path missing in schema: {key}",
            )

    def test_contract_schema_valid_invalid_fixture_set(self) -> None:
        if _validate_schema is None:
            self.skipTest("jsonschema not installed")
        schema = self._load_schema()
        fixtures = self._fixtures_dir()

        valid_paths = [
            fixtures / "valid_minimal.json",
            fixtures / "valid_commands.json",
        ]
        invalid_paths = [
            fixtures / "invalid_missing_scope.json",
            fixtures / "invalid_bad_action.json",
        ]

        for path in valid_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            _validate_schema(payload, schema)

        for path in invalid_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            with self.assertRaises(Exception):
                _validate_schema(payload, schema)


if __name__ == "__main__":
    main()


class TestResolveCLIRegressions(TestCase):
    @staticmethod
    def _normalize_path(value: str | Path) -> str:
        return os.path.realpath(os.fspath(value))

    def _write_policy(
        self, path: Path, scope: str, *, policy_version: str = "v1",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "policy_version": policy_version,
            "scope": scope,
            "commands": {"allow": ["git status"]},
        }
        with path.open("w", encoding="utf-8") as fp:
            yaml.safe_dump(payload, fp, sort_keys=False)

    def _run_resolve(
        self,
        root: Path,
        *,
        emit: Path | None = None,
        json_mode: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "resolve.py"),
            "--root",
            str(root),
            "--harness",
            "codex",
            "--task-domain",
            "repair",
        ]
        if emit is not None:
            cmd.extend(["--emit", str(emit)])
        if json_mode:
            cmd.append("--json")
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_ResolveCLI_repo_root_policy_config_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"
            self._write_policy(config_root / "system.yaml", "system")
            self._write_policy(config_root / "user.yaml", "user")
            self._write_policy(config_root / "repo.yaml", "repo")
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(
                config_root / "task-domain" / "repair.yaml", "task_domain",
            )

            out_path = root / "resolved.json"
            result = self._run_resolve(root, emit=out_path)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            scopes = [
                [scope_name, self._normalize_path(scope_path)]
                for scope_name, scope_path in payload["scopes"]
            ]
            self.assertIn(
                ["repo", self._normalize_path(config_root / "repo.yaml")],
                scopes,
            )
            self.assertIn(
                [
                    "harness",
                    self._normalize_path(config_root / "harness" / "codex.yaml"),
                ],
                scopes,
            )
            self.assertIn(
                [
                    "task_domain",
                    self._normalize_path(config_root / "task-domain" / "repair.yaml"),
                ],
                scopes,
            )

    def test_missing_required_scope_file_returns_missing_exit_code_and_error_text(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"
            self._write_policy(config_root / "system.yaml", "system")
            self._write_policy(config_root / "user.yaml", "user")
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(
                config_root / "task-domain" / "repair.yaml", "task_domain",
            )
            # Intentionally omit repo.yaml.

            result = self._run_resolve(root)

            self.assertEqual(result.returncode, EXIT_CODE_MISSING)
            error_text = f"{result.stdout}\n{result.stderr}"
            self.assertIn("missing required policy file", error_text)
            self.assertIn("scope 'repo'", error_text)
            self.assertIn(str(config_root / "repo.yaml"), error_text)

    def test_policy_version_must_be_v1(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"
            self._write_policy(config_root / "system.yaml", "system")
            self._write_policy(config_root / "user.yaml", "user")
            self._write_policy(config_root / "repo.yaml", "repo")
            self._write_policy(
                config_root / "harness" / "codex.yaml",
                "harness",
                policy_version="v2",
            )
            self._write_policy(
                config_root / "task-domain" / "repair.yaml", "task_domain",
            )

            result = self._run_resolve(root)

            self.assertEqual(result.returncode, EXIT_CODE_INVALID)
            error_text = f"{result.stdout}\n{result.stderr}"
            self.assertIn("policy_version must be 'v1'", error_text)

    def test_policy_version_error_json_payload_has_invalid_code_and_message(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"
            self._write_policy(config_root / "system.yaml", "system")
            self._write_policy(config_root / "user.yaml", "user")
            self._write_policy(config_root / "repo.yaml", "repo")
            self._write_policy(
                config_root / "harness" / "codex.yaml",
                "harness",
                policy_version="v2",
            )
            self._write_policy(
                config_root / "task-domain" / "repair.yaml", "task_domain",
            )

            result = self._run_resolve(root, json_mode=True)

            self.assertEqual(result.returncode, EXIT_CODE_INVALID)
            self.assertEqual(result.stderr.strip(), "")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["code"], "invalid")
            self.assertIn("policy_version must be 'v1'", payload["message"])
            self.assertNotIn("details", payload)

    def test_missing_layout_returns_missing_exit_code_and_explicit_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = self._run_resolve(root)

            self.assertEqual(result.returncode, EXIT_CODE_MISSING)
            error_text = f"{result.stdout}\n{result.stderr}"
            self.assertIn("no supported config root layout exists", error_text)
            self.assertIn(str(root / "policy-config"), error_text)
            self.assertIn(str(root / "policy-contract" / "policy-config"), error_text)

    def test_emit_path_is_stable_for_json_success_with_emit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "policy-config"
            self._write_policy(config_root / "system.yaml", "system")
            self._write_policy(config_root / "user.yaml", "user")
            self._write_policy(config_root / "repo.yaml", "repo")
            self._write_policy(config_root / "harness" / "codex.yaml", "harness")
            self._write_policy(
                config_root / "task-domain" / "repair.yaml", "task_domain",
            )

            emit_path = root / "resolved.json"
            result = self._run_resolve(root, emit=emit_path, json_mode=True)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["code"], "ok")
            self.assertEqual(
                payload["details"]["emit_path"], self._normalize_path(emit_path),
            )
            self.assertEqual(
                payload["details"]["scopes_ordering_assertion_path"],
                "result.policy.scopes",
            )
