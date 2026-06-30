# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""A fixture-driven connector for development and testing.

``MockConnector`` implements the :class:`~moneytor.connectors.base.Connector`
contract without any network access, so the entire downstream stack
(aggregation, GUI, reporting) can be built and tested against realistic data
before the live connectors land in Phase 8.

The :func:`accounts_from_payload` mapper also serves as the reference shape for
the normalized JSON that real connectors will produce.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from moneytor.domain.enums import AccountType, AssetClass, Currency, Institution
from moneytor.domain.models import Account, Holding
from moneytor.domain.money import Money

from .errors import AuthError, ConnectorError, FetchError


def _money_from(node: Mapping[str, Any], where: str) -> Money:
    try:
        return Money(Decimal(str(node["amount"])), Currency(node["currency"]))
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise FetchError(f"Malformed money value at {where}: {node!r}.") from exc


def _holding_from(node: Mapping[str, Any]) -> Holding:
    try:
        raw_yield = node.get("dividend_yield")
        return Holding(
            symbol=str(node["symbol"]),
            name=str(node.get("name", "")),
            sector=str(node.get("sector", "")),
            exchange=str(node["exchange"]),
            asset_class=AssetClass(node["asset_class"]),
            quantity=Decimal(str(node["quantity"])),
            book_value=_money_from(node["book_value"], "holding.book_value"),
            market_value=_money_from(node["market_value"], "holding.market_value"),
            dividend_yield=Decimal(str(raw_yield)) if raw_yield is not None else None,
        )
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise FetchError(f"Malformed holding: {node!r}.") from exc


def _account_from(node: Mapping[str, Any]) -> Account:
    try:
        holdings = tuple(_holding_from(h) for h in node.get("holdings", ()))
        return Account(
            id=str(node["id"]),
            person_id=str(node["person_id"]),
            institution=Institution(node["institution"]),
            account_type=AccountType(node["account_type"]),
            cash=_money_from(node["cash"], "account.cash"),
            holdings=holdings,
        )
    except (KeyError, ValueError) as exc:
        raise FetchError(f"Malformed account: {node!r}.") from exc


def accounts_from_payload(payload: Sequence[Mapping[str, Any]]) -> tuple[Account, ...]:
    """Map a normalized JSON payload into domain :class:`Account` models."""
    return tuple(_account_from(node) for node in payload)


def load_accounts(path: str | Path) -> tuple[Account, ...]:
    """Load and map accounts from a JSON fixture file."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FetchError(f"Cannot read fixture {path}: {exc}.") from exc
    if not isinstance(raw, list):
        raise FetchError(f"Fixture {path} must contain a JSON array of accounts.")
    return accounts_from_payload(raw)


@dataclass
class MockConnector:
    """A connector that serves pre-built accounts from memory or a fixture."""

    institution: Institution
    accounts: tuple[Account, ...] = field(default_factory=tuple)
    fail_auth: bool = False
    _authenticated: bool = field(default=False, init=False)

    @classmethod
    def from_fixture(cls, institution: Institution, path: str | Path) -> MockConnector:
        """Build a connector whose accounts come from a JSON fixture file."""
        return cls(institution=institution, accounts=load_accounts(path))

    def authenticate(self) -> None:
        if self.fail_auth:
            raise AuthError(f"Mock authentication failed for {self.institution.value}.")
        self._authenticated = True

    def fetch_accounts(self) -> tuple[Account, ...]:
        if not self._authenticated:
            raise ConnectorError("Call authenticate() before fetch_accounts().")
        return self.accounts
