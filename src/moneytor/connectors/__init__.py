# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Broker connectors — normalize disparate brokerage data behind one contract."""

from __future__ import annotations

from .base import Connector
from .errors import AuthError, ConnectorError, FetchError, RateLimitError
from .mock import MockConnector, accounts_from_payload, load_accounts
from .questrade import QuestradeConnector
from .wealthsimple import WealthsimpleConnector

__all__ = [
    "AuthError",
    "Connector",
    "ConnectorError",
    "FetchError",
    "MockConnector",
    "QuestradeConnector",
    "RateLimitError",
    "WealthsimpleConnector",
    "accounts_from_payload",
    "load_accounts",
]
