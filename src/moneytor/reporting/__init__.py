# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

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
