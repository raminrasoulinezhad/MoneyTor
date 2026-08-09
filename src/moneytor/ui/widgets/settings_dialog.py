# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""The in-app Settings dialog opened from the toolbar's gear button.

Collects the controls that used to sit in the toolbar (private mode, theme,
export) alongside the launch-at-login toggle, so the cockpit's chrome stays for
navigation and the preferences live in one place.

The dialog owns no state. It emits a *request* per interaction and re-renders
from whatever :meth:`sync` is handed afterwards, so a rejected change (a wrong
password on the private-mode toggle, an autostart entry that could not be
written) snaps the control back without the dialog needing to know why.
"""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    """Application settings, shown over the cockpit as an application-modal dialog."""

    privateModeRequested = Signal(bool)  # user ticked/unticked private mode
    themeToggleRequested = Signal()  # user asked to switch dark <-> light
    exportRequested = Signal()  # user asked to write a report
    launchAtLoginRequested = Signal(bool)  # user ticked/unticked start at login

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Scopes the checkbox-indicator styling in the QSS to this dialog, so
        # the sidebar's account tree keeps its native check marks.
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("MoneyTor settings")
        self.setModal(True)
        self.setMinimumWidth(460)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(16)

        outer.addWidget(self._build_appearance())
        outer.addWidget(self._build_privacy())
        outer.addWidget(self._build_startup())
        outer.addWidget(self._build_data())

        self._error = QLabel("")
        self._error.setObjectName("SettingsError")
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        outer.addWidget(self._error)

        outer.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_button = QPushButton("Close")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        outer.addLayout(buttons)

    # -- public API --------------------------------------------------------- #

    def sync(
        self,
        *,
        private: bool,
        theme_name: str,
        other_theme_name: str,
        launch_at_login: bool,
        launch_supported: bool,
        launch_note: str,
    ) -> None:
        """Render the dialog from the window's current state.

        Signals are blocked throughout, so re-syncing after an action never
        loops back into the handler that triggered it.
        """
        with QSignalBlocker(self.private_checkbox), QSignalBlocker(self.launch_checkbox):
            self.private_checkbox.setChecked(private)
            self.launch_checkbox.setChecked(launch_at_login)
        self.launch_checkbox.setEnabled(launch_supported)
        self._launch_note.setText(launch_note)
        self._theme_value.setText(theme_name)
        self.theme_button.setText(f"Switch to {other_theme_name}")

    def show_error(self, message: str) -> None:
        """Surface a failed change inline rather than in another popup."""
        self._error.setText(message)
        self._error.setVisible(True)

    def clear_error(self) -> None:
        self._error.clear()
        self._error.setVisible(False)

    # -- sections ----------------------------------------------------------- #

    def _build_appearance(self) -> QWidget:
        section, layout = _section("Appearance")

        row = QHBoxLayout()
        label = QLabel("Theme")
        self._theme_value = QLabel("")
        self._theme_value.setObjectName("CardSubtitle")
        self.theme_button = QPushButton("Toggle theme")
        self.theme_button.clicked.connect(self.themeToggleRequested.emit)
        row.addWidget(label)
        row.addWidget(self._theme_value)
        row.addStretch(1)
        row.addWidget(self.theme_button)
        layout.addLayout(row)
        return section

    def _build_privacy(self) -> QWidget:
        section, layout = _section("Privacy")

        self.private_checkbox = QCheckBox("Private mode")
        self.private_checkbox.toggled.connect(self.privateModeRequested.emit)
        layout.addWidget(self.private_checkbox)

        note = QLabel(
            "Masks the total value, the dividend / GIC / income estimates, and "
            "each holding's share count and market value. Revealing them again "
            "requires your password."
        )
        note.setObjectName("SettingsNote")
        note.setWordWrap(True)
        layout.addWidget(note)
        return section

    def _build_startup(self) -> QWidget:
        section, layout = _section("Startup")

        self.launch_checkbox = QCheckBox("Open MoneyTor when I log in")
        self.launch_checkbox.toggled.connect(self.launchAtLoginRequested.emit)
        layout.addWidget(self.launch_checkbox)

        self._launch_note = QLabel("")
        self._launch_note.setObjectName("SettingsNote")
        self._launch_note.setWordWrap(True)
        layout.addWidget(self._launch_note)
        return section

    def _build_data(self) -> QWidget:
        section, layout = _section("Data")

        row = QHBoxLayout()
        self.export_button = QPushButton("Export report…")
        self.export_button.clicked.connect(self.exportRequested.emit)
        note = QLabel("Writes a PDF and a Markdown copy of the full portfolio.")
        note.setObjectName("SettingsNote")
        note.setWordWrap(True)
        row.addWidget(note, stretch=1)
        row.addWidget(self.export_button)
        layout.addLayout(row)
        return section

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Escape closes the dialog; nothing here is destructive to cancel.
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)


def _section(title: str) -> tuple[QWidget, QVBoxLayout]:
    """A titled card matching the dashboard's panel styling."""
    card = QWidget()
    card.setObjectName("Panel")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 16)
    layout.setSpacing(8)

    heading = QLabel(title)
    heading.setObjectName("PanelTitle")
    layout.addWidget(heading)
    return card, layout
