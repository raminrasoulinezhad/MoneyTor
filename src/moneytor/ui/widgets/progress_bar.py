# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""A determinate fetch progress bar shown while accounts are being refreshed."""

from __future__ import annotations

from PySide6.QtWidgets import QProgressBar, QWidget


class FetchProgressBar(QProgressBar):
    """Thin progress bar driven by per-account-source fetch progress.

    Hidden by default. :meth:`begin` shows it (indeterminate until the first
    concrete update arrives), :meth:`set_progress` advances it as each
    person/institution fetch completes, and :meth:`finish` hides and resets it.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FetchProgress")
        self.setTextVisible(True)
        self.setFixedHeight(22)
        self.hide()

    def begin(self) -> None:
        """Show a busy (indeterminate) bar before the first source reports in."""
        self.setRange(0, 0)  # min == max == 0 renders an indeterminate "busy" bar
        self.setFormat("Refreshing…")
        self.show()

    def set_progress(self, done: int, total: int, label: str) -> None:
        """Advance to ``done`` of ``total`` sources, captioned with ``label``."""
        if total <= 0:
            self.setRange(0, 0)
            self.setFormat(label or "Refreshing…")
            return
        self.setRange(0, total)
        self.setValue(done)
        self.setFormat(f"{label}  ·  %v / %m")
        self.show()

    def finish(self) -> None:
        """Hide and reset the bar once the fetch completes (or fails)."""
        self.reset()
        self.hide()
