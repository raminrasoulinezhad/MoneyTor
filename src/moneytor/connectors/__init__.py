"""Broker connectors — normalize disparate brokerage data behind one contract."""

from __future__ import annotations

from .base import Connector
from .errors import AuthError, ConnectorError, FetchError, RateLimitError
from .mock import MockConnector, accounts_from_payload, load_accounts

__all__ = [
    "AuthError",
    "Connector",
    "ConnectorError",
    "FetchError",
    "MockConnector",
    "RateLimitError",
    "accounts_from_payload",
    "load_accounts",
]
