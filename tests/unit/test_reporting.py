# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Tests for the reporting layer (Phase 9)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from moneytor.aggregation import build_snapshot
from moneytor.connectors import load_accounts
from moneytor.domain import Currency, Person
from moneytor.fx import StaticFxProvider
from moneytor.reporting import build_report, render_markdown, render_pdf, write_pdf

CAD = Currency.CAD
USD = Currency.USD
FIXTURE = Path(__file__).parent.parent / "fixtures" / "mock_accounts.json"
PROVIDER = StaticFxProvider(rates={(USD, CAD): Decimal("1.35"), (CAD, USD): Decimal("0.74")})


def _report():
    people = (Person(id="ramin", name="Ramin", accounts=load_accounts(FIXTURE)),)
    snapshot = build_snapshot(people, CAD, PROVIDER, as_of="2026-06-08")
    return build_report(snapshot, PROVIDER)


# --------------------------------------------------------------------------- #
# Report model
# --------------------------------------------------------------------------- #


def test_report_model_totals_and_sorting() -> None:
    report = _report()
    assert report.display_currency is CAD
    assert report.as_of == "2026-06-08"
    # Holdings sorted by value descending.
    values = [h.value.amount for h in report.holdings]
    assert values == sorted(values, reverse=True)
    assert report.people[0].name == "Ramin"
    assert len(report.people[0].accounts) == 3


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #


def test_markdown_contains_key_sections() -> None:
    md = render_markdown(_report())
    assert md.startswith("# MoneyTor Portfolio Report")
    assert "*As of 2026-06-08*" in md
    assert "## Summary" in md
    assert "## By Person" in md
    assert "## Holdings" in md
    # Every holding symbol appears.
    for symbol in ("SHOP", "VFV", "AAPL"):
        assert symbol in md
    # Currency formatting present.
    assert "CAD" in md
    # Table header row.
    assert "| Symbol | Name | Sector | Class | Quantity | Market Value | Allocation |" in md


def test_markdown_is_deterministic() -> None:
    assert render_markdown(_report()) == render_markdown(_report())


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #


def test_pdf_renders_valid_document() -> None:
    pdf = render_pdf(_report())
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 1000


def test_write_pdf_to_disk(tmp_path: Path) -> None:
    out = tmp_path / "report.pdf"
    write_pdf(_report(), out)
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")


def test_empty_portfolio_reports_cleanly() -> None:
    snapshot = build_snapshot((), CAD, PROVIDER)
    report = build_report(snapshot, PROVIDER)
    md = render_markdown(report)
    assert "## Holdings" in md
    assert render_pdf(report).startswith(b"%PDF")


# --------------------------------------------------------------------------- #
# Reconciliation — the report's numbers must add up
# --------------------------------------------------------------------------- #


def test_report_total_reconciles_to_people_and_accounts() -> None:
    from moneytor.domain import Money

    report = _report()
    # Total equals the sum of person values...
    people_sum = sum((p.value for p in report.people), Money.zero(CAD))
    assert report.total_value == people_sum.quantize()
    # ...and each person's value equals the sum of their account values.
    for person in report.people:
        accounts_sum = sum((a.value for a in person.accounts), Money.zero(CAD))
        assert person.value == accounts_sum.quantize()


def test_report_total_matches_known_fixture_value() -> None:
    from moneytor.domain import Money

    # Same expectation as the aggregation suite: the fixture totals 9489.01 CAD.
    assert _report().total_value == Money.of("9489.01", CAD)


def test_report_allocations_sum_to_one() -> None:
    allocations = [h.allocation for h in _report().holdings]
    assert sum(allocations) == pytest.approx(Decimal("1"), abs=Decimal("0.001"))


# --------------------------------------------------------------------------- #
# Rendered content accuracy (not just structure)
# --------------------------------------------------------------------------- #


def test_markdown_shows_computed_total_and_holding_numbers() -> None:
    md = render_markdown(_report())
    assert "**Total value:** $9,489.01 CAD" in md
    # VFV: 25 shares, $3,100.00 CAD, the largest position.
    assert "| VFV |" in md
    assert "| 25 " in md
    assert "$3,100.00 CAD" in md


def test_pdf_handles_non_latin1_names_without_crashing() -> None:
    from dataclasses import replace

    from moneytor.connectors import load_accounts
    from moneytor.domain import Person

    accounts = load_accounts(FIXTURE)
    # Inject a holding name with non-latin-1 characters (em dash, euro sign).
    first = accounts[0]
    renamed = replace(first.holdings[0], name="Açao — Empresa €uro • Ω")
    patched = replace(first, holdings=(renamed, *first.holdings[1:]))
    people = (Person(id="ramin", name="Ramin", accounts=(patched, *accounts[1:])),)
    report = build_report(build_snapshot(people, CAD, PROVIDER), PROVIDER)
    pdf = render_pdf(report)
    assert pdf.startswith(b"%PDF")
    assert pdf.rstrip().endswith(b"%%EOF")
