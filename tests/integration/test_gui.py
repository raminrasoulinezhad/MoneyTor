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
    assert len(window.dashboard.kpi_cards) == 3
    assert "CAD" in window.dashboard.kpi_cards[0].value_text
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
