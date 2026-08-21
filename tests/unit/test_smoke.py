# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Smoke tests proving the test harness and package imports work."""

from __future__ import annotations

import moneytor


def test_version_is_exposed() -> None:
    assert moneytor.__version__ == "1.3.0"


def test_package_metadata_version_matches_dunder_version() -> None:
    # pyproject declares the version dynamic and reads it from __init__.py, so
    # these can only disagree if that wiring breaks. They did drift once —
    # 0.1.0 in the window title against 1.0.0 in pyproject — so pin them.
    from importlib.metadata import version

    assert version("moneytor") == moneytor.__version__


def test_entrypoint_is_importable() -> None:
    # main() launches a blocking GUI event loop, so we only assert it is wired.
    from main import main

    assert callable(main)
