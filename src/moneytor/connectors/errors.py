"""Connector-layer error types.

Connectors translate every failure mode (auth, rate-limit, transport, parsing)
into one of these so the GUI never sees a raw network/HTTP exception and can
degrade gracefully per the CLAUDE.md error-handling rules.
"""

from __future__ import annotations


class ConnectorError(Exception):
    """Base class for all connector failures."""


class AuthError(ConnectorError):
    """Authentication or authorization failed (bad/expired credentials)."""


class RateLimitError(ConnectorError):
    """The institution throttled the request; retry after backing off."""


class FetchError(ConnectorError):
    """A transport or response-parsing failure while fetching data."""
