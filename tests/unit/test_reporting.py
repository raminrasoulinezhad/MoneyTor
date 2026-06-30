"""Tests for the reporting layer (Phase 9)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

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
