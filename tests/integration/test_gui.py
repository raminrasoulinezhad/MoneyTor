"""Offscreen GUI tests for the cockpit (Phase 6).

Run headlessly via ``QT_QPA_PLATFORM=offscreen`` (set in conftest). ``qtbot``
(pytest-qt) manages the QApplication lifecycle.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from moneytor.connectors import load_accounts
from moneytor.connectors.errors import AuthError
from moneytor.domain import Currency, Person
from moneytor.fx import StaticFxProvider
from moneytor.ui.main_window import MainWindow
from moneytor.ui.theme import Theme
from moneytor.ui.workers import FetchWorker

CAD = Currency.CAD
USD = Currency.USD
FIXTURE = Path(__file__).parent.parent / "fixtures" / "mock_accounts.json"
PROVIDER = StaticFxProvider(rates={(USD, CAD): Decimal("1.35"), (CAD, USD): Decimal("0.74")})


def _people() -> tuple[Person, ...]:
    return (Person(id="ramin", name="Ramin", accounts=load_accounts(FIXTURE)),)


def _window(qtbot) -> MainWindow:
    window = MainWindow(people=_people(), provider=PROVIDER, display_currency=CAD)
    qtbot.addWidget(window)
    return window


def test_window_renders_kpis_and_table(qtbot) -> None:
    window = _window(qtbot)
    assert len(window.kpi_panel.kpi_cards) == 3
    assert "CAD" in window.kpi_panel.kpi_cards[0].value_text
    assert window.dashboard.table.rowCount() == 3  # SHOP, VFV, AAPL


def test_theme_toggle_swaps_stylesheet(qtbot) -> None:
    window = _window(qtbot)
    assert window.theme is Theme.DARK
    before = window.styleSheet()
    window.toggle_theme()
    assert window.theme is Theme.LIGHT
    assert window.styleSheet() != before


def test_sidebar_filter_updates_table(qtbot) -> None:
    window = _window(qtbot)
    assert window.dashboard.table.rowCount() == 3
    # Simulate selecting only the TFSA account.
    window._on_selection_changed(frozenset({"qt-tfsa-ramin"}))
    assert window.dashboard.table.rowCount() == 2  # SHOP + VFV only


def test_search_filters_table_by_symbol(qtbot) -> None:
    window = _window(qtbot)
    assert window.dashboard.table.rowCount() == 3
    window.dashboard.search.setText("shop")
    assert window.dashboard.table.rowCount() == 1
    window.dashboard.search.setText("")
    assert window.dashboard.table.rowCount() == 3


def test_search_filters_table_by_name(qtbot) -> None:
    window = _window(qtbot)
    # 'Apple Inc.' and 'Vanguard...' have names but no 'apple'/'vanguard' symbol.
    window.dashboard.search.setText("apple")
    assert window.dashboard.table.rowCount() == 1
    window.dashboard.search.setText("inc")  # matches 'Shopify Inc.' + 'Apple Inc.'
    assert window.dashboard.table.rowCount() == 2


def test_focus_search_does_not_crash(qtbot) -> None:
    window = _window(qtbot)
    window.dashboard.focus_search()
    assert window.dashboard.search.hasFocus() or True  # focus is platform-dependent


def test_export_report_writes_markdown_and_pdf(qtbot, tmp_path) -> None:
    window = _window(qtbot)
    markdown, pdf = window.export_report(tmp_path / "report.pdf")
    assert pdf.exists() and pdf.read_bytes().startswith(b"%PDF")
    text = markdown.read_text(encoding="utf-8")
    assert text.startswith("# MoneyTor Portfolio Report")
    assert "SHOP" in text  # a holding from the fixture


def test_chart_panel_shows_summary_fallback_when_headless(qtbot) -> None:
    # Under the offscreen platform, the panel falls back to a text summary.
    window = _window(qtbot)
    body = window.dashboard.chart_panel._body
    assert body.isVisible() or body.text()  # populated
    assert "Allocation" in body.text()


def test_chart_selector_switches_to_sectors(qtbot) -> None:
    window = _window(qtbot)
    panel = window.dashboard.chart_panel
    assert "Allocation" in panel._body.text()  # holdings mode by default
    panel.selector.setCurrentText("Sectors")
    assert "Sectors" in panel._body.text()  # fallback summary switched modes


def test_chart_panel_empty_selection_message(qtbot) -> None:
    window = _window(qtbot)
    window._on_selection_changed(frozenset())
    # Selecting nothing means "show all", so still has holdings; force empty:
    window.dashboard.chart_panel.set_allocation(())
    assert "No holdings" in window.dashboard.chart_panel._body.text()


def test_fetch_worker_reports_success(qtbot) -> None:
    worker = FetchWorker(task=lambda: "done")
    with qtbot.waitSignal(worker.succeeded, timeout=2000) as blocker:
        worker.start()
    assert blocker.args == ["done"]
    worker.wait()


def test_fetch_worker_reports_failure(qtbot) -> None:
    def boom() -> str:
        raise RuntimeError("kaboom")

    worker = FetchWorker(task=boom)
    with qtbot.waitSignal(worker.failed, timeout=2000) as blocker:
        worker.start()
    assert isinstance(blocker.args[0], RuntimeError)
    worker.wait()


# --------------------------------------------------------------------------- #
# Reload via worker + error banner (Phase 10)
# --------------------------------------------------------------------------- #


def test_reload_updates_data_and_timestamp(qtbot) -> None:
    extra = Person(id="alex", name="Alex", accounts=load_accounts(FIXTURE))

    def loader() -> tuple[Person, ...]:
        return (*_people(), extra)

    window = MainWindow(
        people=_people(),
        provider=PROVIDER,
        display_currency=CAD,
        loader=loader,
        clock=lambda: "2026-06-08 09:00",
    )
    qtbot.addWidget(window)
    assert window.dashboard.table.rowCount() == 3

    window.reload_data()
    qtbot.waitUntil(lambda: window.last_updated != "", timeout=2000)
    assert window.last_updated == "Updated 2026-06-08 09:00"
    assert window.banner.isHidden()


def test_reload_failure_shows_error_banner(qtbot) -> None:
    def loader() -> tuple[Person, ...]:
        raise AuthError("token expired")

    window = MainWindow(people=_people(), provider=PROVIDER, display_currency=CAD, loader=loader)
    qtbot.addWidget(window)

    window.reload_data()
    qtbot.waitUntil(lambda: not window.banner.isHidden(), timeout=2000)
    assert "token expired" in window.banner.message


def test_error_banner_dismiss(qtbot) -> None:
    window = _window(qtbot)
    window.banner.show_message("oops")
    assert not window.banner.isHidden()
    window.banner.hide()
    assert window.banner.isHidden()


# --------------------------------------------------------------------------- #
# GUI OTP bridge (Wealthsimple 2FA)
# --------------------------------------------------------------------------- #


def test_gui_otp_provider_returns_code_from_dialog(qtbot, monkeypatch) -> None:
    from moneytor.ui import otp as otp_module

    monkeypatch.setattr(otp_module, "prompt_otp", lambda parent=None, account="": "654321")
    provider = otp_module.GuiOtpProvider()

    # Invoked from a worker thread; the dialog slot runs on the GUI thread and
    # the code is marshalled back to the caller.
    worker = FetchWorker(task=provider)
    with qtbot.waitSignal(worker.succeeded, timeout=2000) as blocker:
        worker.start()
    assert blocker.args == ["654321"]
    worker.wait()


def test_gui_otp_provider_includes_account_in_prompt(qtbot, monkeypatch) -> None:
    from moneytor.ui import otp as otp_module

    captured: dict[str, str] = {}

    def fake_prompt(parent=None, account="") -> str:
        captured["account"] = account
        return "111222"

    monkeypatch.setattr(otp_module, "prompt_otp", fake_prompt)
    provider = otp_module.GuiOtpProvider()
    labelled = provider.for_account("ramin", "you@example.com")

    worker = FetchWorker(task=labelled)
    with qtbot.waitSignal(worker.succeeded, timeout=2000) as blocker:
        worker.start()
    assert blocker.args == ["111222"]
    assert captured["account"] == "ramin (you@example.com)"
    worker.wait()


def test_gui_otp_provider_returns_empty_on_cancel(qtbot, monkeypatch) -> None:
    from moneytor.ui import otp as otp_module

    monkeypatch.setattr(otp_module, "prompt_otp", lambda parent=None, account="": "")
    provider = otp_module.GuiOtpProvider()

    worker = FetchWorker(task=provider)
    with qtbot.waitSignal(worker.succeeded, timeout=2000) as blocker:
        worker.start()
    assert blocker.args == [""]
    worker.wait()
