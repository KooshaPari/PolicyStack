# Implementation Strategy

## Approach

Keep the badge change small and docs-only:

- README receives the sladge badge under the title.
- Session docs capture why the isolated worktree was required.
- No policy-contract code, generated snapshots, or validation logic changes.

## Rationale

PolicyStack already had unrelated local work. A separate worktree allows the
sladge WBS item to be prepared and committed without disturbing that state.
