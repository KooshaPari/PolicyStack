# Testing Strategy

## Commands

```bash
git diff --check
rg -n "sladge|AI Slop" README.md docs/sessions/20260507-policystack-sladge-refresh
python scripts/validate_policy_contract.py --root .
```

## Results

- `git diff --check`: passed.
- Badge presence search: passed.
- `python scripts/validate_policy_contract.py --root .`: passed with `checked=10 missing=0 invalid=0`.
