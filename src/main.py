"""GUI entrypoint for MoneyTor — launches the PySide6 cockpit (Phase 6)."""

from __future__ import annotations

import sys

from moneytor.ui.app import run_app


def main() -> int:
    """Application entrypoint. Returns a process exit code."""
    return run_app(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
