# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Design tokens for the MoneyTor SaaS-style dashboard.

A single source of truth for colors, spacing, radii, and typography so dark and
light themes stay consistent. Values follow the CLAUDE.md visual standards:
deep slate/charcoal dark backgrounds (never pure black), emerald accent,
semantic green/red, generous spacing, rounded corners.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeTokens:
    """Resolved color/spacing/typography values for one theme."""

    name: str

    # Surfaces
    bg: str
    surface: str
    surface_alt: str  # zebra-stripe / hover row
    border: str

    # Text
    text: str
    text_muted: str

    # Accents / semantics
    accent: str
    accent_hover: str
    positive: str
    negative: str

    # Typography
    font_family: str = "Inter, 'Segoe UI', 'San Francisco', sans-serif"
    font_size_base: int = 14
    font_size_metric: int = 22
    font_size_label: int = 11

    # Layout
    spacing: int = 10
    spacing_lg: int = 14
    radius: int = 12
    radius_sm: int = 8


DARK = ThemeTokens(
    name="dark",
    bg="#0f172a",  # slate-900
    surface="#1e293b",  # slate-800
    surface_alt="#243449",
    border="#334155",  # slate-700
    text="#f8fafc",  # near-white
    text_muted="#94a3b8",  # slate-400
    accent="#10b981",  # emerald-500
    accent_hover="#34d399",  # emerald-400
    positive="#22c55e",
    negative="#f87171",
)

LIGHT = ThemeTokens(
    name="light",
    bg="#f1f5f9",  # slate-100
    surface="#ffffff",
    surface_alt="#f8fafc",
    border="#e2e8f0",  # slate-200
    text="#0f172a",
    text_muted="#64748b",  # slate-500
    accent="#059669",  # emerald-600
    accent_hover="#10b981",
    positive="#16a34a",
    negative="#dc2626",
)
