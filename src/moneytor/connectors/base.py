# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""The broker-agnostic connector contract.

Every institution connector (mock, Wealthsimple, Questrade) implements this
protocol and returns *normalized* :class:`~moneytor.domain.models.Account`
models. Downstream layers depend only on this contract, never on a specific
broker's API shape.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from moneytor.domain.enums import Institution
from moneytor.domain.models import Account


@runtime_checkable
class Connector(Protocol):
    """Fetches and normalizes one person's accounts at one institution."""

    @property
    def institution(self) -> Institution:
        """The institution this connector talks to."""

    def authenticate(self) -> None:
        """Establish an authenticated session.

        Raises:
            AuthError: If credentials are missing, invalid, or expired.
        """

    def fetch_accounts(self) -> tuple[Account, ...]:
        """Return all accounts as normalized domain models.

        Raises:
            ConnectorError: On any auth/rate-limit/transport/parse failure.
        """
