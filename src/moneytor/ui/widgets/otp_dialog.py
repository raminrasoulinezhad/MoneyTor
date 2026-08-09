# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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
