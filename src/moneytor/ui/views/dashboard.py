# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""The main dashboard: two side-by-side chart panels and the holdings table."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from moneytor.ui.theme.tokens import DARK, ThemeTokens
from moneytor.ui.viewmodels import DashboardViewModel, HoldingRow
from moneytor.ui.widgets.chart_panel import ChartPanel
from moneytor.ui.widgets.holdings_table import HoldingsTable


class DashboardView(QWidget):
    """Two side-by-side chart panels and the holdings table (KPIs live left)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Root")

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(24, 24, 24, 24)
        self._outer.setSpacing(24)

        self._tokens: ThemeTokens = DARK
        self._last_rows: tuple[HoldingRow, ...] = ()

        # Two equal-width chart panels side by side, each with its own selector.
        # They default to complementary views (Holdings | Sectors) but either
        # can be switched to any available chart independently.
        charts_row = QHBoxLayout()
        charts_row.setSpacing(24)
        self.left_chart = ChartPanel(default_mode="Holdings")
        self.right_chart = ChartPanel(default_mode="Sectors")
        self._charts = (self.left_chart, self.right_chart)
        for chart in self._charts:
            charts_row.addWidget(chart, stretch=1)
        self._outer.addLayout(charts_row)

        self.search = QLineEdit()
        self.search.setObjectName("SearchBox")
        self.search.setPlaceholderText("Search holdings by symbol or name (Ctrl+F)…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        self._outer.addWidget(self.search)

        self.table = HoldingsTable()
        self._outer.addWidget(self.table, stretch=1)

    def set_theme_tokens(self, tokens: ThemeTokens) -> None:
        """Set the palette used for the charts and re-render them if data exists."""
        self._tokens = tokens
        if self._last_rows:
            for chart in self._charts:
                chart.set_allocation(self._last_rows, self._tokens)

    def set_view_model(self, view_model: DashboardViewModel) -> None:
        """Render the table rows and both charts for ``view_model``."""
        self._last_rows = view_model.rows
        # The table owns sorting/filtering and keeps the active search text, so
        # it re-renders honouring it. The charts always reflect the full set.
        self.table.set_rows(view_model.rows)
        for chart in self._charts:
            chart.set_allocation(view_model.rows, self._tokens)

    def set_private(self, private: bool) -> None:
        """Mask (or reveal) per-holding share counts and values in the table."""
        self.table.set_private(private)

    def focus_search(self) -> None:
        """Focus and select the search box (wired to Ctrl+F)."""
        self.search.setFocus()
        self.search.selectAll()

    def _apply_filter(self) -> None:
        """Filter the table by the search text (the table preserves ranks)."""
        self.table.set_filter(self.search.text())

    def set_loading(self, loading: bool) -> None:
        """Toggle a simple loading state on both chart panels."""
        if loading:
            for chart in self._charts:
                chart.set_placeholder_text("Loading portfolio…")
