# Specifications

## Acceptance Criteria

- Root README links to `https://sladge.net`.
- Badge image source is `https://sladge.net/badge.svg`.
- Older dirty/behind worktrees are not modified.
- projects-landing records this current-head proof.

## Assumptions, Risks, Uncertainties

- Assumption: This is a documentation governance refresh and does not require policy engine code changes.
- Risk: The documented `uv run --with ...` validation path may still hit sandbox cache permission limits.
- Mitigation: Run direct validator form and record exact blockers.
