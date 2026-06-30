# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Theme system: design tokens, QSS, and dark/light switching."""

from __future__ import annotations

from enum import StrEnum

from .qss import build_qss
from .tokens import DARK, LIGHT, ThemeTokens


class Theme(StrEnum):
    """Selectable UI themes."""

    DARK = "dark"
    LIGHT = "light"


def tokens_for(theme: Theme) -> ThemeTokens:
    """Return the design tokens for ``theme``."""
    return DARK if theme is Theme.DARK else LIGHT


def stylesheet_for(theme: Theme) -> str:
    """Return the full QSS stylesheet for ``theme``."""
    return build_qss(tokens_for(theme))


__all__ = [
    "DARK",
    "LIGHT",
    "Theme",
    "ThemeTokens",
    "build_qss",
    "stylesheet_for",
    "tokens_for",
]
