# PolicyStack - tier-0 justfile
# Native task runner. Stack-aware: primary language is python (uv), with rust and node toolchains
# called out explicitly. Recipes: build, test, lint, fmt, audit, deny, grade, ci.

set shell := ["bash", "-uc"]
set dotenv-load

# Default recipe: print help
default: help

# List recipes
help:
    @just --list

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
build:
    @echo "[build] python compileall"
    mkdir -p .pytest_cache/task-tmp
    TMPDIR="$PWD/.pytest_cache/task-tmp" PYTHONPYCACHEPREFIX="$PWD/.pytest_cache/task-tmp/pycache" \
      uv run --no-project python -m compileall -q cli policy_lib.py resolve.py scripts policy-config policies 2>/dev/null || true
    @echo "[build] rust wrapper check"
    cd wrappers/rust && cargo check --locked --offline 2>/dev/null || cargo check --locked

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
test:
    @echo "[test] pytest"
    mkdir -p .pytest_cache/task-tmp
    TMPDIR="$PWD/.pytest_cache/task-tmp" PYTHONPYCACHEPREFIX="$PWD/.pytest_cache/task-tmp/pycache" \
      PYTHONPATH="$PWD:$PWD/cli/src" \
      uv run --no-project --with pytest --with pytest-asyncio --with pyyaml --with jsonschema \
        pytest tests/ -q --tb=short

# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------
lint:
    @echo "[lint] ruff (syntax + import checks)"
    uv run --no-project --with ruff ruff check --select E9,F --exclude scripts .
    @echo "[lint] governance validator"
    python validate_governance.py

# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------
fmt:
    @echo "[fmt] ruff format"
    uv run --no-project --with ruff ruff format .
    @echo "[fmt] ruff lint autofix"
    uv run --no-project --with ruff ruff check --fix --exclude scripts .

# ---------------------------------------------------------------------------
# Audit (dependencies + secrets + governance)
# ---------------------------------------------------------------------------
audit:
    @echo "[audit] python dependency scan (pip-audit)"
    uv run --no-project --with pip-audit pip-audit -r <(uv pip freeze 2>/dev/null || true) || true
    @echo "[audit] gitleaks secrets scan (if installed)"
    command -v gitleaks >/dev/null && gitleaks detect --no-banner --redact || echo "gitleaks not installed, skipping"
    @echo "[audit] governance validator"
    python validate_governance.py

# ---------------------------------------------------------------------------
# Deny (cargo-deny for the rust wrapper)
# ---------------------------------------------------------------------------
deny:
    @echo "[deny] cargo-deny (rust wrapper)"
    cd wrappers/rust && cargo deny check

# ---------------------------------------------------------------------------
# Grade (full project grading)
# ---------------------------------------------------------------------------
grade:
    @echo "[grade] running grade.sh"
    ./grade.sh

# ---------------------------------------------------------------------------
# CI (mirror of .github/workflows/ci.yml)
# ---------------------------------------------------------------------------
ci: lint test
    @echo "[ci] rust wrapper check"
    cd wrappers/rust && cargo check --locked
    @echo "[ci] governance validate"
    python validate_governance.py
    @echo "[ci] all gates green"
