# PolicyStack tests

Run the full suite from the repo root:

```bash
python -m pytest tests/ -q
```

## Windows / shell integration tests

Some tests execute bash shell scripts (for example `test_policy_contract.py::TestWrapperConditionSemanticsParity` and `test_smoke_dispatch_host_hook.py`). On Windows these are skipped automatically because they require `/bin/bash` and Unix-style script execution.

To run the full suite including shell integration tests, use WSL or another Linux environment with bash available.
