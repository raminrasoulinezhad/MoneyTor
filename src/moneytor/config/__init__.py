# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Configuration & secrets layer.

The only sanctioned boundary between raw environment/`.env` values and the rest
of the application.
"""

from __future__ import annotations

from .errors import ConfigError
from .logging import RedactionFilter, setup_logging
from .secret import Secret
from .settings import PersonCredentials, Settings, load_settings

__all__ = [
    "ConfigError",
    "PersonCredentials",
    "RedactionFilter",
    "Secret",
    "Settings",
    "load_settings",
    "setup_logging",
]
