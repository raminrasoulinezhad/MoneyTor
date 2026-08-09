# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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
