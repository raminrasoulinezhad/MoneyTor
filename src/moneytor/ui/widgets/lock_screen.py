# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""A full-window lock overlay that gates the cockpit behind a password.

Rather than a small separate dialog, this is an opaque widget that covers the
entire main window — so the app *feels* locked rather than fronted by another
window. The cockpit is built empty behind it (no data loaded until unlocked),
and the overlay is removed on a correct password. A wrong attempt clears the
field and shows an inline error; ``Quit`` (or Escape) abandons the launch.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LockScreen(QWidget):
    """An opaque, full-window password gate overlaid on the main window."""

    unlocked = Signal()  # correct password entered
    cancelled = Signal()  # user chose to quit instead of unlocking

    def __init__(self, expected_password: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expected = expected_password
        # "Root" gives the overlay the themed window background (opaque), so
        # nothing behind it shows through; autofill paints it over the cockpit.
        self.setObjectName("Root")
        self.setAutoFillBackground(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._build_card())
        row.addStretch(1)
        outer.addLayout(row)

        outer.addStretch(1)

        self._input.setFocus()

    def _build_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("KpiCard")  # reuse the rounded, shadowed card style
        card.setFixedWidth(360)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("MoneyTor")
        title.setObjectName("PanelTitle")
        subtitle = QLabel("Locked — enter your password to continue")
        subtitle.setObjectName("CardSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self._input = QLineEdit()
        self._input.setEchoMode(QLineEdit.EchoMode.Password)
        self._input.setPlaceholderText("Password")
        self._input.returnPressed.connect(self._attempt)
        layout.addWidget(self._input)

        self._error = QLabel("")
        self._error.setObjectName("ErrorBannerText")
        self._error.setVisible(False)
        self._error.setWordWrap(True)
        layout.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(self.cancelled.emit)
        unlock = QPushButton("Unlock")
        unlock.setDefault(True)
        unlock.clicked.connect(self._attempt)
        buttons.addWidget(quit_button)
        buttons.addWidget(unlock)
        layout.addLayout(buttons)
        return card

    def _attempt(self) -> None:
        if self._input.text() == self._expected:
            self.unlocked.emit()
            return
        self._error.setText("Incorrect password. Try again.")
        self._error.setVisible(True)
        self._input.clear()
        self._input.setFocus()

    def keyPressEvent(self, event) -> None:
        # Escape abandons the launch, mirroring the Quit button.
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)
