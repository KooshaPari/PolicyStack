"""Policy federation package.

Multi-platform policy delegation with learning, fallback chains, and
tiered risk assessment. Supports: forge, opencode, cursor, codex,
droid, kilo, forgecode
"""

__version__ = "0.3.0"

# Core delegation
from .delegate import (
    HARNESS_CONFIG,
    HARNESS_FALLBACK,
    DelegateContext,
    DelegateResult,
    clear_cache,
    delegate_ask,
    get_cache_stats,
)

# Risk assessment
from .risk import (
    RiskAssessment,
    RiskTier,
    assess_risk_tiered,
    get_tiered_decision_path,
    is_destructive_pattern,
    is_read_operation,
)

__all__ = [
    # Version
    "__version__",
    # Delegation
    "DelegateContext",
    "DelegateResult",
    "delegate_ask",
    "get_cache_stats",
    "clear_cache",
    "HARNESS_FALLBACK",
    "HARNESS_CONFIG",
    # Risk
    "RiskTier",
    "RiskAssessment",
    "assess_risk_tiered",
    "get_tiered_decision_path",
    "is_read_operation",
    "is_destructive_pattern",
]
