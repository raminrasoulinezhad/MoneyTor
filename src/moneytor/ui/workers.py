"""Background fetch worker so the UI never blocks on connector I/O.

``FetchWorker`` runs an arbitrary zero-arg callable on a ``QThread`` and signals
the result (or the caught exception) back to the UI thread. Connector failures
are reported via :attr:`failed`, never raised into the event loop.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class FetchWorker(QThread):
    """Runs ``task()`` off the UI thread and emits the outcome.

    Uses ``succeeded`` rather than ``finished`` to avoid shadowing QThread's
    own built-in ``finished`` signal.
    """

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, task: Callable[[], Any], parent: Any | None = None) -> None:
        super().__init__(parent)
        self._task = task

    def run(self) -> None:
        try:
            result = self._task()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Boundary: any connector failure is reported, never crashes the UI.
            self.failed.emit(exc)
            return
        self.succeeded.emit(result)
