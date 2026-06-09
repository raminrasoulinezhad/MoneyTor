"""The holdings table: right-aligned currency columns, zebra striping, sorting."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from moneytor.formatting import format_asset_class, format_quantity
from moneytor.ui.viewmodels import HoldingRow

_HEADERS = (
    "Symbol",
    "Name",
    "Sector",
    "Class",
    "Quantity",
    "Market Value",
    "Allocation",
    "52WHG",
)
_VALUE_COLUMN = 5  # default sort column (descending)
# Sort key for cells with no value, so they cluster at the bottom.
_NO_VALUE = Decimal("-1")


class _NumericItem(QTableWidgetItem):
    """A cell that sorts by a numeric key rather than its formatted text."""

    def __init__(self, text: str, key: Decimal) -> None:
        super().__init__(text)
        self._key = key

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, _NumericItem):
            return self._key < other._key
        return super().__lt__(other)


class HoldingsTable(QTableWidget):
    """A read-only, click-to-sort table rendering :class:`HoldingRow` rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(_HEADERS), parent)
        self.setObjectName("HoldingsTable")
        self.setHorizontalHeaderLabels(_HEADERS)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setSortIndicator(_VALUE_COLUMN, Qt.SortOrder.DescendingOrder)
        # The Name column absorbs spare width; the rest size to their content.
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(len(_HEADERS)):
            if col != 1:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    def set_rows(self, rows: Sequence[HoldingRow]) -> None:
        """Replace all rows with ``rows`` (preserving the active sort)."""
        # Sorting must be off while populating, or rows reorder mid-insert.
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for r, row in enumerate(rows):
            self._set(r, 0, row.symbol)
            self._set(r, 1, row.name)
            self._set(r, 2, row.sector or "—")
            self._set(r, 3, format_asset_class(row.asset_class))
            self._set_num(r, 4, format_quantity(row.quantity), row.quantity, right)
            self._set_num(r, 5, row.value.format(), row.value.amount, right)
            self._set_num(r, 6, row.allocation_pct, row.allocation, right)
            high_key = row.high_52w_pct if row.high_52w_pct is not None else _NO_VALUE
            self._set_num(r, 7, row.high_52w_text, high_key, right)
        self.setSortingEnabled(True)

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

    def _set_num(
        self,
        row: int,
        col: int,
        text: str,
        key: Decimal,
        align: Qt.AlignmentFlag | None = None,
    ) -> None:
        item = _NumericItem(text, key)
        if align is not None:
            item.setTextAlignment(align)
        self.setItem(row, col, item)
