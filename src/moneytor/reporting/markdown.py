"""Render a :class:`ReportModel` as Markdown."""

from __future__ import annotations

from decimal import Decimal

from moneytor.formatting import format_quantity

from .model import ReportModel, build_report

__all__ = ["build_report", "render_markdown"]


def _pct(fraction: Decimal) -> str:
    return f"{float(fraction) * 100:.1f}%"


def render_markdown(report: ReportModel) -> str:
    """Return a Markdown document for ``report``."""
    lines: list[str] = [f"# {report.title}", ""]
    if report.as_of:
        lines.append(f"*As of {report.as_of}*")
        lines.append("")

    lines += [
        "## Summary",
        "",
        f"- **Total value:** {report.total_value.format()}",
    ]
    for currency, money in sorted(report.totals_by_currency.items()):
        lines.append(f"- **{currency.value} holdings + cash:** {money.format()}")
    lines.append("")

    lines += ["## By Person", ""]
    for person in report.people:
        lines.append(f"### {person.name} — {person.value.format()}")
        for account in person.accounts:
            lines.append(f"- {account.label}: {account.value.format()}")
        lines.append("")

    lines += [
        "## Holdings",
        "",
        "| Symbol | Name | Class | Quantity | Market Value | Allocation |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for holding in report.holdings:
        quantity = format_quantity(holding.quantity)
        lines.append(
            f"| {holding.symbol} | {holding.name} | {holding.asset_class.title()} | {quantity} "
            f"| {holding.value.format()} | {_pct(holding.allocation)} |"
        )
    lines.append("")
    return "\n".join(lines)
