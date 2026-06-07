"""Tests for Plotly chart HTML generation (Phase 7, no Qt)."""

from __future__ import annotations

from decimal import Decimal

from moneytor.domain import Currency, Money
from moneytor.ui.charts import allocation_donut_html
from moneytor.ui.theme.tokens import DARK
from moneytor.ui.viewmodels import HoldingRow

CAD = Currency.CAD


def _row(symbol: str, value: str, allocation: str) -> HoldingRow:
    return HoldingRow(
        symbol=symbol,
        asset_class="equity",
        quantity=Decimal("1"),
        value=Money.of(value, CAD),
        allocation=Decimal(allocation),
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
