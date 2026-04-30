# Session Overview

## Goal

Add the sladge badge to PolicyStack while preserving unrelated local changes in
the canonical checkout.

## Outcome

- Added the `AI Slop Inside` badge to `README.md`.
- Used isolated worktree `PolicyStack-wtrees/sladge-badge` because canonical
  `PolicyStack` already had unrelated `CLAUDE.md`, `PRD.md`, and test coverage
  matrix changes.
- Kept the change docs-only.

## Success Criteria

- README includes the sladge badge.
- Session docs explain the isolated-worktree decision.
- The worktree is clean after commit.
