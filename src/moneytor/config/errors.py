# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Configuration error types."""

from __future__ import annotations


class ConfigError(Exception):
    """Raised when configuration is missing, malformed, or invalid.

    Carries a human-readable, actionable message — surfaced at startup so the
    user knows exactly which key to fix.
    """
