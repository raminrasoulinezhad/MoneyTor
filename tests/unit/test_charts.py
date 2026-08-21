# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Tests for Plotly chart HTML generation (Phase 7, no Qt)."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

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


def _rows() -> tuple[HoldingRow, ...]:
    return (
        _row("SHOP", "1200.50", "0.4", "Technology"),
        _row("VFV", "1800.25", "0.6", "Financials"),
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


# --------------------------------------------------------------------------- #
# Figure height and privacy
# --------------------------------------------------------------------------- #


def test_donut_height_is_the_requested_one() -> None:
    # Plotly bakes a pixel height into the document, so the panel must be able
    # to ask for one that fits its card; a fixed height overflowed it. Regression
    # for a height parameter that was accepted and then silently ignored.
    html = holdings_pie_html(_rows(), DARK, height=150)
    assert re.search(r"height:150px", html)


@pytest.mark.parametrize("height", [90, 170, 420, 900])
@pytest.mark.parametrize("builder", [holdings_pie_html, sector_pie_html, allocation_donut_html])
def test_every_builder_honours_the_requested_height(builder, height: int) -> None:
    match = re.search(r"height:(\d+)px", builder(_rows(), DARK, height=height))
    assert match is not None
    assert match.group(1) == str(height)


def test_donut_displays_no_dollar_amounts() -> None:
    """Private mode must not be undone by a chart label or tooltip.

    Slices are sized by market value, so the numbers reach Plotly — but nothing
    *rendered* may show them: slice text is the symbol alone and the hover
    template is label plus percentage.
    """
    rows = _rows()
    html = holdings_pie_html(rows, DARK)

    # Plotly escapes the <br>, so match the serialised form.
    assert '"hovertemplate":"%{label}' in html
    assert "%{percent}" in html  # hover shows the share...
    assert "%{value}" not in html  # ...never the amount
    assert '"textinfo":"label"' in html  # slice text is the symbol alone
    # No human-readable currency string is rendered anywhere.
    for row in rows:
        assert row.value.format() not in html
        assert row.value.format(with_currency=False) not in html
