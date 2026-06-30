# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Tests for the snapshot cache (Phase 10)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from moneytor.connectors import load_accounts
from moneytor.domain import Currency, Money, Person
from moneytor.persistence import SnapshotCache

FIXTURE = Path(__file__).parent.parent / "fixtures" / "mock_accounts.json"


def _people() -> tuple[Person, ...]:
    return (Person(id="ramin", name="Ramin", accounts=load_accounts(FIXTURE)),)


def test_missing_cache_returns_none(tmp_path: Path) -> None:
    assert SnapshotCache(tmp_path / "snap.json").load() is None


def test_roundtrip_preserves_data(tmp_path: Path) -> None:
    cache = SnapshotCache(tmp_path / "snap.json")
    cache.save(_people(), Currency.CAD, as_of="2026-06-08")

    loaded = cache.load()
    assert loaded is not None
    assert loaded.display_currency is Currency.CAD
    assert loaded.as_of == "2026-06-08"
    assert len(loaded.people) == 1

    person = loaded.people[0]
    assert person.name == "Ramin"
    assert len(person.accounts) == 3
    tfsa = person.accounts[0]
    assert tfsa.cash == Money.of("1500.00", Currency.CAD)
    assert tfsa.holdings[0].symbol == "SHOP"
    assert tfsa.holdings[0].name == "Shopify Inc."  # name survives the round-trip
    assert tfsa.holdings[0].market_value == Money.of("1200.50", Currency.CAD)
    # Dividend yield survives the round-trip (SHOP has none; VFV does).
    assert tfsa.holdings[0].dividend_yield is None
    vfv = next(h for h in tfsa.holdings if h.symbol == "VFV")
    assert vfv.dividend_yield == Decimal("0.012")


def test_stale_schema_version_is_ignored(tmp_path: Path) -> None:
    import json

    path = tmp_path / "snap.json"
    cache = SnapshotCache(path)
    cache.save(_people(), Currency.CAD)
    # Simulate an older cache by dropping the version marker.
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["version"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert cache.load() is None


def test_backward_compatible_older_version_still_loads(tmp_path: Path) -> None:
    """An additive schema bump must not discard a user's cached values.

    A cache written before ``dividend_yield`` existed (version 3, no such field)
    still loads instantly so the dashboard shows previous values on launch; the
    missing field simply reads as ``None`` until the next live fetch.
    """
    import json

    path = tmp_path / "snap.json"
    cache = SnapshotCache(path)
    cache.save(_people(), Currency.CAD)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = 3  # an older, still-supported schema
    for person in data["people"]:
        for account in person["accounts"]:
            for holding in account["holdings"]:
                holding.pop("dividend_yield", None)
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = cache.load()
    assert loaded is not None
    assert len(loaded.people[0].accounts) == 3
    assert all(
        h.dividend_yield is None for p in loaded.people for a in p.accounts for h in a.holdings
    )


def test_corrupt_cache_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "snap.json"
    path.write_text("{ broken", encoding="utf-8")
    assert SnapshotCache(path).load() is None


def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    cache = SnapshotCache(tmp_path / "deep" / "snap.json")
    cache.save(_people(), Currency.CAD)
    assert (tmp_path / "deep" / "snap.json").exists()


def test_save_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "snap.json"
    SnapshotCache(path).save(_people(), Currency.CAD)
    assert (path.stat().st_mode & 0o777) == 0o600  # financial data, owner-only
