"""GUI entrypoint for MoneyTor.

The full PySide6 cockpit is built in Phase 6 (see IMPLEMENTATION_PLAN.md).
For now this is a placeholder so the launch command is wired up.
"""

from __future__ import annotations

import sys

from moneytor import __version__


def main() -> int:
    """Application entrypoint. Returns a process exit code."""
    print(f"MoneyTor v{__version__} — GUI not yet implemented (Phase 6).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
