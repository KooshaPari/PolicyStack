"""Pytest configuration for PolicyStack tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Mock wrapper libraries and their submodules to unblock import errors
# Only mock wrappers that don't exist as real modules
_EXTERNAL_WRAPPERS = ["codex", "cursor", "droid"]
for wrapper in _EXTERNAL_WRAPPERS:
    mod = ModuleType(wrapper)
    mod.wrapper = MagicMock()
    sys.modules[wrapper] = mod
    sys.modules[f"{wrapper}.wrapper"] = mod.wrapper
# Note: opencode, kilo, forgecode are real modules in wrappers/ directory
# and should not be mocked globally


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "benchmark: mark test as performance benchmark")
    config.addinivalue_line("markers", "slow: mark test as slow")
    config.addinivalue_line("markers", "integration: mark test as integration test")


@pytest.fixture
def temp_repo():
    """Create a temporary repository directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        # Create basic structure
        (repo_root / ".phenotype").mkdir(exist_ok=True)
        (repo_root / ".worktrees" / "feature-branch").mkdir(parents=True, exist_ok=True)
        yield repo_root


@pytest.fixture
def mock_cache(tmp_path):
    """Provide a mock cache database path."""
    from unittest.mock import patch

    cache_db = tmp_path / "test_cache.db"
    with patch("policy_federation.delegate._get_cache_db", return_value=cache_db):
        yield cache_db


@pytest.fixture
def sample_commands():
    """Return sample commands for testing."""
    return {
        "tier_1": ["git status", "git log", "ls -la", "cat file.txt", "pwd"],
        "tier_2": ["git add -A", "git commit -m 'test'", "mkdir -p test"],
        "tier_3": ["git push", "cargo build", "cargo test"],
        "tier_4": ["rm -rf /", "sudo ls", "chmod 777 /etc"],
    }


@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables before each test."""
    import os

    # Save original values
    original_env = {}
    env_vars = [
        "POLICY_MODE",
        "POLICY_ASK_MODE",
        "POLICY_DELEGATE_HARNESS",
        "POLICY_REVIEW_BIN",
        "POLICY_AUDIT_LOG_PATH",
        "FORGECODE_API_KEY",
    ]

    for var in env_vars:
        original_env[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]

    yield

    # Restore original values
    for var, value in original_env.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]
