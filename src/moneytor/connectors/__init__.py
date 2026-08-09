# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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
