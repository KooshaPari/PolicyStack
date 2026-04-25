"""Configuration loader for PolicyStack unified policy.yaml.

Loads and validates configuration from:
- ~/.phenotype/config.yaml (global)
- .phenotype/policy.yaml (repo-specific, overrides global)
- Environment variables (override both)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PlatformConfig:
    """Platform detection and preference settings."""

    auto_detect: bool = True
    preferred_harness: str = "opencode"
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskTierConfig:
    """Configuration for a single risk tier."""

    enabled: bool = True
    extra_patterns: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)


@dataclass
class RiskAssessmentConfig:
    """Risk assessment configuration."""

    enabled: bool = True
    tier_1: RiskTierConfig = field(default_factory=lambda: RiskTierConfig(enabled=True))
    tier_2: RiskTierConfig = field(default_factory=lambda: RiskTierConfig(enabled=True))
    tier_3: RiskTierConfig = field(
        default_factory=lambda: RiskTierConfig(enabled=True, max_risk_score=0.5)
    )
    tier_4: RiskTierConfig = field(default_factory=lambda: RiskTierConfig(enabled=True))
    safe_paths: list[str] = field(default_factory=lambda: [".worktrees/", "worktrees/"])
    high_risk_paths: list[str] = field(
        default_factory=lambda: ["/etc/", "/usr/bin/", "/usr/sbin/", "/bin/", "/sbin/"]
    )


@dataclass
class CacheConfig:
    """Decision caching configuration."""

    enabled: bool = True
    db_path: Path | None = None
    ttl_seconds: int = 86400
    max_entries: int = 10000
    pattern_matching: bool = True


@dataclass
class HarnessConfig:
    """Configuration for a single harness."""

    enabled: bool = True
    model: str = "default"
    timeout_seconds: int = 30
    api_url: str | None = None


@dataclass
class DelegationConfig:
    """Multi-platform delegation configuration."""

    enabled: bool = True
    primary: str = "opencode"
    fallback_chain: list[str] = field(
        default_factory=lambda: ["opencode", "forge", "cursor", "local-fast"]
    )
    harnesses: dict[str, HarnessConfig] = field(default_factory=dict)
    local_fast: dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "max_eval_time_ms": 100}
    )


@dataclass
class GuardianConfig:
    """Guardian mode (headless review) configuration."""

    enabled: bool = True
    primary: str = "codex"
    fallback: str = "opencode"
    timeout_seconds: int = 30
    confirm_guardian_allows: bool = False


@dataclass
class AuditConfig:
    """Audit logging configuration."""

    enabled: bool = True
    log_path: Path | None = None
    format: str = "json"
    log_decisions: bool = True
    log_commands: bool = True
    log_errors: bool = True
    stream_url: str | None = None


@dataclass
class PolicyConfig:
    """Unified PolicyStack configuration."""

    mode: str = "enforce"
    ask_mode: str = "delegate"
    repo_root: Path | None = None

    platform: PlatformConfig = field(default_factory=PlatformConfig)
    risk_assessment: RiskAssessmentConfig = field(default_factory=RiskAssessmentConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    delegation: DelegationConfig = field(default_factory=DelegationConfig)
    guardian: GuardianConfig = field(default_factory=GuardianConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)

    # Advanced settings
    max_command_length: int = 10000
    evaluation_timeout_seconds: int = 5
    debug: bool = False
    strict_mode: bool = False


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Load YAML file and return dict."""
    try:
        import yaml

        if path.exists():
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
    except ImportError:
        pass
    except Exception:
        pass
    return {}


def _apply_env_overrides(config: PolicyConfig) -> PolicyConfig:
    """Apply environment variable overrides to config."""
    env_map = {
        "POLICY_MODE": lambda v: setattr(config, "mode", v),
        "POLICY_ASK_MODE": lambda v: setattr(config, "ask_mode", v),
        "POLICY_DELEGATE_HARNESS": lambda v: setattr(config.delegation, "primary", v),
        "POLICY_REVIEW_BIN": lambda v: setattr(config.guardian, "primary", v),
        "POLICY_AUDIT_LOG_PATH": lambda v: setattr(config.audit, "log_path", Path(v)),
        "FORGECODE_API_KEY": lambda v: None,  # Just validates it exists
    }

    for env_var, setter in env_map.items():
        value = os.environ.get(env_var)
        if value:
            setter(value)

    return config


def load_config(
    repo_root: Path | None = None,
    global_config_path: Path | None = None,
) -> PolicyConfig:
    """Load unified configuration from all sources.

    Priority (highest first):
    1. Environment variables
    2. Repo-specific: .phenotype/policy.yaml
    3. Global: ~/.phenotype/config.yaml
    4. Defaults
    """
    config = PolicyConfig()

    # Load global config
    if global_config_path is None:
        global_config_path = Path.home() / ".phenotype" / "config.yaml"
    global_data = _load_yaml_file(global_config_path)
    _merge_dict_into_config(config, global_data)

    # Load repo-specific config
    if repo_root is None:
        repo_root = Path.cwd()
    repo_config_path = repo_root / ".phenotype" / "policy.yaml"
    repo_data = _load_yaml_file(repo_config_path)
    _merge_dict_into_config(config, repo_data)

    # Apply environment overrides
    config = _apply_env_overrides(config)

    # Auto-detect repo root if not set
    if config.repo_root is None:
        config.repo_root = repo_root

    return config


def _merge_dict_into_config(config: PolicyConfig, data: dict[str, Any]) -> None:
    """Merge a dict into the config dataclass."""
    if not data:
        return

    # Simple fields
    for key in [
        "mode",
        "ask_mode",
        "max_command_length",
        "evaluation_timeout_seconds",
        "debug",
        "strict_mode",
    ]:
        if key in data:
            setattr(config, key, data[key])

    # Nested dataclasses
    if "platform" in data:
        platform_data = data["platform"]
        if "auto_detect" in platform_data:
            config.platform.auto_detect = platform_data["auto_detect"]
        if "preferred_harness" in platform_data:
            config.platform.preferred_harness = platform_data["preferred_harness"]
        if "overrides" in platform_data:
            config.platform.overrides.update(platform_data["overrides"])

    if "risk_assessment" in data:
        risk_data = data["risk_assessment"]
        if "enabled" in risk_data:
            config.risk_assessment.enabled = risk_data["enabled"]
        # Tiers can be merged individually
        for tier in ["tier_1", "tier_2", "tier_3", "tier_4"]:
            if tier in risk_data:
                tier_config = getattr(config.risk_assessment, tier)
                tier_data = risk_data[tier]
                if "enabled" in tier_data:
                    tier_config.enabled = tier_data["enabled"]
                if "extra_patterns" in tier_data:
                    tier_config.extra_patterns = tier_data["extra_patterns"]
                if "patterns" in tier_data:
                    tier_config.patterns = tier_data["patterns"]

    if "cache" in data:
        cache_data = data["cache"]
        if "enabled" in cache_data:
            config.cache.enabled = cache_data["enabled"]
        if "ttl_seconds" in cache_data:
            config.cache.ttl_seconds = cache_data["ttl_seconds"]
        if "max_entries" in cache_data:
            config.cache.max_entries = cache_data["max_entries"]
        if "pattern_matching" in cache_data:
            config.cache.pattern_matching = cache_data["pattern_matching"]

    if "delegation" in data:
        del_data = data["delegation"]
        if "enabled" in del_data:
            config.delegation.enabled = del_data["enabled"]
        if "primary" in del_data:
            config.delegation.primary = del_data["primary"]
        if "fallback_chain" in del_data:
            config.delegation.fallback_chain = del_data["fallback_chain"]
        if "local_fast" in del_data:
            config.delegation.local_fast.update(del_data["local_fast"])

    if "guardian" in data:
        guard_data = data["guardian"]
        if "enabled" in guard_data:
            config.guardian.enabled = guard_data["enabled"]
        if "primary" in guard_data:
            config.guardian.primary = guard_data["primary"]
        if "fallback" in guard_data:
            config.guardian.fallback = guard_data["fallback"]
        if "timeout_seconds" in guard_data:
            config.guardian.timeout_seconds = guard_data["timeout_seconds"]

    if "audit" in data:
        audit_data = data["audit"]
        if "enabled" in audit_data:
            config.audit.enabled = audit_data["enabled"]
        if "format" in audit_data:
            config.audit.format = audit_data["format"]
        if "log_decisions" in audit_data:
            config.audit.log_decisions = audit_data["log_decisions"]
        if "log_commands" in audit_data:
            config.audit.log_commands = audit_data["log_commands"]


def get_active_harness(config: PolicyConfig) -> str:
    """Get the active harness based on configuration."""
    if not config.platform.auto_detect:
        return config.platform.preferred_harness

    # Auto-detect from environment
    from .delegate import _auto_detect_harness

    detected = _auto_detect_harness()
    if detected:
        return detected

    return config.delegation.primary


def is_tier_enabled(config: PolicyConfig, tier: int) -> bool:
    """Check if a risk tier is enabled."""
    if not config.risk_assessment.enabled:
        return False

    tier_config = getattr(config.risk_assessment, f"tier_{tier}", None)
    if tier_config:
        return tier_config.enabled
    return False


def get_cache_db_path(config: PolicyConfig) -> Path:
    """Get the cache database path."""
    if config.cache.db_path:
        return config.cache.db_path
    return Path.home() / ".phenotype" / "cache" / "delegate_cache.db"


def get_audit_log_path(config: PolicyConfig) -> Path | None:
    """Get the audit log path."""
    if not config.audit.enabled:
        return None
    if config.audit.log_path:
        return config.audit.log_path
    return Path.home() / ".phenotype" / "audit.log"
