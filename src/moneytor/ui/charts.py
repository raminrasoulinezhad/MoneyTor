"""Plotly chart generation for the dashboard.

Pure functions returning self-contained HTML (Plotly.js embedded inline so the
desktop app needs no network). Kept Qt-free for unit-testing.

Note: Plotly requires plain ``float`` inputs. Converting ``Decimal`` amounts to
``float`` here is safe because it is *display-only* — no financial arithmetic
happens on these values (CLAUDE.md's Decimal rule applies to calculations).
"""

from __future__ import annotations

from collections.abc import Sequence

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


def allocation_donut_html(rows: Sequence[HoldingRow], tokens: ThemeTokens) -> str:
    """Render a donut chart of portfolio allocation by symbol as full HTML."""
    labels = [row.symbol for row in rows]
    values = [float(row.value.amount) for row in rows]

    figure = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
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
