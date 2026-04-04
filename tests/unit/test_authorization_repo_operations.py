from __future__ import annotations

import unittest

from support import REPO_ROOT

from policy_federation.authorization import evaluate_authorization
from policy_federation.resolver import resolve


class AuthorizationRepoOperationsTest(unittest.TestCase):
    def test_timeout_wrapped_bun_test_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="timeout 30 bun test apps/desktop/tests/unit 2>&1 | tail -10",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/heliosApp-wtrees/tech-debt-wave",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["id"], "phenotype-allow-timeout-wrapped-tests")

    def test_timeout_wrapped_pytest_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="timeout 30 pytest --tb=short -q 2>&1 | tail -15",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/portage-composite-actions",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["id"], "phenotype-allow-timeout-wrapped-tests")

    def test_worktree_package_add_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="bun add -d happy-dom",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/heliosApp-wtrees/tech-debt-wave",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["id"], "phenotype-allow-worktree-package-adds")

    def test_trace_cli_stub_alias_write_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="write",
            command=(
                "printf '\"\"\"Command aliases for TraceRTM CLI.\"\"\"\\n"
                "from __future__ import annotations\\n\\nALIASES: dict[str, str] = {}\\n' "
                "| tee src/tracertm/cli/aliases.py"
            ),
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/trace-wtrees/cli-stubs",
            target_paths=[
                "/Users/kooshapari/CodeProjects/Phenotype/repos/trace-wtrees/cli-stubs/"
                "src/tracertm/cli/aliases.py"
            ],
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["id"], "phenotype-allow-worktree-writes")

    def test_trace_cli_stub_storage_write_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="write",
            command=(
                "printf '\"\"\"Storage helper utilities for TraceRTM CLI.\"\"\"\\n"
                "from __future__ import annotations\\n\\n' "
                "| tee src/tracertm/cli/storage_helper.py"
            ),
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/trace-wtrees/cli-stubs",
            target_paths=[
                "/Users/kooshapari/CodeProjects/Phenotype/repos/trace-wtrees/cli-stubs/"
                "src/tracertm/cli/storage_helper.py"
            ],
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["id"], "phenotype-allow-worktree-writes")

    def test_pwd_is_allowed_in_worktree(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="pwd",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/bifrost-extensions-wtrees/fix-build-blockers",
        )
        self.assertEqual(result["decision"], "allow")

    def test_web_search_is_allowed_for_docs_research(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="network",
            command="WebSearch Plane.so REST API endpoints issues cycles modules documentation",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["id"], "phenotype-allow-docs-web-search")

    def test_destructive_repo_removal_is_denied(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="rm -rf /Users/kooshapari/CodeProjects/Phenotype/repos/phenotype-go-kit",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["winning_rule"]["id"], "phenotype-deny-destructive-repo-removal")

    def test_archive_repo_move_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command=(
                "mv /Users/kooshapari/CodeProjects/Phenotype/repos/phenotype-go-kit "
                "/Users/kooshapari/CodeProjects/Phenotype/repos/.archive/phenotype-go-kit"
            ),
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["id"], "phenotype-allow-archive-repo-moves")


if __name__ == "__main__":
    unittest.main()
