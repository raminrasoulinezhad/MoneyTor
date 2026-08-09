# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Render a :class:`ReportModel` as a PDF using fpdf2.

Uses core fonts (Helvetica), so text is kept within latin-1 (no em dashes);
the middle dot in account labels is latin-1-safe.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from moneytor.formatting import format_asset_class, format_quantity

from .model import ReportModel, build_report

__all__ = ["build_report", "render_pdf", "write_pdf"]

_HEADERS = ("Symbol", "Name", "Sector", "Class", "Quantity", "Market Value", "Allocation")


def _latin1(text: str) -> str:
    """Make ``text`` safe for fpdf2's core (latin-1) fonts."""
    return text.encode("latin-1", "replace").decode("latin-1")


def _line(pdf: FPDF, text: str, height: float = 6.0) -> None:
    pdf.cell(0, height, text=text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def render_pdf(report: ReportModel) -> bytes:
    """Return PDF bytes for ``report``."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    _line(pdf, report.title, height=12)
    if report.as_of:
        pdf.set_font("Helvetica", "I", 10)
        _line(pdf, f"As of {report.as_of}")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, "Summary", height=8)
    pdf.set_font("Helvetica", "", 11)
    _line(pdf, f"Total value: {report.total_value.format()}")
    for currency, money in sorted(report.totals_by_currency.items()):
        _line(pdf, f"{currency.value} holdings + cash: {money.format()}")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, "By Person", height=8)
    for person in report.people:
        pdf.set_font("Helvetica", "B", 11)
        _line(pdf, f"{person.name}: {person.value.format()}")
        pdf.set_font("Helvetica", "", 10)
        for account in person.accounts:
            _line(pdf, f"   {account.label}: {account.value.format()}", height=5)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, "Holdings", height=8)
    pdf.set_font("Helvetica", "", 10)
    with pdf.table() as table:
        header = table.row()
        for label in _HEADERS:
            header.cell(label)
        for holding in report.holdings:
            quantity = format_quantity(holding.quantity)
            row = table.row()
            row.cell(holding.symbol)
            row.cell(_latin1(holding.name))
            row.cell(_latin1(holding.sector or "-"))
            row.cell(format_asset_class(holding.asset_class))
            row.cell(quantity)
            row.cell(holding.value.format())
            row.cell(f"{float(holding.allocation) * 100:.1f}%")

    return bytes(pdf.output())


def write_pdf(report: ReportModel, path: str | Path) -> None:
    """Render ``report`` to a PDF file at ``path``."""
    Path(path).write_bytes(render_pdf(report))
