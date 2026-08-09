# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Shared pytest fixtures and configuration.

`pythonpath = ["src"]` in pyproject makes `moneytor` and `main` importable
without an editable install.
"""

from __future__ import annotations

import os

# Run Qt headlessly so GUI tests work without a display server. Must be set
# before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
