# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Bridge a worker-thread 2FA request to a GUI-thread prompt.

Connector authentication runs off the UI thread (see :class:`FetchWorker`), but
a Qt dialog must run on the GUI thread. :class:`GuiOtpProvider` is a callable
(matching ``WealthsimpleConnector``'s ``otp_provider`` contract) that, when
invoked from the worker thread, hands the request to the GUI thread via a queued
signal and blocks until the user submits or cancels.
"""

from __future__ import annotations

import queue
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QWidget

from moneytor.ui.widgets.otp_dialog import prompt_otp


class GuiOtpProvider(QObject):
    """A thread-safe ``otp_provider``: blocks the caller while the GUI prompts.

    Construct on the GUI thread so the dialog slot runs there. Set
    :attr:`parent_widget` once the main window exists to center the dialog.
    """

    _requested = Signal()

    def __init__(self, parent_widget: QWidget | None = None) -> None:
        super().__init__()
        self.parent_widget = parent_widget
        self._account = ""
        self._result: queue.Queue[str] = queue.Queue(maxsize=1)
        # Queued: emitted from the worker thread, the slot runs on the GUI thread.
        self._requested.connect(self._show, Qt.ConnectionType.QueuedConnection)

    def __call__(self) -> str:
        """Invoked on the worker thread; blocks until the GUI returns a code."""
        self._requested.emit()
        return self._result.get()

    def for_account(self, person_id: str, email: str) -> Callable[[], str]:
        """Return a zero-arg ``otp_provider`` whose prompt names this account.

        Logins run sequentially on the worker thread, so stashing the label on
        the instance before each prompt is safe.
        """

        def provider() -> str:
            self._account = f"{person_id} ({email})" if email else person_id
            return self()

        return provider

    @Slot()
    def _show(self) -> None:
        self._result.put(prompt_otp(self.parent_widget, account=self._account))
