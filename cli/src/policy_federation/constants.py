"""Shared policy federation constants."""
from __future__ import annotations

ASK_MODE_FAIL = "fail"
ASK_MODE_ALLOW = "allow"
ASK_MODE_REVIEW = "review"
ASK_MODE_CHOICES = (ASK_MODE_FAIL, ASK_MODE_ALLOW, ASK_MODE_REVIEW)
DEFAULT_ASK_MODE = ASK_MODE_REVIEW
DEFAULT_REVIEW_BIN = "/opt/homebrew/bin/codex"
DEFAULT_REVIEW_MODEL = "gpt-5.4-mini"

# Fallback reviewer (MiniMax via Droid)
DEFAULT_FALLBACK_REVIEW_BIN = "/opt/homebrew/bin/droid"
DEFAULT_FALLBACK_REVIEW_MODEL = "custom:minimax-m2.5-highspeed"
