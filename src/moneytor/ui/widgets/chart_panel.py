"""Chart panel — a card hosting the portfolio distribution donut chart.

The chart is one panel *inside* the application, not the whole window. It
renders a Plotly figure in a ``QWebEngineView`` when one is available. Under a
headless/offscreen platform (or if WebEngine is missing) it gracefully falls
back to a compact text summary, so the app and its tests run anywhere.
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
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
        self._html_path: str | None = None

    def set_allocation(self, rows: Sequence[HoldingRow], tokens: ThemeTokens = DARK) -> None:
        """Render the allocation donut for ``rows`` (or a fallback message)."""
        if not rows:
            self._show_text("No holdings for this selection.")
            return
        if self._ensure_webview():
            self._render_html(allocation_donut_html(rows, tokens))
        else:
            self._show_text(_summary(rows))

    def set_placeholder_text(self, text: str) -> None:
        """Force the text body (used for loading/empty states)."""
        self._show_text(text)

    # -- internals ---------------------------------------------------------- #

    def _render_html(self, html: str) -> None:
        """Load Plotly HTML via a temp file.

        ``QWebEngineView.setHtml`` silently fails for content over ~2 MB, and
        the inline-Plotly document is several MB, so we write it to a file and
        load it by URL instead (no size limit, works offline).
        """
        if self._html_path is None:
            handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - kept for the panel's lifetime
                mode="w", suffix=".html", prefix="moneytor_chart_", delete=False, encoding="utf-8"
            )
            handle.close()
            self._html_path = handle.name
        Path(self._html_path).write_text(html, encoding="utf-8")
        self._webview.setUrl(QUrl.fromLocalFile(self._html_path))
        self._webview.show()
        self._body.hide()

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
