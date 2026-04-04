from __future__ import annotations

import unittest

from support import REPO_ROOT

from policy_federation.runtime_context import infer_repo_name_from_cwd


class RuntimeContextTest(unittest.TestCase):
    def test_infer_repo_name_from_worktree_cwd(self) -> None:
        self.assertTrue(REPO_ROOT.exists())
        self.assertEqual(
            infer_repo_name_from_cwd(
                "/Users/kooshapari/CodeProjects/Phenotype/repos/trace-wtrees/cli-stubs"
            ),
            "trace",
        )

    def test_infer_repo_name_from_nested_worktrees_layout(self) -> None:
        self.assertEqual(
            infer_repo_name_from_cwd(
                "/Users/kooshapari/CodeProjects/Phenotype/repos/worktrees/heliosApp/claude-md-standardize"
            ),
            "heliosApp",
        )

    def test_infer_repo_name_falls_back_to_leaf_name(self) -> None:
        self.assertEqual(infer_repo_name_from_cwd("/tmp/custom-repo"), "custom-repo")


if __name__ == "__main__":
    unittest.main()
