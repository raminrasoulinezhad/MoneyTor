"""The main dashboard: KPI card row, chart panel, and holdings table."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from moneytor.ui.viewmodels import DashboardViewModel
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

        self.chart_panel = ChartPanel()
        self._outer.addWidget(self.chart_panel)

        self.table = HoldingsTable()
        self._outer.addWidget(self.table, stretch=1)

    def set_view_model(self, view_model: DashboardViewModel) -> None:
        """Render a full view-model, rebuilding KPI cards and table rows."""
        self._rebuild_kpis(view_model)
        self.table.set_rows(view_model.rows)
        if not view_model.rows:
            self.chart_panel.set_placeholder_text("No holdings for this selection.")
        else:
            self.chart_panel.set_placeholder_text("Interactive chart arrives in Phase 7.")

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
