"""Chart panel — a card that hosts the portfolio distribution chart.

In this phase it shows a styled placeholder. Phase 7 swaps the placeholder for
a Plotly figure rendered in a ``QWebEngineView`` *inside this same card*, so the
chart is one panel of the application rather than the whole window.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ChartPanel(QWidget):
    """Card container for the main dashboard chart."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        title = QLabel("Portfolio Distribution")
        title.setObjectName("PanelTitle")

        self._body = QLabel("Interactive chart arrives in Phase 7.")
        self._body.setObjectName("Placeholder")
        self._body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.setMinimumHeight(220)

        layout.addWidget(title)
        layout.addWidget(self._body, stretch=1)

    def set_placeholder_text(self, text: str) -> None:
        """Update the placeholder body text (used while loading / when empty)."""
        self._body.setText(text)
