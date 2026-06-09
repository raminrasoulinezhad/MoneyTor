"""Bridge a worker-thread 2FA request to a GUI-thread prompt.

Connector authentication runs off the UI thread (see :class:`FetchWorker`), but
a Qt dialog must run on the GUI thread. :class:`GuiOtpProvider` is a callable
(matching ``WealthsimpleConnector``'s ``otp_provider`` contract) that, when
invoked from the worker thread, hands the request to the GUI thread via a queued
signal and blocks until the user submits or cancels.
"""

from __future__ import annotations

import queue

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
        self._result: queue.Queue[str] = queue.Queue(maxsize=1)
        # Queued: emitted from the worker thread, the slot runs on the GUI thread.
        self._requested.connect(self._show, Qt.ConnectionType.QueuedConnection)

    def __call__(self) -> str:
        """Invoked on the worker thread; blocks until the GUI returns a code."""
        self._requested.emit()
        return self._result.get()

    @Slot()
    def _show(self) -> None:
        self._result.put(prompt_otp(self.parent_widget))
