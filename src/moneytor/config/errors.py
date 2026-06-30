# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Configuration error types."""

from __future__ import annotations


class ConfigError(Exception):
    """Raised when configuration is missing, malformed, or invalid.

    Carries a human-readable, actionable message — surfaced at startup so the
    user knows exactly which key to fix.
    """
