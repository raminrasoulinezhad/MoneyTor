# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Background fetch worker so the UI never blocks on connector I/O.

``FetchWorker`` runs a callable on a ``QThread`` and signals the result (or the
caught exception) back to the UI thread. Connector failures are reported via
:attr:`failed`, never raised into the event loop.

A task may optionally accept a single positional argument — a progress reporter
``report(done, total, label)``. When it does, the worker passes one in and
relays each call through the thread-safe :attr:`progress` signal so the UI can
drive a loading bar. Zero-arg tasks (e.g. the 2FA provider) are called as-is.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

# report(done, total, label): how many fetches are complete out of the total,
# plus a human-readable label for the one currently in flight.
ProgressFn = Callable[[int, int, str], None]


class FetchWorker(QThread):
    """Runs ``task()`` off the UI thread and emits the outcome.

    Uses ``succeeded`` rather than ``finished`` to avoid shadowing QThread's
    own built-in ``finished`` signal.
    """

    succeeded = Signal(object)
    failed = Signal(object)
    progress = Signal(int, int, str)  # done, total, label

    def __init__(self, task: Callable[..., Any], parent: Any | None = None) -> None:
        super().__init__(parent)
        self._task = task
        self._wants_progress = _accepts_positional_arg(task)

    def run(self) -> None:
        try:
            result = self._task(self._report) if self._wants_progress else self._task()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Boundary: any connector failure is reported, never crashes the UI.
            self.failed.emit(exc)
            return
        self.succeeded.emit(result)

    def _report(self, done: int, total: int, label: str) -> None:
        """Progress hook handed to the task (called on the worker thread).

        Emitting a signal across threads is queued by Qt, so the connected UI
        slot runs safely on the GUI thread.
        """
        self.progress.emit(done, total, label)


def _accepts_positional_arg(task: Callable[..., Any]) -> bool:
    """True if ``task`` can be called with one positional argument (the reporter).

    Keeps the worker backward-compatible: zero-arg tasks (the OTP provider, test
    lambdas) are called with no args, while loaders that accept a reporter get
    one. Falls back to ``False`` for callables we cannot introspect.
    """
    try:
        params = inspect.signature(task).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL) for p in params
    )
