# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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


# --------------------------------------------------------------------------- #
# Legibility: WCAG contrast ratios, checked rather than eyeballed
# --------------------------------------------------------------------------- #


def _luminance(hex_color: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("tokens", [DARK, LIGHT], ids=lambda t: t.name)
def test_text_is_readable_on_cards_and_tooltips(tokens) -> None:
    # WCAG AA for normal text. Tooltips use the card surface.
    assert _contrast(tokens.text, tokens.surface) >= 4.5
    assert _contrast(tokens.text_muted, tokens.surface) >= 4.5


@pytest.mark.parametrize("tokens", [DARK, LIGHT], ids=lambda t: t.name)
def test_account_slices_stand_out_from_every_row_colour(tokens) -> None:
    # WCAG non-text contrast (3:1) for the pies and their legend dots, on both
    # the plain and the zebra-striped row.
    for color in tokens.account_colors:
        for background in (tokens.surface, tokens.surface_alt):
            assert _contrast(color, background) >= 3, (tokens.name, color, background)


@pytest.mark.parametrize("tokens", [DARK, LIGHT], ids=lambda t: t.name)
def test_tooltips_are_themed(tokens) -> None:
    # Without a background, tooltips inherited the theme's text colour but kept
    # Qt's pale-yellow default: near-white on yellow in dark theme.
    qss = build_qss(tokens)
    block = qss[qss.index("QToolTip {") :].split("}", 1)[0]
    assert f"background: {tokens.surface}" in block
    assert f"color: {tokens.text}" in block
