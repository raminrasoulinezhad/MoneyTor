# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Logging setup with secret redaction.

Even though :class:`~moneytor.config.secret.Secret` already redacts itself,
this filter is defence-in-depth: if a revealed secret value ever reaches a log
message (e.g. embedded in an API error string), it is scrubbed before emission.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

_REDACTED = "***"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


class RedactionFilter(logging.Filter):
    """Replaces known secret substrings in log records with ``***``."""

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        # Longest first so overlapping secrets are fully masked.
        self._secrets = sorted({s for s in secrets if s}, key=len, reverse=True)

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        message = record.getMessage()
        redacted = message
        for secret in self._secrets:
            redacted = redacted.replace(secret, _REDACTED)
        if redacted != message:
            # Collapse args into the already-formatted, scrubbed message.
            record.msg = redacted
            record.args = None
        return True


def setup_logging(level: str = "INFO", secrets: Iterable[str] = ()) -> None:
    """Configure root logging with a formatter and redaction filter.

    Args:
        level: Log level name (e.g. ``"INFO"``).
        secrets: Revealed secret strings to scrub from all log output.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(RedactionFilter(secrets))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
