"""Shared pytest fixtures and configuration.

`pythonpath = ["src"]` in pyproject makes `moneytor` and `main` importable
without an editable install.
"""

from __future__ import annotations

import os

# Run Qt headlessly so GUI tests work without a display server. Must be set
# before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
