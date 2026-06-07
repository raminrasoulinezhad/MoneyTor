"""Smoke tests proving the test harness and package imports work."""

from __future__ import annotations

import moneytor
from main import main


def test_version_is_exposed() -> None:
    assert moneytor.__version__ == "0.1.0"


def test_main_returns_success() -> None:
    assert main() == 0
