# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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


def test_usd_cad_table_inverse_keeps_full_precision() -> None:
    # The inverse is not rounded — full Decimal precision is preserved so the
    # round-trip stays as accurate as the source rate allows.
    table = usd_cad_table(Decimal("1.35"))
    assert table[(CAD, USD)] == Decimal(1) / Decimal("1.35")


def test_fetch_usd_cad_creates_and_closes_its_own_client(monkeypatch) -> None:
    from moneytor.fx import live

    closed = {"value": False}

    class _TrackingClient(httpx.Client):
        def close(self) -> None:
            closed["value"] = True
            super().close()

    def factory(*args, **kwargs) -> httpx.Client:
        handler = lambda r: httpx.Response(200, json={"rates": {"CAD": 1.41}})  # noqa: E731
        return _TrackingClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(live.httpx, "Client", factory)
    # Called with no client: it must build one and close it afterwards.
    assert fetch_usd_cad() == Decimal("1.41")
    assert closed["value"] is True


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
