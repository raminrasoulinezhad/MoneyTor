"""Persist fetched portfolio data for offline viewing and fast cold starts.

Caches the normalized people/accounts (the expensive-to-fetch inputs) as JSON;
aggregation re-runs cheaply on load. A corrupt or missing cache yields ``None``
so the app simply falls back to a live fetch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from moneytor.domain.enums import AccountType, AssetClass, Currency, Institution
from moneytor.domain.models import Account, Holding, Person
from moneytor.domain.money import Money

DEFAULT_CACHE_PATH = Path(".cache") / "snapshot.json"
# Bump when the serialized holding/account shape changes so stale caches
# (e.g. missing name/sector/52w) are ignored rather than shown with blank fields.
_SCHEMA_VERSION = 3


@dataclass(frozen=True)
class CachedPortfolio:
    """The deserialized contents of a snapshot cache."""

    people: tuple[Person, ...]
    display_currency: Currency
    as_of: str | None = field(default=None)


def _money_dict(money: Money) -> dict[str, str]:
    return {"amount": str(money.amount), "currency": money.currency.value}


def _holding_dict(holding: Holding) -> dict[str, Any]:
    return {
        "symbol": holding.symbol,
        "name": holding.name,
        "sector": holding.sector,
        "exchange": holding.exchange,
        "asset_class": holding.asset_class.value,
        "quantity": str(holding.quantity),
        "book_value": _money_dict(holding.book_value),
        "market_value": _money_dict(holding.market_value),
        "high_52w": _money_dict(holding.high_52w) if holding.high_52w is not None else None,
    }


def _account_dict(account: Account) -> dict[str, Any]:
    return {
        "id": account.id,
        "person_id": account.person_id,
        "institution": account.institution.value,
        "account_type": account.account_type.value,
        "cash": _money_dict(account.cash),
        "holdings": [_holding_dict(h) for h in account.holdings],
    }


def _person_dict(person: Person) -> dict[str, Any]:
    return {
        "id": person.id,
        "name": person.name,
        "accounts": [_account_dict(a) for a in person.accounts],
    }


def _money(node: Any) -> Money:
    return Money(Decimal(str(node["amount"])), Currency(node["currency"]))


def _holding(node: Any) -> Holding:
    return Holding(
        symbol=str(node["symbol"]),
        name=str(node.get("name", "")),
        sector=str(node.get("sector", "")),
        exchange=str(node["exchange"]),
        asset_class=AssetClass(node["asset_class"]),
        quantity=Decimal(str(node["quantity"])),
        book_value=_money(node["book_value"]),
        market_value=_money(node["market_value"]),
        high_52w=_money(node["high_52w"]) if node.get("high_52w") else None,
    )


def _account(node: Any) -> Account:
    return Account(
        id=str(node["id"]),
        person_id=str(node["person_id"]),
        institution=Institution(node["institution"]),
        account_type=AccountType(node["account_type"]),
        cash=_money(node["cash"]),
        holdings=tuple(_holding(h) for h in node["holdings"]),
    )


def _person(node: Any) -> Person:
    return Person(
        id=str(node["id"]),
        name=str(node["name"]),
        accounts=tuple(_account(a) for a in node["accounts"]),
    )


class SnapshotCache:
    """Reads/writes a portfolio cache as JSON."""

    def __init__(self, path: str | Path = DEFAULT_CACHE_PATH) -> None:
        self._path = Path(path)

    def save(
        self,
        people: tuple[Person, ...],
        display_currency: Currency,
        as_of: str | None = None,
    ) -> None:
        """Serialize ``people`` and metadata to the cache file."""
        data = {
            "version": _SCHEMA_VERSION,
            "display_currency": display_currency.value,
            "as_of": as_of,
            "people": [_person_dict(p) for p in people],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> CachedPortfolio | None:
        """Return the cached portfolio, or ``None`` if missing/corrupt."""
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if data.get("version") != _SCHEMA_VERSION:
                return None  # stale schema (e.g. pre-name/sector) — refetch
            return CachedPortfolio(
                people=tuple(_person(p) for p in data["people"]),
                display_currency=Currency(data["display_currency"]),
                as_of=data.get("as_of"),
            )
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            ValueError,
            InvalidOperation,
            TypeError,
        ):
            return None
