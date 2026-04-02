# Contributing to PolicyStack

Thank you for your interest in contributing to PolicyStack.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Phenotype-Enterprise/PolicyStack
cd PolicyStack

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run governance tests
uv run --with pytest --with pyyaml --with jsonschema pytest tests/ -q

# Validate policy contract
uv run --with pyyaml --with jsonschema python scripts/validate_policy_contract.py --root .
```

## Policy Scope Model

PolicyStack implements a hierarchical policy scope model:

- `system` → global hard constraints
- `user` → operator-level constraints
- `repo` → repository contract baseline
- `harness` → Codex/Cursor-agent/Claude/Factory-Droid
- `task_domain` → domain-specific safety/runtime checks
- `task_instance` → one-off request override

## Making Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes
4. Add tests
5. Run governance tests
6. Validate policy contracts
7. Commit using conventional commits
8. Push and create PR

## Testing

Run the governance test matrix:

```bash
uv run --with pytest --with pyyaml pytest tests/test_resolve_cli_governance.py -q
uv run --with pytest --with pyyaml pytest tests/test_policy_common.py -q
uv run --with pytest --with pyyaml pytest tests/test_smoke_dispatch_host_hook.py -q
```

## Code Style

- Python code follows PEP 8
- YAML files use consistent indentation
- Policy files must validate against schema
