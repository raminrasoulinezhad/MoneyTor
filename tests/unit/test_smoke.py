# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Smoke tests proving the test harness and package imports work."""

from __future__ import annotations

import moneytor


def test_version_is_exposed() -> None:
    assert moneytor.__version__ == "0.1.0"


def test_entrypoint_is_importable() -> None:
    # main() launches a blocking GUI event loop, so we only assert it is wired.
    from main import main

    assert callable(main)
