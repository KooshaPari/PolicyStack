# Implementation Strategy

## Approach

Add one Sladge badge under the README heading and keep all policy engine files untouched.

## Boundary Decisions

- Do not modify canonical `PolicyStack`.
- Do not reuse the behind `PolicyStack-wtrees/sladge-current` worktree because it has unrelated local changes.
- Do not repair unrelated validation cache or toolchain issues in this badge-only lane.
