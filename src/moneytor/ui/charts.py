"""Plotly chart generation for the dashboard.

Pure functions returning self-contained HTML (Plotly.js embedded inline so the
desktop app needs no network). Kept Qt-free for unit-testing.

Note: Plotly requires plain ``float`` inputs. Converting ``Decimal`` amounts to
``float`` here is safe because it is *display-only* — no financial arithmetic
happens on these values (CLAUDE.md's Decimal rule applies to calculations).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import plotly.graph_objects as go

from moneytor.ui.theme.tokens import ThemeTokens
from moneytor.ui.viewmodels import HoldingRow

# A pleasant categorical palette anchored on the emerald accent.
_PALETTE = [
    "#10b981",
    "#3b82f6",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#14b8a6",
    "#ec4899",
    "#84cc16",
]

# Slices below these fractions of the total are grouped into a catch-all.
_HOLDINGS_THRESHOLD = Decimal("0.01")  # holdings pie: < 1% -> "Others"
_SECTOR_THRESHOLD = Decimal("0.02")  # sector pie: < 2% -> "Other"
_UNKNOWN_SECTOR = "Unknown"


def _donut_html(labels: Sequence[str], values: Sequence[Decimal], tokens: ThemeTokens) -> str:
    """Render a donut chart from parallel label/value sequences as full HTML."""
    figure = go.Figure(
        data=[
            go.Pie(
                labels=list(labels),
                values=[float(v) for v in values],
                hole=0.58,
                marker={"colors": _PALETTE, "line": {"color": tokens.surface, "width": 2}},
                textinfo="label+percent",
                textfont={"color": tokens.text},
                hovertemplate="%{label}<br>%{percent}<extra></extra>",
                sort=False,
            )
        ]
    )
    figure.update_layout(
        paper_bgcolor=tokens.surface,
        plot_bgcolor=tokens.surface,
        font={"color": tokens.text, "family": tokens.font_family},
        showlegend=False,
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
        height=300,
    )
    return figure.to_html(
        include_plotlyjs="inline",
        full_html=True,
        config={"displayModeBar": False, "responsive": True},
    )


def allocation_donut_html(rows: Sequence[HoldingRow], tokens: ThemeTokens) -> str:
    """Donut of allocation by symbol (every holding shown individually)."""
    return _donut_html([r.symbol for r in rows], [r.value.amount for r in rows], tokens)


def _grouped(
    totals: dict[str, Decimal], threshold: Decimal, other_label: str
) -> tuple[list[str], list[Decimal]]:
    """Order slices by value desc, rolling those under ``threshold`` into one."""
    grand = sum(totals.values(), Decimal("0"))
    cutoff = grand * threshold
    kept = sorted(
        ((k, v) for k, v in totals.items() if grand == 0 or v >= cutoff),
        key=lambda kv: kv[1],
        reverse=True,
    )
    other = sum((v for v in totals.values() if grand > 0 and v < cutoff), Decimal("0"))
    labels = [k for k, _ in kept]
    values = [v for _, v in kept]
    if other > 0:
        labels.append(other_label)
        values.append(other)
    return labels, values


def holdings_pie_html(rows: Sequence[HoldingRow], tokens: ThemeTokens) -> str:
    """Donut by symbol, grouping holdings under 1% of the portfolio into 'Others'."""
    totals: dict[str, Decimal] = {row.symbol: row.value.amount for row in rows}
    labels, values = _grouped(totals, _HOLDINGS_THRESHOLD, "Others")
    return _donut_html(labels, values, tokens)


def sector_pie_html(rows: Sequence[HoldingRow], tokens: ThemeTokens) -> str:
    """Donut by GICS sector ('Unknown' when missing), sectors under 2% as 'Other'."""
    totals: dict[str, Decimal] = {}
    for row in rows:
        key = row.sector or _UNKNOWN_SECTOR
        totals[key] = totals.get(key, Decimal("0")) + row.value.amount
    labels, values = _grouped(totals, _SECTOR_THRESHOLD, "Other")
    return _donut_html(labels, values, tokens)
