"""The main dashboard: KPI card row, chart panel, and holdings table."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from moneytor.ui.theme.tokens import DARK, ThemeTokens
from moneytor.ui.viewmodels import DashboardViewModel, HoldingRow
from moneytor.ui.widgets.chart_panel import ChartPanel
from moneytor.ui.widgets.holdings_table import HoldingsTable


class DashboardView(QWidget):
    """The chart panel and the holdings table (KPIs live in the left column)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Root")

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(24, 24, 24, 24)
        self._outer.setSpacing(24)

        self._tokens: ThemeTokens = DARK
        self._last_rows: tuple[HoldingRow, ...] = ()

        self.chart_panel = ChartPanel()
        self._outer.addWidget(self.chart_panel)

        self.search = QLineEdit()
        self.search.setObjectName("SearchBox")
        self.search.setPlaceholderText("Search holdings by symbol or name (Ctrl+F)…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        self._outer.addWidget(self.search)

        self.table = HoldingsTable()
        self._outer.addWidget(self.table, stretch=1)

    def set_theme_tokens(self, tokens: ThemeTokens) -> None:
        """Set the palette used for the chart and re-render it if data exists."""
        self._tokens = tokens
        if self._last_rows:
            self.chart_panel.set_allocation(self._last_rows, self._tokens)

    def set_view_model(self, view_model: DashboardViewModel) -> None:
        """Render the table rows and the chart for ``view_model``."""
        self._last_rows = view_model.rows
        self._apply_filter()  # honours any active search text
        self.chart_panel.set_allocation(view_model.rows, self._tokens)

    def focus_search(self) -> None:
        """Focus and select the search box (wired to Ctrl+F)."""
        self.search.setFocus()
        self.search.selectAll()

    def _apply_filter(self) -> None:
        """Show only rows whose symbol or name matches the search text."""
        query = self.search.text().strip().lower()
        if not query:
            self.table.set_rows(self._last_rows)
            return
        self.table.set_rows(
            tuple(
                row
                for row in self._last_rows
                if query in row.symbol.lower() or query in row.name.lower()
            )
        )

    def set_loading(self, loading: bool) -> None:
        """Toggle a simple loading state on the chart panel."""
        if loading:
            self.chart_panel.set_placeholder_text("Loading portfolio…")
