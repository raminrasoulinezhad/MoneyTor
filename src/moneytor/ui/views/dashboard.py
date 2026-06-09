"""The main dashboard: KPI card row, chart panel, and holdings table."""

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
from moneytor.ui.widgets.kpi_card import KpiCard


class DashboardView(QWidget):
    """Grid of KPI cards, the chart panel, and the holdings table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Root")

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(24, 24, 24, 24)
        self._outer.setSpacing(24)

        self._kpi_row = QHBoxLayout()
        self._kpi_row.setSpacing(16)
        self._kpi_cards: list[KpiCard] = []
        self._outer.addLayout(self._kpi_row)

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
        """Render a full view-model, rebuilding KPI cards and table rows."""
        self._rebuild_kpis(view_model)
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

    def _rebuild_kpis(self, view_model: DashboardViewModel) -> None:
        if len(self._kpi_cards) == len(view_model.kpis):
            for card, model in zip(self._kpi_cards, view_model.kpis, strict=True):
                card.update_model(model)
            return
        while self._kpi_row.count():
            item = self._kpi_row.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._kpi_cards = []
        for model in view_model.kpis:
            card = KpiCard(model)
            self._kpi_cards.append(card)
            self._kpi_row.addWidget(card)

    @property
    def kpi_cards(self) -> list[KpiCard]:
        """The current KPI card widgets (used by tests)."""
        return self._kpi_cards
