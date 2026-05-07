# DAG WBS

## Work Breakdown

1. Confirm canonical branch and stale prepared branch state.
2. Create fresh isolated worktree from current `ci/add-mypy`.
3. Add root README Sladge badge.
4. Record session evidence.
5. Run validation.
6. Commit downstream change with required trailer.
7. Update projects-landing governance and task ledgers.

## Dependency Notes

- Step 3 depends on the isolated current-head worktree from step 2.
- Step 7 depends on downstream commit hash from step 6.
