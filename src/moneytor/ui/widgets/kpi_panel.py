# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""A vertical stack of KPI cards for the left column (above the account tree)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from PySide6.QtWidgets import QVBoxLayout, QWidget

from moneytor.formatting import PRIVATE_MASK
from moneytor.ui.viewmodels import KpiModel
from moneytor.ui.widgets.kpi_card import KpiCard


class KpiPanel(QWidget):
    """Renders the dashboard KPIs as a vertical column of cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("KpiPanel")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 8)
        self._layout.setSpacing(12)
        self._cards: list[KpiCard] = []
        self._kpis: tuple[KpiModel, ...] = ()
        self._private = False

    def set_kpis(self, kpis: Sequence[KpiModel]) -> None:
        """Store ``kpis`` and render them (masking sensitive cards if private)."""
        self._kpis = tuple(kpis)
        self._render()

    def set_private(self, private: bool) -> None:
        """Mask (or reveal) the monetary value on sensitive cards in place."""
        self._private = private
        self._render()

    def _render(self) -> None:
        """Render the stored KPIs, reusing cards when the count is unchanged."""
        models = [self._display(model) for model in self._kpis]
        if len(self._cards) == len(models):
            for card, model in zip(self._cards, models, strict=True):
                card.update_model(model)
            return
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._cards = []
        for model in models:
            card = KpiCard(model)
            self._cards.append(card)
            self._layout.addWidget(card)

    def _display(self, model: KpiModel) -> KpiModel:
        """The model as shown: a masked value for sensitive cards in private mode."""
        if self._private and model.sensitive:
            return replace(model, value=PRIVATE_MASK)
        return model

    @property
    def kpi_cards(self) -> list[KpiCard]:
        """The current KPI card widgets (used by tests)."""
        return self._cards
