# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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
from typing import TYPE_CHECKING

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

from moneytor.domain import Currency, Money
from moneytor.formatting import PRIVATE_MASK, format_asset_class, format_quantity
from moneytor.ui.theme.tokens import DARK, ThemeTokens
from moneytor.ui.viewmodels import AccountBucket, HoldingRow
from moneytor.ui.widgets.account_pie import (
    MIX_ROLE,
    AccountMixDelegate,
    Mix,
    legend_html,
    mix_html,
)

if TYPE_CHECKING:
    # typeshed's "anything sorted() accepts" protocol. It has no runtime module,
    # hence the guard; `from __future__ import annotations` keeps the reference
    # below a string so nothing is evaluated at import time.
    from _typeshed import SupportsRichComparison

# Headers are deliberately terse: every column but Name sizes to its contents,
# so the label is usually what sets the width. "Allocation" is twice as wide as
# any value under it. _HEADER_TOOLTIPS carries the full wording.
_HEADERS = (
    "Symbol",
    "Name",
    "Sector",
    "Class",
    "Qty",
    "Value",
    "Alloc",
    "52WHG",
    "Price",
    "Avg Paid",
    "Accounts",
)
_HEADER_TOOLTIPS = {
    4: "Quantity — shares held, rounded to 2 decimals",
    5: "Market value in the display currency",
    6: "Allocation — share of the total portfolio",
    7: "52-week high gap — how far below the 52-week high the price sits",
    8: "Current price per share, in the security's own currency",
    9: "Average price paid per share, in the security's own currency",
}
_PARTIAL_COST_TIP = (
    "Average of the shares whose cost your broker reported. Some shares have "
    "no cost on record (often ones transferred in from another broker)."
)
_VALUE_COLUMN = 5  # default sort column (descending)
_ACCOUNTS_COLUMN = 10
# Fractional share counts carry a dozen decimals from the broker; two is plenty.
_QUANTITY_PLACES = 2
# Widest any one column may grow. Long names and sectors elide, with the full
# text on hover.
_MAX_COLUMN_WIDTH = 300
# Text columns default to ascending when first sorted; numeric ones default to
# descending (largest first), which is what you usually want for money/size.
_TEXT_COLUMNS = frozenset({0, 1, 2, 3, _ACCOUNTS_COLUMN})
# Free-text columns wide enough to be cut off by the one-line row height.
_ELIDABLE_COLUMNS = frozenset({1, 2})
# Sort key for cells with no value, so they cluster at the bottom of a
# descending sort (and the top of an ascending one), matching the old behaviour.
_NO_VALUE = Decimal("-1")
_NO_MONEY = Money(_NO_VALUE, Currency.CAD)

# How to sort by each column: a HoldingRow -> comparable key. Text columns
# yield str and numeric ones Decimal; a column never mixes the two, so every
# key is comparable against the others produced for that same column.
_SORT_KEYS: dict[int, Callable[[HoldingRow], SupportsRichComparison]] = {
    0: lambda r: r.symbol.casefold(),
    1: lambda r: r.name.casefold(),
    2: lambda r: r.sector.casefold(),
    3: lambda r: format_asset_class(r.asset_class).casefold(),
    4: lambda r: r.quantity,
    5: lambda r: r.value.amount,
    6: lambda r: r.allocation,
    7: lambda r: r.high_52w_pct if r.high_52w_pct is not None else _NO_VALUE,
    # Sorted on the display-currency price, not the shown native one: the column
    # mixes currencies, so raw numbers are not comparable. Falls back to the
    # native price when no converted one was supplied.
    8: lambda r: (r.unit_price_display or r.unit_price_native or _NO_MONEY).amount,
    9: lambda r: (r.avg_cost_display or r.avg_cost_native or _NO_MONEY).amount,
    # Clusters rows by their main account group, in the fixed group order, and
    # within a group puts the most concentrated first: all-TFSA rows lead.
    _ACCOUNTS_COLUMN: lambda r: _mix_sort_key(r.account_mix),
}


_BUCKET_ORDER = tuple(AccountBucket)


def _mix_sort_key(mix: Mix) -> tuple[int, Decimal]:
    if not mix:
        return (len(_BUCKET_ORDER), Decimal("0"))  # unsplittable rows sort last
    bucket, share = mix[0]
    return (_BUCKET_ORDER.index(bucket), -share)


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

        self._tokens: ThemeTokens = DARK
        self._mix_delegate = AccountMixDelegate(self)
        self.setItemDelegateForColumn(_ACCOUNTS_COLUMN, self._mix_delegate)

        self._rows: tuple[HoldingRow, ...] = ()
        self._query: str = ""
        self._private = False
        self._sort_col: int = _VALUE_COLUMN
        self._sort_order: Qt.SortOrder = Qt.SortOrder.DescendingOrder

        # One line per holding: wrapping lets a long name grow a row to two or
        # three lines, which costs far more rows on screen than the full name is
        # worth. The Name column stretches, so it has room before eliding.
        self.setWordWrap(False)

        # The vertical header is a rank gutter: each row carries an explicit
        # 1-based index (its standing in the full sorted set).
        vheader = self.verticalHeader()
        vheader.setVisible(True)
        # Sized once per render (see _render), not continuously: in
        # ResizeToContents mode Qt re-measures every row on each cell added.
        vheader.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vheader.setHighlightSections(False)
        vheader.setDefaultAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._label_rank_corner()

        header = self.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        for col, tip in _HEADER_TOOLTIPS.items():
            item = self.horizontalHeaderItem(col)
            if item is not None:
                item.setToolTip(tip)
        self._set_legend_tooltip()
        header.setSortIndicator(self._sort_col, self._sort_order)
        header.sectionClicked.connect(self._on_section_clicked)
        # Every column sizes to its contents, capped. Name used to stretch into
        # all the spare width — ~500px on a maximized window — while the numbers
        # beside it were cramped; Qt's Stretch mode ignores a maximum, so it
        # sizes to content like the rest. Long names and sectors elide, with the
        # full text on hover. Spare width is left at the right edge.
        header.setMaximumSectionSize(_MAX_COLUMN_WIDTH)
        # Not ResizeToContents: that mode re-measures every row each time a
        # cell is set, which made a render quadratic in the row count — 2-3 s
        # per search keystroke on a 160-holding portfolio. _render sizes the
        # columns to their contents once, after filling.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

    # ----------------------------------------------------------------- API --- #

    def set_rows(self, rows: Sequence[HoldingRow]) -> None:
        """Replace the full backing set (re-rendered under the active sort/filter)."""
        self._rows = tuple(rows)
        self._render()

    def set_filter(self, query: str) -> None:
        """Show only rows matching ``query`` (by symbol or name); ranks unchanged."""
        self._query = query.strip().lower()
        self._render()

    def set_theme_tokens(self, tokens: ThemeTokens) -> None:
        """Recolour the Accounts pies and their legend for ``tokens``' theme."""
        self._tokens = tokens
        self._mix_delegate.set_tokens(tokens)
        self._set_legend_tooltip()
        self._render()

    def set_private(self, private: bool) -> None:
        """Mask (or reveal) each holding's share count and market value."""
        self._private = private
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
        # Every merged ticker counts, so searching "CCJ" finds Cameco's CCO row.
        tickers = row.listings or (row.symbol,)
        return any(self._query in t.lower() for t in tickers) or self._query in row.name.lower()

    def _render(self) -> None:
        # Rank over the full sorted set, then keep only matching rows — so a
        # filtered row still shows its standing in the whole portfolio.
        visible = [
            (rank, row) for rank, row in enumerate(self._ordered_rows(), 1) if self._matches(row)
        ]
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        self.setUpdatesEnabled(False)
        try:
            self._fill(visible, right)
        finally:
            self.resizeColumnsToContents()
            self.setUpdatesEnabled(True)

    def _fill(self, visible: list[tuple[int, HoldingRow]], right: Qt.AlignmentFlag) -> None:
        self.setRowCount(len(visible))
        for r, (rank, row) in enumerate(visible):
            self._set(r, 0, row.symbol)
            if len(row.listings) > 1:
                merged = self.item(r, 0)
                if merged is not None:
                    merged.setToolTip("Merged listings: " + ", ".join(row.listings))
            self._set(r, 1, row.name)
            self._set(r, 2, row.sector or "—")
            self._set(r, 3, format_asset_class(row.asset_class))
            # Per-holding share count and market value are hidden in private mode.
            quantity = format_quantity(row.quantity, places=_QUANTITY_PLACES)
            self._set(r, 4, PRIVATE_MASK if self._private else quantity, right)
            self._set(r, 5, PRIVATE_MASK if self._private else row.value.format(), right)
            self._set(r, 6, row.allocation_pct, right)
            self._set(r, 7, row.high_52w_text, right)
            self._set(r, 8, row.unit_price_text, right)
            self._set(r, 9, row.avg_cost_text, right)
            if row.avg_cost_partial:
                partial = self.item(r, 9)
                if partial is not None:
                    partial.setToolTip(_PARTIAL_COST_TIP)
            # Shares only, never amounts, so the pie stays visible in private mode.
            self._set(r, _ACCOUNTS_COLUMN, "")
            mix_item = self.item(r, _ACCOUNTS_COLUMN)
            if mix_item is not None:
                mix_item.setData(MIX_ROLE, row.account_mix)
                mix_item.setToolTip(
                    mix_html(row.account_mix, self._tokens) if row.account_mix else ""
                )
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
        # Rows are one line, so a long name or sector is elided. Carry the full
        # text as a tooltip rather than losing it.
        if col in _ELIDABLE_COLUMNS:
            item.setToolTip(text)
        self.setItem(row, col, item)

    def _set_legend_tooltip(self) -> None:
        item = self.horizontalHeaderItem(_ACCOUNTS_COLUMN)
        if item is not None:
            item.setToolTip(legend_html(self._tokens))

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
