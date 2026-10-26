# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""A tiny pie per table cell: how a holding splits across account types.

The cell carries the split as data (:data:`MIX_ROLE`) and no text; this
delegate draws the pie over the normal cell background, so selection and zebra
striping still render as they do in every other column.
"""

from __future__ import annotations

from decimal import Decimal
from html import escape

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget

from moneytor.ui.theme.tokens import DARK, ThemeTokens
from moneytor.ui.viewmodels import AccountBucket

# Where a cell keeps its split: a tuple of (AccountBucket, fraction) pairs.
MIX_ROLE = Qt.ItemDataRole.UserRole + 1

_MAX_DIAMETER = 18  # px; the row is ~30px tall
_MARGIN = 6  # px kept clear above and below the pie
_FULL_CIRCLE = 360 * 16  # Qt measures arcs in 1/16ths of a degree
_TWELVE_O_CLOCK = 90 * 16

Mix = tuple[tuple[AccountBucket, Decimal], ...]


def bucket_colors(tokens: ThemeTokens) -> dict[AccountBucket, str]:
    """Each account group's slice colour for ``tokens``' theme."""
    return dict(zip(AccountBucket, tokens.account_colors, strict=True))


def legend_html(tokens: ThemeTokens) -> str:
    """A coloured key to every group, for the column header's tooltip."""
    colors = bucket_colors(tokens)
    keys = "<br>".join(
        f'<span style="color:{colors[b]}">●</span> {escape(b.value)}' for b in AccountBucket
    )
    return f"<b>Share of this holding in each account type</b><br>{keys}"


def mix_html(mix: Mix, tokens: ThemeTokens) -> str:
    """One holding's split, largest first, with matching colour dots."""
    colors = bucket_colors(tokens)
    return "<br>".join(
        f'<span style="color:{colors[b]}">●</span> {escape(b.value)} {share:.0%}'
        for b, share in mix
    )


class AccountMixDelegate(QStyledItemDelegate):
    """Paints a cell's :data:`MIX_ROLE` split as a small pie."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colors: dict[AccountBucket, QColor] = {}
        self._outline = QColor()
        self.set_tokens(DARK)

    def set_tokens(self, tokens: ThemeTokens) -> None:
        """Repaint with ``tokens``' slice colours (the owner triggers the repaint)."""
        self._colors = {b: QColor(c) for b, c in bucket_colors(tokens).items()}
        self._outline = QColor(tokens.surface)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        super().paint(painter, option, index)  # background, selection, focus
        mix = index.data(MIX_ROLE)
        if not mix:
            return
        rect = option.rect
        diameter = min(_MAX_DIAMETER, rect.height() - 2 * _MARGIN)
        if diameter <= 0:
            return
        pie = QRectF(0, 0, diameter, diameter)
        pie.moveCenter(QRectF(rect).center())

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # A hairline in the cell colour separates adjacent slices.
        painter.setPen(QPen(self._outline, 1))
        if len(mix) == 1:
            painter.setBrush(self._colors[mix[0][0]])
            painter.drawEllipse(pie)
        else:
            start = _TWELVE_O_CLOCK
            for i, (bucket, share) in enumerate(mix):
                # The last slice closes the circle, so rounding never leaves a
                # gap. float() is safe: these are pixels, not money.
                span = (
                    _TWELVE_O_CLOCK - _FULL_CIRCLE - start
                    if i == len(mix) - 1
                    else -round(float(share) * _FULL_CIRCLE)
                )
                painter.setBrush(self._colors[bucket])
                painter.drawPie(pie, start, span)
                start += span
        painter.restore()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        hint = super().sizeHint(option, index)
        return QSize(_MAX_DIAMETER + 2 * _MARGIN, hint.height())
