# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""GUI entrypoint for MoneyTor — launches the PySide6 cockpit (Phase 6)."""

from __future__ import annotations

import sys

from moneytor.ui.app import run_app


def main() -> int:
    """Application entrypoint. Returns a process exit code."""
    return run_app(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
