"""Tests for configuration loader."""

from __future__ import annotations

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open

from policy_federation.config_loader import (
    PolicyConfig,
    load_config,
    get_active_harness,
    is_tier_enabled,
    get_cache_db_path,
    get_audit_log_path,
    _apply_env_overrides,
    _merge_dict_into_config,
)


class TestConfigDefaults:
    """Test default configuration values."""

    def test_default_config_values(self):
        """Default config should have sensible values."""
        config = PolicyConfig()

        assert config.mode == "enforce"
        assert config.ask_mode == "delegate"
        assert config.platform.auto_detect is True
        assert config.platform.preferred_harness == "opencode"
        assert config.risk_assessment.enabled is True
        assert config.cache.enabled is True
        assert config.delegation.enabled is True
        assert config.guardian.enabled is True
        assert config.audit.enabled is True

    def test_default_risk_tiers_enabled(self):
        """All risk tiers should be enabled by default."""
        config = PolicyConfig()

        assert config.risk_assessment.tier_1.enabled is True
        assert config.risk_assessment.tier_2.enabled is True
        assert config.risk_assessment.tier_3.enabled is True
        assert config.risk_assessment.tier_4.enabled is True


class TestConfigLoading:
    """Test configuration loading from files."""

    def test_load_config_creates_defaults(self):
        """load_config should return default config when no files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(repo_root=Path(tmpdir))
            assert config.mode == "enforce"
            assert config.ask_mode == "delegate"

    def test_repo_config_overrides_global(self):
        """Repo-specific config should override global config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create repo config
            phenotype_dir = repo_root / ".phenotype"
            phenotype_dir.mkdir()
            config_file = phenotype_dir / "policy.yaml"
            config_file.write_text("mode: audit\nask_mode: ask")

            config = load_config(repo_root=repo_root)
            assert config.mode == "audit"
            assert config.ask_mode == "ask"


class TestEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_policy_mode_override(self):
        """POLICY_MODE should override config file."""
        with patch.dict(os.environ, {"POLICY_MODE": "disabled"}):
            config = PolicyConfig()
            config = _apply_env_overrides(config)
            assert config.mode == "disabled"

    def test_policy_ask_mode_override(self):
        """POLICY_ASK_MODE should override config file."""
        with patch.dict(os.environ, {"POLICY_ASK_MODE": "allow"}):
            config = PolicyConfig()
            config = _apply_env_overrides(config)
            assert config.ask_mode == "allow"

    def test_policy_delegate_harness_override(self):
        """POLICY_DELEGATE_HARNESS should override config file."""
        with patch.dict(os.environ, {"POLICY_DELEGATE_HARNESS": "forge"}):
            config = PolicyConfig()
            config = _apply_env_overrides(config)
            assert config.delegation.primary == "forge"

    def test_multiple_env_overrides(self):
        """Multiple env vars should all be applied."""
        env_vars = {
            "POLICY_MODE": "audit",
            "POLICY_ASK_MODE": "review",
            "POLICY_DELEGATE_HARNESS": "cursor",
        }

        with patch.dict(os.environ, env_vars):
            config = PolicyConfig()
            config = _apply_env_overrides(config)
            assert config.mode == "audit"
            assert config.ask_mode == "review"
            assert config.delegation.primary == "cursor"


class TestConfigMerging:
    """Test configuration merging from dict."""

    def test_merge_simple_fields(self):
        """Simple fields should be merged."""
        config = PolicyConfig()
        data = {
            "mode": "audit",
            "ask_mode": "allow",
            "debug": True,
        }

        _merge_dict_into_config(config, data)

        assert config.mode == "audit"
        assert config.ask_mode == "allow"
        assert config.debug is True

    def test_merge_nested_platform(self):
        """Nested platform config should be merged."""
        config = PolicyConfig()
        data = {
            "platform": {
                "auto_detect": False,
                "preferred_harness": "cursor",
            }
        }

        _merge_dict_into_config(config, data)

        assert config.platform.auto_detect is False
        assert config.platform.preferred_harness == "cursor"

    def test_merge_risk_tiers(self):
        """Risk tier settings should be merged."""
        config = PolicyConfig()
        data = {
            "risk_assessment": {
                "enabled": False,
                "tier_1": {"enabled": False},
                "tier_4": {"enabled": True},
            }
        }

        _merge_dict_into_config(config, data)

        assert config.risk_assessment.enabled is False
        assert config.risk_assessment.tier_1.enabled is False
        # tier_4 should be enabled (explicitly set)
        assert config.risk_assessment.tier_4.enabled is True
        # tier_2 and tier_3 should remain at defaults
        assert config.risk_assessment.tier_2.enabled is True

    def test_merge_partial_nested(self):
        """Partial nested config should only update specified fields."""
        config = PolicyConfig()
        original_timeout = config.cache.ttl_seconds

        data = {
            "cache": {
                "enabled": False,
                # ttl_seconds not specified - should remain unchanged
            }
        }

        _merge_dict_into_config(config, data)

        assert config.cache.enabled is False
        assert config.cache.ttl_seconds == original_timeout


class TestHelperFunctions:
    """Test config helper functions."""

    def test_get_active_harness_auto_detect(self):
        """get_active_harness should auto-detect when enabled."""
        config = PolicyConfig()
        config.platform.auto_detect = True

        with patch(
            "policy_federation.config_loader._auto_detect_harness",
            return_value="opencode",
        ):
            harness = get_active_harness(config)
            assert harness == "opencode"

    def test_get_active_harness_preferred(self):
        """get_active_harness should use preferred when auto-detect disabled."""
        config = PolicyConfig()
        config.platform.auto_detect = False
        config.platform.preferred_harness = "cursor"
        config.delegation.primary = "forge"

        harness = get_active_harness(config)
        assert harness == "cursor"

    def test_get_active_harness_fallback_to_delegation(self):
        """get_active_harness should fall back to delegation.primary."""
        config = PolicyConfig()
        config.platform.auto_detect = True
        config.delegation.primary = "kilo"

        with patch(
            "policy_federation.config_loader._auto_detect_harness", return_value=None
        ):
            harness = get_active_harness(config)
            assert harness == "kilo"

    def test_is_tier_enabled_global_disabled(self):
        """is_tier_enabled should return False when risk assessment disabled."""
        config = PolicyConfig()
        config.risk_assessment.enabled = False

        assert is_tier_enabled(config, 1) is False
        assert is_tier_enabled(config, 2) is False
        assert is_tier_enabled(config, 3) is False
        assert is_tier_enabled(config, 4) is False

    def test_is_tier_enabled_specific_tier(self):
        """is_tier_enabled should check specific tier when global enabled."""
        config = PolicyConfig()
        config.risk_assessment.enabled = True
        config.risk_assessment.tier_2.enabled = False

        assert is_tier_enabled(config, 1) is True
        assert is_tier_enabled(config, 2) is False
        assert is_tier_enabled(config, 3) is True

    def test_get_cache_db_path_default(self):
        """get_cache_db_path should return default path."""
        config = PolicyConfig()
        path = get_cache_db_path(config)

        assert ".phenotype" in str(path)
        assert "cache" in str(path)
        assert path.name == "delegate_cache.db"

    def test_get_cache_db_path_custom(self):
        """get_cache_db_path should respect custom path."""
        config = PolicyConfig()
        config.cache.db_path = Path("/custom/cache.db")

        path = get_cache_db_path(config)
        assert path == Path("/custom/cache.db")

    def test_get_audit_log_path_disabled(self):
        """get_audit_log_path should return None when audit disabled."""
        config = PolicyConfig()
        config.audit.enabled = False

        path = get_audit_log_path(config)
        assert path is None

    def test_get_audit_log_path_default(self):
        """get_audit_log_path should return default path when enabled."""
        config = PolicyConfig()
        config.audit.enabled = True

        path = get_audit_log_path(config)
        assert path is not None
        assert ".phenotype" in str(path)


class TestConfigValidation:
    """Test configuration validation."""

    def test_valid_modes(self):
        """Mode should be one of valid values."""
        valid_modes = ["enforce", "audit", "disabled"]

        for mode in valid_modes:
            config = PolicyConfig()
            config.mode = mode
            assert config.mode == mode

    def test_valid_ask_modes(self):
        """Ask mode should be one of valid values."""
        valid_modes = ["ask", "delegate", "review", "allow"]

        for mode in valid_modes:
            config = PolicyConfig()
            config.ask_mode = mode
            assert config.ask_mode == mode

    def test_cache_ttl_positive(self):
        """Cache TTL should be positive."""
        config = PolicyConfig()
        assert config.cache.ttl_seconds > 0

    def test_timeout_values_reasonable(self):
        """Timeout values should be reasonable."""
        config = PolicyConfig()

        # All timeouts should be between 5 and 300 seconds
        for harness, harness_config in config.delegation.harnesses.items():
            assert 5 <= harness_config.timeout_seconds <= 300, (
                f"{harness} timeout unreasonable"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
