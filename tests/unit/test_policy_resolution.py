from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from support import REPO_ROOT

from policy_federation.resolver import _append_unique_items, _merge_maps, resolve
from policy_federation.validate import validate_policy_file


class PolicyResolutionTest(unittest.TestCase):
    def test_policy_file_with_authorization_block_validates(self) -> None:
        doc = validate_policy_file(REPO_ROOT / "policies" / "user" / "org-default.yaml")
        self.assertIn("authorization", doc["policy"])

    def test_extends_contributes_shared_devops_rules(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        rule_ids = {rule["id"] for rule in resolved["policy"]["authorization"]["rules"]}
        self.assertIn("devops-ask-networked-installs", rule_ids)
        self.assertIn("devops-ask-network-egress", rule_ids)

    def test_append_unique_items_replaces_by_id(self) -> None:
        merged = _append_unique_items(
            [
                {"id": "a", "action": "allow"},
                {"id": "b", "action": "deny"},
                {"id": "a", "action": "deny"},
                {"id": "c", "action": "ask"},
            ]
        )
        self.assertEqual(
            merged,
            [
                {"id": "a", "action": "deny"},
                {"id": "b", "action": "deny"},
                {"id": "c", "action": "ask"},
            ],
        )

    def test_merge_maps_append_unique_replaces_matching_id_items(self) -> None:
        base = {
            "authorization": {
                "rules": [
                    {"id": "r1", "action": "allow"},
                    {"id": "r2", "action": "deny"},
                ]
            }
        }
        overrides = {
            "authorization": {
                "rules": [
                    {"id": "r1", "action": "ask"},
                    {"id": "r3", "action": "allow"},
                ]
            }
        }

        conflicts: list[dict] = []
        merged = _merge_maps(base, overrides, "append_unique", conflicts)
        self.assertEqual(
            merged["authorization"]["rules"],
            [
                {"id": "r1", "action": "ask"},
                {"id": "r2", "action": "deny"},
                {"id": "r3", "action": "allow"},
            ],
        )
        self.assertEqual(conflicts, [])

    def test_resolve_extends_overrides_authorization_rules_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "policies" / "task-domain").mkdir(parents=True)

            shared_policy = (
                """
                version: "1.0"
                id: "shared-policy"
                scope: task_domain
                merge:
                  strategy: append_unique
                policy:
                  authorization:
                    rules:
                      - id: "shared"
                        description: "parent"
                        effect: deny
                        priority: 10
                        actions: ["exec"]
                        match:
                          command_patterns:
                            - "npm *"
                """
            )
            (repo_root / "policies" / "task-domain" / "shared.yaml").write_text(
                shared_policy, encoding="utf-8"
            )

            child_policy = (
                """
                version: "1.0"
                id: "child-policy"
                scope: task_domain
                extends:
                  - "task_domain/shared"
                merge:
                  strategy: append_unique
                policy:
                  authorization:
                    rules:
                      - id: "shared"
                        description: "child override"
                        effect: allow
                        priority: 20
                        actions: ["exec"]
                        match:
                          command_patterns:
                            - "npm *"
                      - id: "child"
                        description: "child new"
                        effect: allow
                        priority: 5
                        actions: ["exec"]
                        match:
                          command_patterns:
                            - "yarn *"
                """
            )
            (repo_root / "policies" / "task-domain" / "task-domain.yaml").write_text(
                child_policy, encoding="utf-8"
            )

            resolved = resolve(
                repo_root=repo_root,
                harness="cursor-agent",
                repo="test-repo",
                task_domain="task-domain",
            )
            rules = {rule["id"]: rule for rule in resolved["policy"]["authorization"]["rules"]}

            self.assertEqual(rules["shared"]["effect"], "allow")
            self.assertEqual(rules["shared"]["description"], "child override")
            self.assertIn("child", rules)
            self.assertEqual(len(rules), 2)


if __name__ == "__main__":
    unittest.main()
