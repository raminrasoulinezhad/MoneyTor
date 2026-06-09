"""The holdings table: right-aligned currency columns, zebra striping, sorting.

Sorting and the rank gutter are owned here in Python rather than delegated to
``QTableWidget``'s in-place item sort. That gives two properties the built-in
sort cannot:

* the **rank gutter** (vertical header) shows each holding's 1-based standing in
  the *full* sorted set, and
* **search** filters the rows as a view while each surviving row keeps the rank
  it had in the full set — re-sorting updates the ranks, searching never does.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
# Text columns default to ascending when first sorted; numeric ones default to
# descending (largest first), which is what you usually want for money/size.
_TEXT_COLUMNS = frozenset({0, 1, 2, 3})
# Sort key for cells with no value, so they cluster at the bottom of a
# descending sort (and the top of an ascending one), matching the old behaviour.
_NO_VALUE = Decimal("-1")

# How to sort by each column: a HoldingRow -> comparable key.
_SORT_KEYS: dict[int, Callable[[HoldingRow], object]] = {
    0: lambda r: r.symbol.casefold(),
    1: lambda r: r.name.casefold(),
    2: lambda r: r.sector.casefold(),
    3: lambda r: format_asset_class(r.asset_class).casefold(),
    4: lambda r: r.quantity,
    5: lambda r: r.value.amount,
    6: lambda r: r.allocation,
    7: lambda r: r.high_52w_pct if r.high_52w_pct is not None else _NO_VALUE,
}


class HoldingsTable(QTableWidget):
    """A read-only, click-to-sort table rendering :class:`HoldingRow` rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(_HEADERS), parent)
        self.setObjectName("HoldingsTable")
        self.setHorizontalHeaderLabels(_HEADERS)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # We sort in Python (see module docstring), so the built-in item sort is
        # off — but the header stays clickable to drive our own sort.
        self.setSortingEnabled(False)

        self._rows: tuple[HoldingRow, ...] = ()
        self._query: str = ""
        self._sort_col: int = _VALUE_COLUMN
        self._sort_order: Qt.SortOrder = Qt.SortOrder.DescendingOrder

        # The vertical header is a rank gutter: each row carries an explicit
        # 1-based index (its standing in the full sorted set).
        vheader = self.verticalHeader()
        vheader.setVisible(True)
        vheader.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        vheader.setHighlightSections(False)
        vheader.setDefaultAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._label_rank_corner()

        header = self.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self._sort_col, self._sort_order)
        header.sectionClicked.connect(self._on_section_clicked)
        # The Name column absorbs spare width; the rest size to their content.
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(len(_HEADERS)):
            if col != 1:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    # ----------------------------------------------------------------- API --- #

    def set_rows(self, rows: Sequence[HoldingRow]) -> None:
        """Replace the full backing set (re-rendered under the active sort/filter)."""
        self._rows = tuple(rows)
        self._render()

    def set_filter(self, query: str) -> None:
        """Show only rows matching ``query`` (by symbol or name); ranks unchanged."""
        self._query = query.strip().lower()
        self._render()

    # ------------------------------------------------------------- internals --- #

    def _on_section_clicked(self, col: int) -> None:
        """Toggle/redirect the sort on a header click, then re-rank and re-render."""
        if col == self._sort_col:
            self._sort_order = (
                Qt.SortOrder.AscendingOrder
                if self._sort_order == Qt.SortOrder.DescendingOrder
                else Qt.SortOrder.DescendingOrder
            )
        else:
            self._sort_col = col
            self._sort_order = (
                Qt.SortOrder.AscendingOrder
                if col in _TEXT_COLUMNS
                else Qt.SortOrder.DescendingOrder
            )
        self.horizontalHeader().setSortIndicator(self._sort_col, self._sort_order)
        self._render()

    def _ordered_rows(self) -> list[HoldingRow]:
        """The full set sorted by the active column/order (stable for ties)."""
        reverse = self._sort_order == Qt.SortOrder.DescendingOrder
        return sorted(self._rows, key=_SORT_KEYS[self._sort_col], reverse=reverse)

    def _matches(self, row: HoldingRow) -> bool:
        if not self._query:
            return True
        return self._query in row.symbol.lower() or self._query in row.name.lower()

    def _render(self) -> None:
        # Rank over the full sorted set, then keep only matching rows — so a
        # filtered row still shows its standing in the whole portfolio.
        visible = [
            (rank, row) for rank, row in enumerate(self._ordered_rows(), 1) if self._matches(row)
        ]
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        self.setRowCount(len(visible))
        for r, (rank, row) in enumerate(visible):
            self._set(r, 0, row.symbol)
            self._set(r, 1, row.name)
            self._set(r, 2, row.sector or "—")
            self._set(r, 3, format_asset_class(row.asset_class))
            self._set(r, 4, format_quantity(row.quantity), right)
            self._set(r, 5, row.value.format(), right)
            self._set(r, 6, row.allocation_pct, right)
            self._set(r, 7, row.high_52w_text, right)
            rank_item = QTableWidgetItem(str(rank))
            rank_item.setTextAlignment(right)
            self.setVerticalHeaderItem(r, rank_item)

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

    def _label_rank_corner(self) -> None:
        """Put ``#`` in the gutter's header corner (the top-left intersection).

        The corner is a ``QTableCornerButton`` whose painter ignores any text it
        is given, so we overlay a transparent label; its background is themed via
        ``QTableView QTableCornerButton::section`` to match the column headers.
        """
        corner = self.findChild(QAbstractButton)
        if corner is None:  # pragma: no cover - present in every Qt table view
            return
        layout = QHBoxLayout(corner)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("#", corner)
        label.setObjectName("RankCorner")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
