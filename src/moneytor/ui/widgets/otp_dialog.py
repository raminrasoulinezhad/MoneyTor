# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""A modal 2FA prompt for institutions that require a one-time code."""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QLineEdit, QWidget


def prompt_otp(
    parent: QWidget | None = None,
    institution: str = "Wealthsimple",
    account: str = "",
) -> str:
    """Ask the user for a 2FA code. Returns ``""`` if they cancel.

    ``account`` names whose login this is (e.g. ``"ramin (you@example.com)"``)
    so the user knows which credentials/code to enter. Must run on the GUI thread.
    """
    who = f" for {account}" if account else ""
    code, accepted = QInputDialog.getText(
        parent,
        f"{institution} two-factor authentication",
        f"Enter the {institution} verification code{who}:",
        QLineEdit.EchoMode.Normal,
    )
    return code.strip() if accepted else ""
