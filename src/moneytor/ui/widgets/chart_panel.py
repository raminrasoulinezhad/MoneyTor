"""Chart panel — a card hosting the portfolio distribution donut chart.

The chart is one panel *inside* the application, not the whole window. It
renders a Plotly figure in a ``QWebEngineView`` when one is available. Under a
headless/offscreen platform (or if WebEngine is missing) it gracefully falls
back to a compact text summary, so the app and its tests run anywhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from moneytor.ui.charts import allocation_donut_html
from moneytor.ui.theme.tokens import DARK, ThemeTokens
from moneytor.ui.viewmodels import HoldingRow


class ChartPanel(QWidget):
    """Card container for the main dashboard chart."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(8)

        title = QLabel("Portfolio Distribution")
        title.setObjectName("PanelTitle")

        self._body = QLabel("Loading…")
        self._body.setObjectName("Placeholder")
        self._body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.setWordWrap(True)
        self._body.setMinimumHeight(220)

        self._layout.addWidget(title)
        self._layout.addWidget(self._body, stretch=1)

        # Lazily created QWebEngineView; Any because the import is optional and
        # platform-dependent (justified deviation from the no-Any rule).
        self._webview: Any = None

    def set_allocation(self, rows: Sequence[HoldingRow], tokens: ThemeTokens = DARK) -> None:
        """Render the allocation donut for ``rows`` (or a fallback message)."""
        if not rows:
            self._show_text("No holdings for this selection.")
            return
        if self._ensure_webview():
            self._webview.setHtml(allocation_donut_html(rows, tokens))
            self._webview.show()
            self._body.hide()
        else:
            self._show_text(_summary(rows))

    def set_placeholder_text(self, text: str) -> None:
        """Force the text body (used for loading/empty states)."""
        self._show_text(text)

    # -- internals ---------------------------------------------------------- #

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


def _summary(rows: Sequence[HoldingRow]) -> str:
    """A compact textual allocation summary for headless/fallback rendering."""
    top = rows[: min(4, len(rows))]
    parts = [f"{row.symbol} {row.allocation_pct}" for row in top]
    return "Allocation — " + "  ·  ".join(parts)
