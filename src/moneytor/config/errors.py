"""Configuration error types."""

from __future__ import annotations


class ConfigError(Exception):
    """Raised when configuration is missing, malformed, or invalid.

    Carries a human-readable, actionable message — surfaced at startup so the
    user knows exactly which key to fix.
    """
