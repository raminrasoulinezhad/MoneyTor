"""Tests for the QSS theme (no Qt widgets needed)."""

from __future__ import annotations

import pytest

from moneytor.ui.theme import DARK, LIGHT, Theme, build_qss, stylesheet_for


@pytest.mark.parametrize("tokens", [DARK, LIGHT])
def test_inputs_are_styled_with_explicit_colors(tokens) -> None:
    qss = build_qss(tokens)
    # Inputs must set both background and text colour, or text is invisible.
    assert "QLineEdit" in qss
    assert "QComboBox QAbstractItemView" in qss
    assert tokens.text in qss
    assert tokens.surface_alt in qss


def test_stylesheet_for_each_theme_differs() -> None:
    assert stylesheet_for(Theme.DARK) != stylesheet_for(Theme.LIGHT)
