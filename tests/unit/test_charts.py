# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Tests for Plotly chart HTML generation (Phase 7, no Qt)."""

from __future__ import annotations

from decimal import Decimal

from moneytor.domain import Currency, Money
from moneytor.ui.charts import allocation_donut_html, holdings_pie_html, sector_pie_html
from moneytor.ui.theme.tokens import DARK
from moneytor.ui.viewmodels import HoldingRow

CAD = Currency.CAD


def _row(symbol: str, value: str, allocation: str, sector: str = "") -> HoldingRow:
    return HoldingRow(
        symbol=symbol,
        asset_class="equity",
        quantity=Decimal("1"),
        value=Money.of(value, CAD),
        allocation=Decimal(allocation),
        sector=sector,
    )


def test_html_contains_plotly_and_every_symbol() -> None:
    rows = (_row("SHOP", "1200", "0.4"), _row("VFV", "1800", "0.6"))
    html = allocation_donut_html(rows, DARK)
    assert "plotly" in html.lower()
    assert "SHOP" in html
    assert "VFV" in html
    assert len(html) > 1000  # inlined plotly.js -> substantial


def test_single_holding_renders() -> None:
    html = allocation_donut_html((_row("AAPL", "999", "1.0"),), DARK)
    assert "AAPL" in html


def test_holdings_pie_groups_small_positions_into_others() -> None:
    rows = (
        _row("BIG", "9000", "0.90"),
        _row("MID", "900", "0.09"),
        _row("TINY", "50", "0.005"),  # below 1% -> Others
        _row("DUST", "50", "0.005"),  # below 1% -> Others
    )
    html = holdings_pie_html(rows, DARK)
    assert "BIG" in html and "MID" in html
    assert "Others" in html
    assert "TINY" not in html and "DUST" not in html


def test_sector_pie_aggregates_by_sector() -> None:
    rows = (
        _row("AAPL", "100", "0.5", sector="Information Technology"),
        _row("MSFT", "100", "0.3", sector="Information Technology"),
        _row("XOM", "50", "0.2", sector="Energy"),
        _row("MYSTERY", "10", "0.0"),  # no sector -> Unknown
    )
    html = sector_pie_html(rows, DARK)
    assert "Information Technology" in html
    assert "Energy" in html
    assert "Unknown" in html


def test_sector_pie_groups_small_sectors_into_other() -> None:
    rows = (
        _row("A", "9800", "0.0", sector="Information Technology"),
        _row("B", "100", "0.0", sector="Energy"),  # 1% -> Other
        _row("C", "100", "0.0", sector="Utilities"),  # 1% -> Other
    )
    html = sector_pie_html(rows, DARK)
    assert "Information Technology" in html
    assert "Other" in html
    assert "Energy" not in html and "Utilities" not in html
