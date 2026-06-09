"""Tests for the snapshot cache (Phase 10)."""

from __future__ import annotations

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
    assert len(person.accounts) == 2
    tfsa = person.accounts[0]
    assert tfsa.cash == Money.of("1500.00", Currency.CAD)
    assert tfsa.holdings[0].symbol == "SHOP"
    assert tfsa.holdings[0].name == "Shopify Inc."  # name survives the round-trip
    assert tfsa.holdings[0].market_value == Money.of("1200.50", Currency.CAD)


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


def test_corrupt_cache_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "snap.json"
    path.write_text("{ broken", encoding="utf-8")
    assert SnapshotCache(path).load() is None


def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    cache = SnapshotCache(tmp_path / "deep" / "snap.json")
    cache.save(_people(), Currency.CAD)
    assert (tmp_path / "deep" / "snap.json").exists()
