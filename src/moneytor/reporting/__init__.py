# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Reporting layer — Markdown and PDF exports from a PortfolioSnapshot."""

from __future__ import annotations

from .markdown import render_markdown
from .model import (
    AccountLine,
    HoldingLine,
    PersonLine,
    ReportModel,
    build_report,
)
from .pdf import render_pdf, write_pdf

__all__ = [
    "AccountLine",
    "HoldingLine",
    "PersonLine",
    "ReportModel",
    "build_report",
    "render_markdown",
    "render_pdf",
    "write_pdf",
]
