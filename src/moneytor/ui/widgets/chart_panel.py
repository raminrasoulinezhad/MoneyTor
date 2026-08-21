# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Chart panel — a card hosting the portfolio distribution donut chart.

The chart is one panel *inside* the application, not the whole window. It
renders a Plotly figure in a ``QWebEngineView`` when one is available. Under a
headless/offscreen platform (or if WebEngine is missing) it gracefully falls
back to a compact text summary, so the app and its tests run anywhere.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from moneytor.ui.charts import holdings_pie_html, sector_pie_html
from moneytor.ui.theme.tokens import DARK, ThemeTokens
from moneytor.ui.viewmodels import HoldingRow

_HOLDINGS = "Holdings"
_SECTORS = "Sectors"
# Floor for the plot area, so a fully-collapsed card still renders something.
_MIN_CHART_HEIGHT = 90
# Only re-render the (multi-MB) Plotly document once the height really moved.
_RERENDER_THRESHOLD = 24


class ChartPanel(QWidget):
    """Card container for the main dashboard chart (holdings or sector pie)."""

    def __init__(self, default_mode: str = _HOLDINGS, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 10, 14, 10)
        self._layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Portfolio Distribution")
        title.setObjectName("PanelTitle")
        self.selector = QComboBox()
        self.selector.setObjectName("ChartSelector")
        self.selector.addItems([_HOLDINGS, _SECTORS])
        # Set the starting mode before wiring the signal (no spurious rerender).
        if default_mode in (_HOLDINGS, _SECTORS):
            self.selector.setCurrentText(default_mode)
        self.selector.currentTextChanged.connect(self._rerender)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.selector)

        self._body = QLabel("Loading…")
        self._body.setObjectName("Placeholder")
        self._body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.setWordWrap(True)
        # No maximum: the dashboard splitter decides how tall the card is, so
        # dragging the divider is what enlarges the plot.
        self._body.setMinimumHeight(90)

        self._layout.addLayout(header)
        self._layout.addWidget(self._body, stretch=1)

        # Lazily created QWebEngineView; Any because the import is optional and
        # platform-dependent (justified deviation from the no-Any rule).
        self._webview: Any = None
        self._html_path: str | None = None
        self._rows: tuple[HoldingRow, ...] = ()
        self._tokens: ThemeTokens = DARK
        self._rendered_height = 0

    def set_allocation(self, rows: Sequence[HoldingRow], tokens: ThemeTokens = DARK) -> None:
        """Store rows and render the currently-selected chart (holdings/sectors)."""
        self._rows = tuple(rows)
        self._tokens = tokens
        self._rerender()

    def set_placeholder_text(self, text: str) -> None:
        """Force the text body (used for loading/empty states)."""
        self._show_text(text)

    # -- internals ---------------------------------------------------------- #

    def _rerender(self) -> None:
        """(Re)draw the chart for the current rows and selected mode."""
        rows = self._rows
        if not rows:
            self._show_text("No holdings for this selection.")
            return
        by_sector = self.selector.currentText() == _SECTORS
        if self._ensure_webview():
            height = self._chart_height()
            html = (
                sector_pie_html(rows, self._tokens, height)
                if by_sector
                else holdings_pie_html(rows, self._tokens, height)
            )
            self._rendered_height = height
            self._render_html(html)
        else:
            self._show_text(_summary(rows, by_sector))

    def _render_html(self, html: str) -> None:
        """Load Plotly HTML via a temp file.

        ``QWebEngineView.setHtml`` silently fails for content over ~2 MB, and
        the inline-Plotly document is several MB, so we write it to a file and
        load it by URL instead (no size limit, works offline).
        """
        if self._html_path is None:
            # mkstemp, not NamedTemporaryFile: we want a unique path we own for
            # the panel's lifetime, not a handle to hold open. The fd is closed
            # straight away — every write below goes through Path.
            handle, self._html_path = tempfile.mkstemp(suffix=".html", prefix="moneytor_chart_")
            os.close(handle)
        Path(self._html_path).write_text(html, encoding="utf-8")
        self._webview.setUrl(QUrl.fromLocalFile(self._html_path))
        self._webview.show()
        self._body.hide()

    def _chart_height(self) -> int:
        """Pixels available to the plot inside this card, after header/margins."""
        margins = self._layout.contentsMargins()
        chrome = margins.top() + margins.bottom() + self.selector.sizeHint().height()
        chrome += self._layout.spacing()
        return max(_MIN_CHART_HEIGHT, self.height() - chrome)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Plotly bakes a pixel height into the document, so a resized card needs
        # a re-render or the donut is clipped/floating. Re-rendering costs a
        # multi-megabyte HTML write, so only bother once the height has actually
        # moved a meaningful amount (e.g. after a splitter drag settles).
        if self._webview is None or not self._rows:
            return
        if abs(self._chart_height() - self._rendered_height) >= _RERENDER_THRESHOLD:
            self._rerender()

    def _show_text(self, text: str) -> None:
        if self._webview is not None:
            self._webview.hide()
        self._body.setText(text)
        self._body.show()

    def _ensure_webview(self) -> bool:
        """Create the web view on first use; False if unavailable/headless."""
        if self._webview is not None:
            return True
        if QApplication.instance() is None:
            return False
        if QGuiApplication.platformName() == "offscreen":
            return False
        try:
            # Lazy: heavy, optional, platform-dependent dependency.
            from PySide6.QtWebEngineWidgets import (  # pylint: disable=import-outside-toplevel
                QWebEngineView,
            )
        except ImportError:
            return False
        self._webview = QWebEngineView()
        self._layout.addWidget(self._webview, stretch=1)
        return True


def _summary(rows: Sequence[HoldingRow], by_sector: bool = False) -> str:
    """A compact textual allocation summary for headless/fallback rendering."""
    if by_sector:
        totals: dict[str, Decimal] = {}
        for row in rows:
            key = row.sector or "Unknown"
            totals[key] = totals.get(key, Decimal("0")) + row.value.amount
        ordered = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:4]
        parts = [name for name, _ in ordered]
        return "Sectors — " + "  ·  ".join(parts)
    top = rows[: min(4, len(rows))]
    parts = [f"{row.symbol} {row.allocation_pct}" for row in top]
    return "Allocation — " + "  ·  ".join(parts)
