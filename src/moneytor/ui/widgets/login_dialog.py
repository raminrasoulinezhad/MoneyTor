"""A modal password gate shown before the cockpit opens.

The app is unusable until the correct password is entered. The dialog keeps
itself open on a wrong attempt (clearing the field and showing an inline error)
and only accepts on a match; closing or cancelling rejects, which the caller
treats as "quit without launching".
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from moneytor.ui.theme import Theme, stylesheet_for


class LoginDialog(QDialog):
    """Password prompt that accepts only when the entered value matches."""

    def __init__(self, expected_password: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expected = expected_password
        self.setObjectName("Root")
        self.setWindowTitle("MoneyTor — Sign in")
        self.setModal(True)
        self.setMinimumWidth(360)
        # The theme is normally applied to the main window; this gate opens
        # before it exists, so style it directly to match the cockpit.
        self.setStyleSheet(stylesheet_for(Theme.DARK))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("MoneyTor")
        title.setObjectName("PanelTitle")
        subtitle = QLabel("Enter your password to continue")
        subtitle.setObjectName("CardSubtitle")
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
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        unlock = QPushButton("Unlock")
        unlock.setDefault(True)
        unlock.clicked.connect(self._attempt)
        buttons.addWidget(cancel)
        buttons.addWidget(unlock)
        layout.addLayout(buttons)

        self._input.setFocus()

    def _attempt(self) -> None:
        if self._input.text() == self._expected:
            self.accept()
            return
        self._error.setText("Incorrect password. Try again.")
        self._error.setVisible(True)
        self._input.clear()
        self._input.setFocus()


def require_password(expected_password: str, parent: QWidget | None = None) -> bool:
    """Block on the login dialog. Return True if unlocked, False if cancelled."""
    dialog = LoginDialog(expected_password, parent)
    return dialog.exec() == QDialog.DialogCode.Accepted
