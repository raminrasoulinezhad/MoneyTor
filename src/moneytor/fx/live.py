# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""A USD/CAD FX snapshot fetched on demand (no API key, daily-fresh).

We don't need a live streaming rate — just a *reasonably current* USD<->CAD
rate captured whenever portfolio data is fetched. :class:`SnapshotFxProvider`
holds one such snapshot and re-fetches it via :meth:`refresh`; the snapshot is
swapped atomically so the UI thread can read rates while a worker thread
refreshes. If the network is unavailable the previous (or fallback) rate is
kept, so conversion never breaks the app.

Source: https://open.er-api.com (free, keyless, updated daily).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation

import httpx

from moneytor.domain.enums import Currency

from .errors import FxError
from .provider import StaticFxProvider

_LOG = logging.getLogger(__name__)
_ENDPOINT = "https://open.er-api.com/v6/latest/USD"
_ONE = Decimal(1)

RateTable = Mapping[tuple[Currency, Currency], Decimal]


def fetch_usd_cad(client: httpx.Client | None = None) -> Decimal:
    """Fetch the current USD->CAD rate. Raises :class:`FxError` on any failure."""
    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        response = client.get(_ENDPOINT)
        response.raise_for_status()
        rate = response.json()["rates"]["CAD"]
        value = Decimal(str(rate))
    except (httpx.HTTPError, KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise FxError(f"Could not fetch USD->CAD rate: {exc}.") from exc
    finally:
        if owns_client:
            client.close()
    if value <= 0:
        raise FxError(f"Implausible USD->CAD rate: {value}.")
    return value


def usd_cad_table(usd_to_cad: Decimal) -> dict[tuple[Currency, Currency], Decimal]:
    """Build a two-way USD<->CAD rate table from a single USD->CAD rate."""
    return {
        (Currency.USD, Currency.CAD): usd_to_cad,
        (Currency.CAD, Currency.USD): _ONE / usd_to_cad,
    }


class SnapshotFxProvider:
    """An :class:`FxProvider` holding a refreshable USD<->CAD rate snapshot.

    Starts from ``fallback_usd_cad`` so conversion works offline/before the
    first fetch. :meth:`refresh` re-fetches and atomically replaces the snapshot.
    """

    def __init__(
        self, fallback_usd_cad: Decimal, fetcher: Callable[[], Decimal] = fetch_usd_cad
    ) -> None:
        self._fetcher = fetcher
        self._snapshot = StaticFxProvider(usd_cad_table(fallback_usd_cad))

    def get_rate(self, base: Currency, quote: Currency) -> Decimal:
        return self._snapshot.get_rate(base, quote)

    def refresh(self) -> None:
        """Re-fetch the rate; keep the previous snapshot if the fetch fails."""
        try:
            rate = self._fetcher()
        except FxError as exc:
            _LOG.warning("Keeping previous FX rate: %s", exc)
            return
        # Atomic swap: a single attribute rebind, safe against concurrent reads.
        self._snapshot = StaticFxProvider(usd_cad_table(rate))
        _LOG.info("Refreshed FX: USD->CAD = %s", rate)
