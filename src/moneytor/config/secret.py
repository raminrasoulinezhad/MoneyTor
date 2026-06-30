# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""A minimal secret wrapper that prevents accidental disclosure.

Secrets never render their value via ``repr``/``str``/f-strings, so they are
safe to log, print, or include in tracebacks. The real value is accessible only
through the explicit :meth:`Secret.reveal` call, making every disclosure a
greppable, auditable code site.
"""

from __future__ import annotations

from dataclasses import dataclass

_REDACTED = "***"


@dataclass(frozen=True, repr=False)
class Secret:
    """An immutable string secret with redacted text representations."""

    _value: str

    def reveal(self) -> str:
        """Return the underlying secret value. The only disclosure path."""
        return self._value

    def __repr__(self) -> str:
        return f"Secret({_REDACTED!r})"

    def __str__(self) -> str:
        return _REDACTED
