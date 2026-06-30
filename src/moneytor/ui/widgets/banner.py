# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""A dismissible error banner shown when a data fetch fails.

Keeps connector failures visible without crashing or blocking the UI
(CLAUDE.md graceful-degradation rule).
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class ErrorBanner(QWidget):
    """A hidden-by-default red banner with a message and dismiss button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ErrorBanner")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        self._label = QLabel("")
        self._label.setObjectName("ErrorBannerText")
        self._label.setWordWrap(True)

        dismiss = QPushButton("Dismiss")
        dismiss.setObjectName("ErrorBannerDismiss")
        dismiss.clicked.connect(self.hide)

        layout.addWidget(self._label, stretch=1)
        layout.addWidget(dismiss)
        self.hide()

    def show_message(self, message: str) -> None:
        """Display ``message`` and make the banner visible."""
        self._label.setText(message)
        self.show()

    @property
    def message(self) -> str:
        """The current banner text (used by tests)."""
        return self._label.text()
