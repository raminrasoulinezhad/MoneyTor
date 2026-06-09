"""The holdings table: right-aligned currency columns, zebra striping."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from moneytor.formatting import format_quantity
from moneytor.ui.viewmodels import HoldingRow

_HEADERS = ("Symbol", "Name", "Class", "Quantity", "Market Value", "Allocation")


class HoldingsTable(QTableWidget):
    """A read-only table rendering :class:`HoldingRow` rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(_HEADERS), parent)
        self.setObjectName("HoldingsTable")
        self.setHorizontalHeaderLabels(_HEADERS)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        # The Name column absorbs spare width; the rest size to their content.
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(len(_HEADERS)):
            if col != 1:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    def set_rows(self, rows: Sequence[HoldingRow]) -> None:
        """Replace all rows with ``rows``."""
        self.setRowCount(len(rows))
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for r, row in enumerate(rows):
            self._set(r, 0, row.symbol)
            self._set(r, 1, row.name)
            self._set(r, 2, row.asset_class.title())
            self._set(r, 3, format_quantity(row.quantity), right)
            self._set(r, 4, row.value.format(), right)
            self._set(r, 5, row.allocation_pct, right)

    def _set(
        self,
        row: int,
        col: int,
        text: str,
        align: Qt.AlignmentFlag | None = None,
    ) -> None:
        item = QTableWidgetItem(text)
        if align is not None:
            item.setTextAlignment(align)
        self.setItem(row, col, item)
