# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""A KPI metric card with a title, large value, and helper subtitle."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from moneytor.ui.viewmodels import KpiModel

_TONE_OBJECT_NAME = {
    "neutral": "MetricValue",
    "positive": "MetricPositive",
    "negative": "MetricNegative",
}


class KpiCard(QWidget):
    """Displays one :class:`KpiModel` as a rounded, shadowed card."""

    def __init__(self, model: KpiModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("KpiCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(2)

        self._title = QLabel(model.title)
        self._title.setObjectName("KpiTitle")

        self._value = QLabel(model.value)
        self._value.setObjectName(_TONE_OBJECT_NAME.get(model.tone, "MetricValue"))

        self._subtitle = QLabel(model.subtitle)
        self._subtitle.setObjectName("CardSubtitle")

        layout.addWidget(self._title)
        layout.addWidget(self._value)
        layout.addWidget(self._subtitle)
        layout.addStretch(1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def update_model(self, model: KpiModel) -> None:
        """Refresh the card's text and tone in place."""
        self._title.setText(model.title)
        self._value.setText(model.value)
        self._value.setObjectName(_TONE_OBJECT_NAME.get(model.tone, "MetricValue"))
        self._subtitle.setText(model.subtitle)

    @property
    def value_text(self) -> str:
        """The currently displayed metric value (used by tests)."""
        return self._value.text()
