"""Tests for the on-demand USD/CAD FX snapshot provider (no network)."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from moneytor.domain.enums import Currency
from moneytor.domain.money import Money
from moneytor.fx import FxError, SnapshotFxProvider, convert, fetch_usd_cad, usd_cad_table

CAD = Currency.CAD
USD = Currency.USD


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_usd_cad_parses_rate() -> None:
    client = _client(lambda r: httpx.Response(200, json={"rates": {"CAD": 1.394766}}))
    assert fetch_usd_cad(client) == Decimal("1.394766")


def test_fetch_usd_cad_raises_on_http_error() -> None:
    client = _client(lambda r: httpx.Response(503))
    with pytest.raises(FxError):
        fetch_usd_cad(client)


def test_fetch_usd_cad_raises_on_missing_field() -> None:
    client = _client(lambda r: httpx.Response(200, json={"rates": {}}))
    with pytest.raises(FxError):
        fetch_usd_cad(client)


def test_fetch_usd_cad_raises_on_implausible_rate() -> None:
    client = _client(lambda r: httpx.Response(200, json={"rates": {"CAD": 0}}))
    with pytest.raises(FxError):
        fetch_usd_cad(client)


def test_usd_cad_table_is_two_way() -> None:
    table = usd_cad_table(Decimal("1.25"))
    assert table[(USD, CAD)] == Decimal("1.25")
    assert table[(CAD, USD)] == Decimal(1) / Decimal("1.25")


def test_snapshot_uses_fallback_then_refreshes() -> None:
    provider = SnapshotFxProvider(Decimal("1.36"), fetcher=lambda: Decimal("1.40"))
    assert provider.get_rate(USD, CAD) == Decimal("1.36")
    provider.refresh()
    assert provider.get_rate(USD, CAD) == Decimal("1.40")
    assert provider.get_rate(USD, USD) == Decimal(1)


def test_snapshot_keeps_previous_rate_when_refresh_fails() -> None:
    def boom() -> Decimal:
        raise FxError("offline")

    provider = SnapshotFxProvider(Decimal("1.36"), fetcher=boom)
    provider.refresh()  # swallows the error
    assert provider.get_rate(USD, CAD) == Decimal("1.36")


def test_snapshot_drives_conversion() -> None:
    provider = SnapshotFxProvider(Decimal("1.30"))
    converted = convert(Money.of("100.00", USD), CAD, provider)
    assert converted == Money.of("130.00", CAD)
