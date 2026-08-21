# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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


def test_pre_v5_cache_is_discarded(tmp_path: Path) -> None:
    """v5 corrected a currency label, so earlier caches hold wrong data.

    Wealthsimple's 52-week high used to be tagged with the position's currency
    (always CAD) while the value is the security's own, so a v4 cache stores USD
    highs labelled CAD. That cannot be converted back, so those caches are
    dropped and refetched rather than displayed.
    """
    import json

    path = tmp_path / "snap.json"
    cache = SnapshotCache(path)
    cache.save(_people(), Currency.CAD)
    data = json.loads(path.read_text(encoding="utf-8"))

    for stale in (3, 4):
        data["version"] = stale
        path.write_text(json.dumps(data), encoding="utf-8")
        assert cache.load() is None, f"v{stale} cache must not load"


def test_additive_fields_stay_backward_compatible(tmp_path: Path) -> None:
    """A field added without bumping the floor must not discard a cache.

    Optional fields are read with a default, so a cache written before one
    existed still loads and shows previous values on launch — the missing field
    simply reads as None until the next live fetch.
    """
    import json

    path = tmp_path / "snap.json"
    cache = SnapshotCache(path)
    cache.save(_people(), Currency.CAD)
    data = json.loads(path.read_text(encoding="utf-8"))
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
