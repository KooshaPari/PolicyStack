from __future__ import annotations

import unittest

from support import REPO_ROOT

from policy_federation.authorization import evaluate_authorization
from policy_federation.resolver import resolve


class AuthorizationDecisionTest(unittest.TestCase):
    def test_process_inspection_is_allowed_anywhere(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="ps aux | grep -i claude | grep -v grep | head -20",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/trace",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_repo_scaffolding_mkdir_is_allowed_in_phenotype_repos(self) -> None:
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
                "mkdir -p "
                "/Users/kooshapari/CodeProjects/Phenotype/repos/trace/"
                "src/tracertm/cli/commands/test"
            ),
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_repo_coordination_loop_is_allowed(self) -> None:
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
                "for repo in trace cliproxyapi++ heliosCLI agentapi-plusplus thegent; do "
                "echo \"=== $repo ===\" && "
                "[ -d \"$repo/.github/workflows\" ] && ls \"$repo/.github/workflows/\""
            ),
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_go_cache_cleanup_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="go clean -cache",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/trace",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_homebrew_cache_cleanup_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="rm -rf ~/Library/Caches/Homebrew/downloads/*",
            cwd="/Users/kooshapari",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_git_symbolic_ref_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="git symbolic-ref refs/remotes/origin/HEAD",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/trace",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_git_worktree_list_is_allowed(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="git worktree list",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_pwd_is_allowed(self) -> None:
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
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_readlink_realpath_probe_is_allowed(self) -> None:
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
                "readlink -f "
                "/Users/kooshapari/CodeProjects/Phenotype/repos/worktrees/heliosApp/"
                "claude-md-standardize 2>/dev/null || realpath "
                "/Users/kooshapari/CodeProjects/Phenotype/repos/worktrees/heliosApp/"
                "claude-md-standardize"
            ),
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_diff_probe_is_allowed(self) -> None:
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
                "diff /Users/kooshapari/CodeProjects/Phenotype/repos/worktrees/heliosApp/"
                "claude-md-standardize/biome.json "
                "/Users/kooshapari/CodeProjects/Phenotype/repos/heliosApp-wtrees/"
                "claude-md-standardize/biome.json 2>/dev/null || echo \"DIFFERENT or one missing\""
            ),
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_repo_inventory_prefix_is_allowed(self) -> None:
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
                "for repo in agentapi-plusplus-composite-actions "
                "bifrost-extensions-composite-actions cliproxyapi++-composite-actions "
                "agentapi-plusplus-governance bifrost-extensions-governance; do "
                "echo \"=== $repo ===\"; if [ -d \"$repo\" ]; then [ -d \"$repo/.github\" ] && "
                "echo \"Has .github:\" && ls \"$repo/.github/\""
            ),
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_repo_metadata_inventory_is_allowed(self) -> None:
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
                "for repo in phenotype-go-kit phenotype-shared template-commons thegent; do "
                "echo \"=== $repo ===\"; [ -f \"$repo/go.mod\" ] && echo \"go.mod: YES\" || "
                "echo \"go.mod: NO\"; [ -f \"$repo/CLAUDE.md\" ] && echo \"CLAUDE.md: YES\" || "
                "echo \"CLAUDE.md: NO\"; [ -d \"$repo/.github/workflows\" ] && "
                "echo \"Workflows: $(ls $repo/.github/workflows 2>/dev/null | wc -l)\" || "
                "echo \"Workflows: 0\"; [ -f \"$repo/.pre-commit-config.yaml\" ] && "
                "echo \"Pre-commit: YES\" || echo \"Pre-commit: NO\"; echo \"\"; done"
            ),
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["winning_rule"]["effect"], "allow")

    def test_git_commit_is_allowed_from_thegent_worktree(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="git commit -m test",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
        )
        self.assertEqual(result["decision"], "allow")
        self.assertIn(result["winning_rule"]["id"], {"thegent-allow-git-write-in-worktrees", "phenotype-allow-worktree-git-ops"})

    def test_git_commit_is_denied_outside_thegent_worktree(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="git commit -m test",
            cwd="/tmp",
        )
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["winning_rule"]["id"], "thegent-deny-git-write-outside-worktrees")

    def test_no_verify_bypass_is_denied_even_inside_worktree(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="git commit --no-verify -m test",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/thegent-wtrees/demo",
        )
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["winning_rule"]["id"], "user-deny-no-verify-bypass")

    def test_network_request_is_asked(self) -> None:
        resolved = resolve(
            repo_root=REPO_ROOT,
            harness="codex",
            repo="thegent",
            task_domain="devops",
        )
        result = evaluate_authorization(
            resolved["policy"],
            action="exec",
            command="curl https://example.com",
            cwd="/Users/kooshapari/CodeProjects/Phenotype/repos/trace",
        )
        self.assertEqual(result["decision"], "ask")
        self.assertIsNone(result["winning_rule"])


if __name__ == "__main__":
    unittest.main()
