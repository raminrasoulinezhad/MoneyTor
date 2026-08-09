# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Smoke tests proving the test harness and package imports work."""

from __future__ import annotations

import moneytor


def test_version_is_exposed() -> None:
    assert moneytor.__version__ == "0.1.0"


def test_entrypoint_is_importable() -> None:
    # main() launches a blocking GUI event loop, so we only assert it is wired.
    from main import main

    assert callable(main)
