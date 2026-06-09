"""A modal 2FA prompt for institutions that require a one-time code."""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QLineEdit, QWidget


def prompt_otp(parent: QWidget | None = None, institution: str = "Wealthsimple") -> str:
    """Ask the user for a 2FA code. Returns ``""`` if they cancel.

    Must be called on the GUI thread (it runs a modal dialog).
    """
    code, accepted = QInputDialog.getText(
        parent,
        f"{institution} two-factor authentication",
        f"Enter the {institution} verification code:",
        QLineEdit.EchoMode.Normal,
    )
    return code.strip() if accepted else ""
