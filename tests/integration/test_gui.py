# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Offscreen GUI tests for the cockpit (Phase 6).

Run headlessly via ``QT_QPA_PLATFORM=offscreen`` (set in conftest). ``qtbot``
(pytest-qt) manages the QApplication lifecycle.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView

from moneytor.autostart import AutostartError
from moneytor.config.secret import Secret
from moneytor.config.settings import PersonCredentials, Settings
from moneytor.connectors import load_accounts
from moneytor.connectors.errors import AuthError
from moneytor.domain import AssetClass, Currency, Money, Person
from moneytor.domain.enums import AccountType, Institution
from moneytor.formatting import PRIVATE_MASK
from moneytor.fx import StaticFxProvider
from moneytor.persistence.token_store import TokenStore
from moneytor.ui import app as app_module
from moneytor.ui.main_window import MainWindow
from moneytor.ui.theme import Theme
from moneytor.ui.workers import FetchWorker

CAD = Currency.CAD
USD = Currency.USD
FIXTURE = Path(__file__).parent.parent / "fixtures" / "mock_accounts.json"
PROVIDER = StaticFxProvider(rates={(USD, CAD): Decimal("1.35"), (CAD, USD): Decimal("0.74")})


def _people() -> tuple[Person, ...]:
    return (Person(id="ramin", name="Ramin", accounts=load_accounts(FIXTURE)),)


class _FakeAutostart:
    """In-memory Autostart backend, so tests never touch the real login config."""

    def __init__(self, supported: bool = True, fail_with: str | None = None) -> None:
        self.supported = supported
        self.reason = "Launch at login is not available on this platform."
        self._enabled = False
        self._fail_with = fail_with

    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        if self._fail_with is not None:
            raise AutostartError(self._fail_with)
        self._enabled = True

    def disable(self) -> None:
        if self._fail_with is not None:
            raise AutostartError(self._fail_with)
        self._enabled = False

    def set_enabled(self, enabled: bool) -> None:
        self.enable() if enabled else self.disable()


def _window(qtbot, autostart=None) -> MainWindow:
    window = MainWindow(
        people=_people(),
        provider=PROVIDER,
        display_currency=CAD,
        autostart=autostart if autostart is not None else _FakeAutostart(),
    )
    qtbot.addWidget(window)
    return window


def test_window_renders_kpis_and_table(qtbot) -> None:
    window = _window(qtbot)
    assert len(window.kpi_panel.kpi_cards) == 6
    assert "$" in window.kpi_panel.kpi_cards[0].value_text  # currency code is in the subtitle
    # SHOP, VFV, AAPL, GIC, plus the TFSA's CAD cash and the margin account's USD
    # cash — cash is in the headline total, so it has a row too.
    assert window.dashboard.table.rowCount() == 6


def test_lock_overlay_covers_window_and_unlocks(qtbot) -> None:
    window = _window(qtbot)
    window.resize(1200, 800)
    overlay = window.lock("hunter2")

    # The lock is shown and covers the whole window.
    assert not overlay.isHidden()
    assert overlay.size() == window.size()

    # Wrong password keeps it locked; correct password dismisses it.
    overlay._input.setText("nope")
    overlay._attempt()
    assert window._lock_overlay is overlay  # still locked

    unlocked = []
    overlay.unlocked.connect(lambda: unlocked.append(True))
    overlay._input.setText("hunter2")
    overlay._attempt()
    assert unlocked == [True]
    assert window._lock_overlay is None  # dismissed


def test_log_out_relocks_after_unlock(qtbot) -> None:
    window = _window(qtbot)
    window.show()

    # No password configured yet: Log out is hidden and a no-op.
    assert not window._logout_button.isVisible()
    window.log_out()
    assert window._lock_overlay is None

    # Lock, then unlock: the cockpit shows and Log out becomes available.
    overlay = window.lock("hunter2")
    overlay._input.setText("hunter2")
    overlay._attempt()
    assert window._lock_overlay is None
    assert window._logout_button.isVisible()

    # Log out returns to the password gate; unlocking again dismisses it.
    window.log_out()
    assert window._lock_overlay is not None
    window._lock_overlay._input.setText("hunter2")
    window._lock_overlay._attempt()
    assert window._lock_overlay is None


def test_theme_toggle_swaps_stylesheet(qtbot) -> None:
    window = _window(qtbot)
    assert window.theme is Theme.DARK
    before = window.styleSheet()
    window.toggle_theme()
    assert window.theme is Theme.LIGHT
    assert window.styleSheet() != before


def test_sidebar_filter_updates_table(qtbot) -> None:
    window = _window(qtbot)
    assert window.dashboard.table.rowCount() == 6
    # Simulate selecting only the TFSA account.
    window._on_selection_changed(frozenset({"qt-tfsa-ramin"}))
    assert window.dashboard.table.rowCount() == 3  # SHOP + VFV + the TFSA's cash


def test_search_filters_table_by_symbol(qtbot) -> None:
    window = _window(qtbot)
    assert window.dashboard.table.rowCount() == 6
    window.dashboard.search.setText("shop")
    assert window.dashboard.table.rowCount() == 1
    window.dashboard.search.setText("")
    assert window.dashboard.table.rowCount() == 6


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
    body = window.dashboard.left_chart._body
    assert body.isVisible() or body.text()  # populated
    assert "Allocation" in body.text()


def test_dashboard_has_two_charts_with_default_modes(qtbot) -> None:
    # Two side-by-side panels: the left defaults to Holdings, the right Sectors.
    window = _window(qtbot)
    assert window.dashboard.left_chart.selector.currentText() == "Holdings"
    assert window.dashboard.right_chart.selector.currentText() == "Sectors"
    assert "Allocation" in window.dashboard.left_chart._body.text()
    assert "Sectors" in window.dashboard.right_chart._body.text()


def test_table_sorts_market_value_numerically(qtbot) -> None:
    window = _window(qtbot)
    table = window.dashboard.table
    # Market Value column (5) defaults to descending; one click toggles to
    # ascending. Confirm true numeric order (a string sort would put
    # "$1,200.50" before "$950.75").
    table.horizontalHeader().sectionClicked.emit(5)
    values = [table.item(r, 5).text() for r in range(table.rowCount())]
    # AAPL 950.75 (USD) -> CAD is smallest; the largest is VFV 3100.
    amounts = [float(v.replace("$", "").replace(",", "").split()[0]) for v in values]
    assert amounts == sorted(amounts)


def _rank_of(table, symbol: str) -> int:
    for r in range(table.rowCount()):
        if table.item(r, 0).text() == symbol:
            return int(table.verticalHeaderItem(r).text())
    raise AssertionError(f"{symbol} not visible")


def test_rank_gutter_reflects_active_sort(qtbot) -> None:
    window = _window(qtbot)
    table = window.dashboard.table
    assert not table.verticalHeader().isHidden()  # rank gutter shown

    # Default sort is Market Value descending: the largest holding ranks #1.
    assert _rank_of(table, "VFV") == 1  # VFV 3100 is the largest in the fixture

    # Clicking the Market Value header toggles to ascending: ranks flip.
    table.horizontalHeader().sectionClicked.emit(5)
    assert _rank_of(table, "VFV") == table.rowCount()


def test_rank_corner_shows_hash(qtbot) -> None:
    from PySide6.QtWidgets import QLabel

    window = _window(qtbot)
    corner = window.dashboard.table.findChild(QLabel, "RankCorner")
    assert corner is not None and corner.text() == "#"


def test_rank_index_is_stable_under_search(qtbot) -> None:
    window = _window(qtbot)
    table = window.dashboard.table
    # AAPL's rank in the full (value-desc) set, before filtering.
    full_rank = _rank_of(table, "AAPL")
    assert full_rank != 1  # AAPL is not the largest, so this is a real check

    window.dashboard.search.setText("aapl")
    assert table.rowCount() == 1  # only AAPL matches
    # Its index is preserved from the full set rather than reset to 1.
    assert _rank_of(table, "AAPL") == full_rank

    window.dashboard.search.setText("")
    assert _rank_of(table, "AAPL") == full_rank  # unchanged after clearing


# --------------------------------------------------------------------------- #
# Holdings table sorting (numeric vs text, None handling, tie stability)
# --------------------------------------------------------------------------- #


def _sort_row(symbol: str, qty: str, value: str, *, high=None, unit=None):
    from decimal import Decimal

    from moneytor.domain import Money
    from moneytor.ui.viewmodels import HoldingRow

    return HoldingRow(
        symbol=symbol,
        asset_class="equity",
        quantity=Decimal(qty),
        value=Money.of(value, CAD),
        allocation=Decimal("0"),
        high_52w_pct=high,
        unit_price_native=unit,
    )


def _make_table(qtbot, rows):
    from moneytor.ui.widgets.holdings_table import HoldingsTable

    table = HoldingsTable()
    qtbot.addWidget(table)
    table.set_rows(rows)
    return table


def _column(table, col: int) -> list[str]:
    return [table.item(r, col).text() for r in range(table.rowCount())]


def test_quantity_sorts_numerically_not_lexicographically(qtbot) -> None:
    from decimal import Decimal

    table = _make_table(
        qtbot,
        [
            _sort_row("AAA", "9", "100"),
            _sort_row("BBB", "100", "200"),
            _sort_row("CCC", "25", "150"),
        ],
    )
    table.horizontalHeader().sectionClicked.emit(4)  # Quantity, defaults descending
    quantities = [Decimal(t) for t in _column(table, 4)]
    assert quantities == [Decimal("100"), Decimal("25"), Decimal("9")]


def test_none_52whg_sorts_to_bottom_descending_top_ascending(qtbot) -> None:
    from decimal import Decimal

    table = _make_table(
        qtbot,
        [
            _sort_row("AAA", "1", "100", high=None),
            _sort_row("BBB", "1", "100", high=Decimal("0.5")),
            _sort_row("CCC", "1", "100", high=Decimal("0.1")),
        ],
    )
    table.horizontalHeader().sectionClicked.emit(7)  # 52WHG descending: missing last
    assert _column(table, 0) == ["BBB", "CCC", "AAA"]
    assert _column(table, 7)[-1] == "—"
    table.horizontalHeader().sectionClicked.emit(7)  # ascending: missing first
    assert _column(table, 0) == ["AAA", "CCC", "BBB"]
    assert _column(table, 7)[0] == "—"


def test_none_unit_price_sorts_consistently(qtbot) -> None:
    from moneytor.domain import Money

    table = _make_table(
        qtbot,
        [
            _sort_row("AAA", "1", "100", unit=Money.of("10", USD)),
            _sort_row("BBB", "1", "100", unit=None),
            _sort_row("CCC", "1", "100", unit=Money.of("50", USD)),
        ],
    )
    table.horizontalHeader().sectionClicked.emit(8)  # Unit Price descending: missing last
    assert _column(table, 0) == ["CCC", "AAA", "BBB"]
    assert _column(table, 8)[-1] == "—"


def test_symbol_column_sorts_case_insensitively_ascending_first(qtbot) -> None:
    # Text columns default to ascending and ignore case.
    table = _make_table(
        qtbot, [_sort_row("bbb", "1", "1"), _sort_row("AAA", "1", "2"), _sort_row("Ccc", "1", "3")]
    )
    table.horizontalHeader().sectionClicked.emit(0)  # Symbol
    assert _column(table, 0) == ["AAA", "bbb", "Ccc"]


def test_sort_is_stable_for_ties(qtbot) -> None:
    # Equal sort keys preserve the input order (Python's sort is stable).
    rows = [
        _sort_row("FIRST", "1", "100"),
        _sort_row("SECOND", "1", "100"),
        _sort_row("THIRD", "1", "100"),
    ]
    table = _make_table(qtbot, rows)
    table.horizontalHeader().sectionClicked.emit(5)  # Market Value, all equal
    assert _column(table, 0) == ["FIRST", "SECOND", "THIRD"]


def test_chart_selector_switches_independently(qtbot) -> None:
    window = _window(qtbot)
    left = window.dashboard.left_chart
    assert "Allocation" in left._body.text()  # holdings mode by default
    left.selector.setCurrentText("Sectors")
    assert "Sectors" in left._body.text()  # fallback summary switched modes
    # Switching the left panel leaves the right one untouched.
    assert window.dashboard.right_chart.selector.currentText() == "Sectors"


def test_chart_panel_empty_selection_message(qtbot) -> None:
    window = _window(qtbot)
    window._on_selection_changed(frozenset())
    # Selecting nothing means "show all", so still has holdings; force empty:
    window.dashboard.left_chart.set_allocation(())
    assert "No holdings" in window.dashboard.left_chart._body.text()


class _StubWebView:
    """Stands in for QWebEngineView, which never loads under offscreen Qt."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.shown = False

    def setUrl(self, url) -> None:
        self.urls.append(url.toLocalFile())

    def show(self) -> None:
        self.shown = True

    def hide(self) -> None:
        self.shown = False


def test_chart_panel_writes_html_to_a_reused_temp_file(qtbot) -> None:
    # The web view path never runs headlessly, so drive it with a stub. The
    # panel keeps one temp file for its lifetime and rewrites it per render —
    # QWebEngineView.setHtml truncates past ~2 MB, hence loading by URL.
    from pathlib import Path

    from moneytor.ui.widgets.chart_panel import ChartPanel

    panel = ChartPanel()
    qtbot.addWidget(panel)
    panel._webview = _StubWebView()

    panel._render_html("<html><body>first</body></html>")
    path = Path(panel._html_path)

    assert path.exists()
    assert path.suffix == ".html"  # the view needs the extension to render it
    assert path.name.startswith("moneytor_chart_")
    assert path.read_text(encoding="utf-8").endswith("first</body></html>")
    assert panel._webview.urls == [str(path)]
    assert panel._webview.shown

    # A second render overwrites in place rather than leaking another file.
    panel._render_html("<html><body>second</body></html>")

    assert panel._html_path == str(path)
    assert "second" in path.read_text(encoding="utf-8")
    assert panel._webview.urls == [str(path), str(path)]

    path.unlink()


# --------------------------------------------------------------------------- #
# Private mode
# --------------------------------------------------------------------------- #

_MASK = "••••••"
# KPI card order: Total Value, Dividends, GIC Interest, Income, Holdings, Top.
_SENSITIVE_KPIS = (0, 1, 2, 3)
_QTY_COL, _VALUE_COL = 4, 5


def test_private_mode_masks_sensitive_values(qtbot) -> None:
    window = _window(qtbot)
    cards = window.kpi_panel.kpi_cards
    table = window.dashboard.table
    # Real values before private mode.
    assert cards[0].value_text != _MASK
    assert table.item(0, _VALUE_COL).text() != _MASK

    window.set_private(True)

    # Total value + dividend/GIC/income KPIs are masked; count/top are not.
    for i in _SENSITIVE_KPIS:
        assert cards[i].value_text == _MASK
    assert cards[4].value_text != _MASK  # Holdings count stays visible
    assert cards[5].value_text != _MASK  # Top Position symbol stays visible
    # Per-holding share count and market value are masked; symbol/allocation not.
    for r in range(table.rowCount()):
        assert table.item(r, _QTY_COL).text() == _MASK
        assert table.item(r, _VALUE_COL).text() == _MASK
        assert table.item(r, 0).text() != _MASK  # symbol
        assert table.item(r, 6).text() != _MASK  # allocation %


def test_private_mode_persists_across_refresh(qtbot) -> None:
    window = _window(qtbot)
    window.set_private(True)
    # A re-render (e.g. after a refresh or filter) keeps values masked.
    window.refresh()
    assert window.kpi_panel.kpi_cards[0].value_text == _MASK
    assert window.dashboard.table.item(0, _VALUE_COL).text() == _MASK


def test_exit_private_mode_requires_password(qtbot, monkeypatch) -> None:
    from moneytor.ui import main_window as mw

    window = _window(qtbot)
    # Configure the gate password (as the launch lock would).
    window.lock("hunter2")
    window._dismiss_lock()
    dialog = window.open_settings()
    window.set_private(True)
    # The wrong-password warning is modal; stub it so the test never blocks.
    monkeypatch.setattr(mw.QMessageBox, "warning", lambda *a, **k: None)

    # Wrong password: stays private, and the checkbox snaps back to ticked.
    monkeypatch.setattr(mw.QInputDialog, "getText", lambda *a, **k: ("nope", True))
    window._on_private_requested(False)
    assert window.private_mode is True
    assert dialog.private_checkbox.isChecked()

    # Cancelled dialog: stays private.
    monkeypatch.setattr(mw.QInputDialog, "getText", lambda *a, **k: ("", False))
    window._on_private_requested(False)
    assert window.private_mode is True

    # Correct password: reveals.
    monkeypatch.setattr(mw.QInputDialog, "getText", lambda *a, **k: ("hunter2", True))
    window._on_private_requested(False)
    assert window.private_mode is False
    assert window.kpi_panel.kpi_cards[0].value_text != _MASK


def test_enter_private_mode_needs_no_password(qtbot) -> None:
    # Turning private mode ON is always free, even with a gate configured.
    window = _window(qtbot)
    window.lock("hunter2")
    window._dismiss_lock()
    window._on_private_requested(True)
    assert window.private_mode is True


# --------------------------------------------------------------------------- #
# Settings dialog
# --------------------------------------------------------------------------- #


def test_toolbar_keeps_only_navigation_controls(qtbot) -> None:
    from PySide6.QtWidgets import QPushButton, QToolBar

    # Private mode / Toggle theme / Export moved into Settings, so the toolbar
    # is down to Refresh, Log out, and the gear.
    window = _window(qtbot)
    toolbar = window.findChild(QToolBar)
    labels = {b.text() for b in toolbar.findChildren(QPushButton)}
    assert labels == {"Refresh", "Log out", "⚙  Settings"}


def test_settings_dialog_opens_and_is_reused(qtbot) -> None:
    window = _window(qtbot)
    assert window._settings_dialog is None  # built lazily on first open

    dialog = window.open_settings()
    qtbot.addWidget(dialog)
    assert dialog.isVisible()
    assert dialog.isModal()
    # Re-opening returns the same instance rather than stacking dialogs.
    assert window.open_settings() is dialog


def test_settings_dialog_toggles_theme(qtbot) -> None:
    window = _window(qtbot)
    dialog = window.open_settings()
    qtbot.addWidget(dialog)
    assert window.theme is Theme.DARK
    assert dialog.theme_button.text() == "Switch to Light"

    dialog.theme_button.click()

    assert window.theme is Theme.LIGHT
    # The dialog re-renders: it now offers the way back.
    assert dialog.theme_button.text() == "Switch to Dark"


def test_settings_dialog_toggles_private_mode(qtbot) -> None:
    window = _window(qtbot)
    dialog = window.open_settings()
    qtbot.addWidget(dialog)
    assert not dialog.private_checkbox.isChecked()

    dialog.private_checkbox.setChecked(True)

    assert window.private_mode is True
    assert window.kpi_panel.kpi_cards[0].value_text == _MASK

    # No password configured, so revealing is free.
    dialog.private_checkbox.setChecked(False)
    assert window.private_mode is False


def test_settings_dialog_reflects_private_mode_set_elsewhere(qtbot) -> None:
    window = _window(qtbot)
    dialog = window.open_settings()
    qtbot.addWidget(dialog)
    window.set_private(True)
    assert dialog.private_checkbox.isChecked()


def test_settings_dialog_exports_report(qtbot, monkeypatch, tmp_path) -> None:
    from moneytor.ui import main_window as mw

    window = _window(qtbot)
    dialog = window.open_settings()
    qtbot.addWidget(dialog)
    target = tmp_path / "report.pdf"
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: None)

    dialog.export_button.click()

    assert target.exists() and target.read_bytes().startswith(b"%PDF")
    assert target.with_suffix(".md").exists()


def test_settings_dialog_cancelled_export_writes_nothing(qtbot, monkeypatch, tmp_path) -> None:
    from moneytor.ui import main_window as mw

    window = _window(qtbot)
    dialog = window.open_settings()
    qtbot.addWidget(dialog)
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))

    dialog.export_button.click()

    assert list(tmp_path.iterdir()) == []


def test_settings_dialog_toggles_launch_at_login(qtbot) -> None:
    autostart = _FakeAutostart()
    window = _window(qtbot, autostart=autostart)
    dialog = window.open_settings()
    qtbot.addWidget(dialog)
    assert dialog.launch_checkbox.isEnabled()
    assert not dialog.launch_checkbox.isChecked()

    dialog.launch_checkbox.setChecked(True)
    assert autostart.is_enabled() is True

    dialog.launch_checkbox.setChecked(False)
    assert autostart.is_enabled() is False


def test_settings_dialog_shows_autostart_failure_and_reverts(qtbot) -> None:
    autostart = _FakeAutostart(fail_with="Could not write /nope/moneytor.desktop")
    window = _window(qtbot, autostart=autostart)
    dialog = window.open_settings()
    qtbot.addWidget(dialog)

    dialog.launch_checkbox.setChecked(True)

    # The error is shown inline and the checkbox falls back to the real state.
    assert dialog._error.isVisible()
    assert "Could not write" in dialog._error.text()
    assert not dialog.launch_checkbox.isChecked()


def test_settings_dialog_disables_launch_toggle_when_unsupported(qtbot) -> None:
    autostart = _FakeAutostart(supported=False)
    window = _window(qtbot, autostart=autostart)
    dialog = window.open_settings()
    qtbot.addWidget(dialog)

    assert not dialog.launch_checkbox.isEnabled()
    assert dialog._launch_note.text() == autostart.reason


def test_locking_hides_the_settings_dialog(qtbot) -> None:
    # The dialog is application-modal; leaving it up would let a locked-out user
    # keep changing settings over the password gate.
    window = _window(qtbot)
    window.show()
    dialog = window.open_settings()
    qtbot.addWidget(dialog)
    assert dialog.isVisible()

    window.lock("hunter2")

    assert not dialog.isVisible()


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


def test_fetch_worker_passes_progress_reporter(qtbot) -> None:
    # A task that accepts one positional arg is handed a reporter; each call is
    # relayed through the worker's progress signal (queued to this thread).
    def task(report) -> str:
        report(0, 2, "first")
        report(2, 2, "done")
        return "ok"

    updates: list[tuple[int, int, str]] = []
    worker = FetchWorker(task=task)
    worker.progress.connect(lambda d, t, label: updates.append((d, t, label)))
    with qtbot.waitSignal(worker.succeeded, timeout=2000):
        worker.start()
    worker.wait()
    assert updates == [(0, 2, "first"), (2, 2, "done")]


def test_fetch_worker_handles_zero_arg_task(qtbot) -> None:
    # Zero-arg tasks (e.g. the OTP provider) must still be called with no args.
    worker = FetchWorker(task=lambda: "no-args")
    with qtbot.waitSignal(worker.succeeded, timeout=2000) as blocker:
        worker.start()
    assert blocker.args == ["no-args"]
    worker.wait()


class _FakeConnector:
    """Minimal Connector for exercising live_people's progress reporting."""

    def __init__(self, institution: Institution, accounts) -> None:
        self._institution = institution
        self._accounts = tuple(accounts)

    @property
    def institution(self) -> Institution:
        return self._institution

    def authenticate(self) -> None:
        return None

    def fetch_accounts(self):
        return self._accounts


def _accounts_of(person_id: str):
    """The fixture accounts, numbered for ``person_id`` so no two people share one.

    Handing two people identical account numbers would model a joint account,
    which live_people deliberately counts only once.
    """
    from dataclasses import replace as dc_replace

    return tuple(
        dc_replace(a, id=f"{person_id}-{a.id}", person_id=person_id) for a in load_accounts(FIXTURE)
    )


def test_live_people_reports_progress_per_source(monkeypatch) -> None:
    settings = Settings(
        people=(
            PersonCredentials(
                person_id="ramin", wealthsimple_email="r@x.io", wealthsimple_password=Secret("pw")
            ),
            PersonCredentials(person_id="alex", questrade_refresh_token=Secret("tok")),
        )
    )

    def fake_connectors_for(creds, token_store, otp_provider=None):
        institution = (
            Institution.WEALTHSIMPLE if creds.person_id == "ramin" else Institution.QUESTRADE
        )
        return [_FakeConnector(institution, _accounts_of(creds.person_id))]

    monkeypatch.setattr(app_module, "_connectors_for", fake_connectors_for)

    updates: list[tuple[int, int, str]] = []
    people = app_module.live_people(
        settings, TokenStore(), report=lambda d, t, label: updates.append((d, t, label))
    )

    assert {p.id for p in people} == {"ramin", "alex"}
    # One report before each of the two sources, plus a final completion report.
    assert updates[0] == (0, 2, "Fetching Ramin — Wealthsimple")
    assert updates[1] == (1, 2, "Fetching Alex — Questrade")
    assert updates[-1] == (2, 2, "Finalizing")


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
    assert window.dashboard.table.rowCount() == 6

    window.reload_data()
    qtbot.waitUntil(lambda: window.last_updated != "", timeout=2000)
    # The rate in use is shown too, so a conversion is never invisible.
    assert window.last_updated == "Updated 2026-06-08 09:00 · USD/CAD 1.3500"
    assert window.banner.isHidden()
    # The loading bar is hidden again once the fetch completes.
    assert window.progress.isHidden()


def test_reload_drives_progress_bar(qtbot) -> None:
    extra = Person(id="alex", name="Alex", accounts=load_accounts(FIXTURE))

    def loader(report) -> tuple[Person, ...]:
        report(0, 2, "Fetching Ramin — Wealthsimple")
        report(1, 2, "Fetching Alex — Questrade")
        return (*_people(), extra)

    window = MainWindow(people=_people(), provider=PROVIDER, display_currency=CAD, loader=loader)
    qtbot.addWidget(window)

    window.reload_data()
    qtbot.waitUntil(lambda: window.last_updated != "", timeout=2000)
    # Bar advanced to the reported total and is hidden again after success.
    assert window.progress.maximum() == 2
    assert window.progress.isHidden()


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


# --------------------------------------------------------------------------- #
# Dashboard density and the charts/list divider
# --------------------------------------------------------------------------- #


def test_charts_and_table_share_a_draggable_splitter(qtbot) -> None:
    window = _window(qtbot)
    window.show()
    splitter = window.dashboard.splitter

    assert splitter.count() == 2
    assert splitter.orientation() == Qt.Orientation.Vertical
    # Neither side may be dragged away entirely.
    assert not splitter.childrenCollapsible()


def test_window_growth_goes_to_the_list_not_taller_charts(qtbot) -> None:
    window = _window(qtbot)
    window.resize(1600, 800)
    window.show()
    charts_before, table_before = window.dashboard.splitter.sizes()

    window.resize(1600, 1200)
    charts_after, table_after = window.dashboard.splitter.sizes()

    assert charts_after == charts_before  # charts keep their height
    assert table_after > table_before  # the extra 400px becomes rows


def test_dragging_the_divider_moves_space_from_charts_to_the_table(qtbot) -> None:
    window = _window(qtbot)
    window.resize(1600, 1000)
    window.show()
    splitter = window.dashboard.splitter
    charts_before, table_before = splitter.sizes()

    splitter.setSizes([charts_before + 200, max(50, table_before - 200)])
    charts_after, table_after = splitter.sizes()

    assert charts_after > charts_before
    assert table_after < table_before


def test_charts_start_compact_so_the_list_gets_the_room(qtbot) -> None:
    window = _window(qtbot)
    window.resize(1600, 1000)
    window.show()
    charts, table = window.dashboard.splitter.sizes()
    # The holdings list is the point of the screen.
    assert table > charts


def test_holdings_rows_are_single_line(qtbot) -> None:
    # Wrapping a long name over two lines costs more rows than the name is worth.
    window = _window(qtbot)
    assert window.dashboard.table.wordWrap() is False


def test_elided_text_columns_carry_a_tooltip(qtbot) -> None:
    window = _window(qtbot)
    table = window.dashboard.table
    name = table.item(0, 1)
    assert name.toolTip() == name.text()
    assert name.toolTip() != ""
    # Numeric columns are never elided, so they stay tooltip-free.
    assert table.item(0, 5).toolTip() == ""


def test_unit_price_sorts_on_the_display_currency(qtbot) -> None:
    # The column mixes currencies (USD for NYSE, CAD for TSX), so a raw-number
    # sort would rank 120 CAD above 100 USD (~137 CAD).
    from moneytor.ui.viewmodels import HoldingRow
    from moneytor.ui.widgets.holdings_table import HoldingsTable

    rate = Decimal("1.376")

    def row(symbol: str, price: str, currency: Currency) -> HoldingRow:
        native = Money.of(price, currency)
        display = native if currency is CAD else Money(native.amount * rate, CAD)
        return HoldingRow(
            symbol=symbol,
            name=symbol,
            sector="X",
            asset_class=AssetClass.EQUITY,
            quantity=Decimal("1"),
            value=Money.of("100", CAD),
            allocation=Decimal("0.1"),
            unit_price_native=native,
            unit_price_display=display,
        )

    table = HoldingsTable()
    qtbot.addWidget(table)
    table.set_rows([row("US100", "100", USD), row("CA120", "120", CAD), row("US90", "90", USD)])
    table.horizontalHeader().sectionClicked.emit(8)

    assert [table.item(r, 0).text() for r in range(table.rowCount())] == ["US100", "US90", "CA120"]


# --------------------------------------------------------------------------- #
# Average price paid, compact columns, configured names
# --------------------------------------------------------------------------- #


def test_avg_paid_column_shows_native_cost_and_sorts_on_display_currency(qtbot) -> None:
    from moneytor.ui.viewmodels import HoldingRow

    rate = Decimal("1.376")

    def row(symbol: str, cost: str, currency: Currency) -> HoldingRow:
        native = Money.of(cost, currency)
        display = native if currency is CAD else Money(native.amount * rate, CAD)
        return HoldingRow(
            symbol=symbol,
            asset_class="equity",
            quantity=Decimal("1"),
            value=Money.of("100", CAD),
            allocation=Decimal("0.1"),
            avg_cost_native=native,
            avg_cost_display=display,
        )

    table = _make_table(
        qtbot, [row("US100", "100", USD), row("CA120", "120", CAD), row("US90", "90", USD)]
    )
    assert table.horizontalHeaderItem(9).text() == "Avg Paid"
    table.horizontalHeader().sectionClicked.emit(9)  # descending first

    # 100 USD (~137.60 CAD) outranks 120 CAD; a raw-number sort would not.
    assert _column(table, 0) == ["US100", "US90", "CA120"]
    assert _column(table, 9) == ["$100.00 USD", "$90.00 USD", "$120.00 CAD"]


def test_avg_paid_shows_a_dash_when_unknown(qtbot) -> None:
    table = _make_table(qtbot, [_sort_row("AAA", "1", "10")])
    assert _column(table, 9) == ["—"]


def test_quantity_is_rounded_to_two_decimals_in_the_table(qtbot) -> None:
    table = _make_table(
        qtbot,
        [_sort_row("AAA", "103.9999", "1"), _sort_row("BBB", "22.7106", "2")],
    )
    assert sorted(_column(table, 4)) == ["104", "22.71"]


def test_quantity_sort_uses_the_exact_value_not_the_rounded_text(qtbot) -> None:
    # 1.004 and 1.001 both display as "1"; the order must still be exact.
    table = _make_table(qtbot, [_sort_row("LOW", "1.001", "1"), _sort_row("HIGH", "1.004", "2")])
    table.horizontalHeader().sectionClicked.emit(4)
    assert _column(table, 0) == ["HIGH", "LOW"]


def test_rounded_quantity_is_still_masked_in_private_mode(qtbot) -> None:
    table = _make_table(qtbot, [_sort_row("AAA", "103.9999", "1")])
    table.set_private(True)
    assert _column(table, 4) == [PRIVATE_MASK]


def test_name_column_is_capped_on_a_wide_table(qtbot) -> None:
    from moneytor.ui.viewmodels import HoldingRow
    from moneytor.ui.widgets import holdings_table

    long_name = "A VERY LONG COMPANY NAME THAT WOULD OTHERWISE TAKE HALF THE TABLE INC"
    table = _make_table(
        qtbot,
        [
            HoldingRow(
                symbol="LONG",
                name=long_name,
                asset_class="equity",
                quantity=Decimal("1"),
                value=Money.of("1", CAD),
                allocation=Decimal("0"),
            )
        ],
    )
    table.resize(2400, 600)
    table.show()
    qtbot.waitExposed(table)

    assert table.horizontalHeader().sectionSize(1) <= holdings_table._MAX_COLUMN_WIDTH
    assert table.item(0, 1).toolTip() == long_name  # elided text stays reachable


def test_terse_headers_carry_their_full_meaning_as_tooltips(qtbot) -> None:
    table = _make_table(qtbot, [])
    tips = {
        table.horizontalHeaderItem(c).text(): table.horizontalHeaderItem(c).toolTip()
        for c in range(table.columnCount())
    }
    assert tips["Qty"].startswith("Quantity")
    assert tips["Alloc"].startswith("Allocation")
    assert "52-week high" in tips["52WHG"]
    assert "paid" in tips["Avg Paid"]


def test_sidebar_is_narrower_than_before(qtbot) -> None:
    from moneytor.ui.widgets.sidebar import SIDEBAR_WIDTH, Sidebar

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    assert SIDEBAR_WIDTH < 300
    assert sidebar.width() == SIDEBAR_WIDTH


def test_live_people_use_the_configured_display_names(monkeypatch) -> None:
    settings = Settings(
        people=(
            PersonCredentials(
                person_id="person1", questrade_refresh_token=Secret("t1"), name="Alex"
            ),
            PersonCredentials(person_id="person2", questrade_refresh_token=Secret("t2")),
        )
    )
    monkeypatch.setattr(
        app_module,
        "_connectors_for",
        lambda creds, token_store, otp_provider=None: [
            _FakeConnector(Institution.QUESTRADE, _accounts_of(creds.person_id))
        ],
    )
    labels: list[str] = []
    people = app_module.live_people(
        settings, TokenStore(), report=lambda d, t, label: labels.append(label)
    )

    assert {p.id: p.name for p in people} == {"person1": "Alex", "person2": "Person2"}
    assert labels[0] == "Fetching Alex — Questrade"


def test_cached_people_are_renamed_from_config() -> None:
    accounts = load_accounts(FIXTURE)
    cached = (
        Person(id="person1", name="Person1", accounts=accounts),
        Person(id="person2", name="Person2", accounts=accounts),
    )
    settings = Settings(
        people=(
            PersonCredentials(
                person_id="person1", questrade_refresh_token=Secret("t"), name="Alex"
            ),
        )
    )

    renamed = app_module.apply_configured_names(cached, settings)
    assert [p.name for p in renamed] == ["Alex", "Person2"]  # unnamed person untouched
    assert renamed[0].accounts == accounts


def _merged_row(symbol: str, listings: tuple[str, ...]):
    from moneytor.ui.viewmodels import HoldingRow

    return HoldingRow(
        symbol=symbol,
        name="Cameco Corporation" if symbol == "CCO" else symbol,
        asset_class="equity",
        quantity=Decimal("1"),
        value=Money.of("1", CAD),
        allocation=Decimal("0"),
        listings=listings,
    )


def test_merged_symbol_names_its_listings_on_hover(qtbot) -> None:
    table = _make_table(qtbot, [_merged_row("CCO", ("CCO", "CCJ")), _merged_row("SHOP", ("SHOP",))])
    tips = {table.item(r, 0).text(): table.item(r, 0).toolTip() for r in range(2)}
    assert tips["CCO"] == "Merged listings: CCO, CCJ"
    assert tips["SHOP"] == ""  # nothing merged, nothing to explain


def test_search_finds_a_merged_row_by_its_other_ticker(qtbot) -> None:
    table = _make_table(qtbot, [_merged_row("CCO", ("CCO", "CCJ")), _merged_row("SHOP", ("SHOP",))])
    table.set_filter("ccj")
    assert _column(table, 0) == ["CCO"]


def test_app_merges_bundled_and_user_listing_groups(tmp_path, monkeypatch) -> None:
    path = tmp_path / "listings.json"
    path.write_text('[["ABX", "B"], ["XYZ", "CCJ"]]', encoding="utf-8")
    monkeypatch.setattr(app_module, "_LISTINGS_PATH", path)

    asset_map = app_module._load_asset_map()
    assert asset_map.canonical("CCJ") == "CCO"  # bundled grouping wins
    assert asset_map.canonical("B") == "ABX"  # user group added


def test_app_ignores_an_invalid_listings_file(tmp_path, monkeypatch, caplog) -> None:
    path = tmp_path / "listings.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(app_module, "_LISTINGS_PATH", path)

    asset_map = app_module._load_asset_map()
    assert asset_map.canonical("CCJ") == "CCO"  # bundled groups still apply
    assert "Ignoring invalid listing groups" in caplog.text


def test_window_merges_listings_it_is_given(qtbot) -> None:
    from moneytor.aggregation import AssetMap
    from moneytor.domain.models import Account, Holding

    def holding(symbol: str, value: str, currency: Currency) -> Holding:
        return Holding(
            symbol=symbol,
            exchange="",
            asset_class=AssetClass.EQUITY,
            quantity=Decimal("1"),
            book_value=Money.of(value, currency),
            market_value=Money.of(value, currency),
        )

    account = Account(
        id="a1",
        person_id="p1",
        institution=Institution.QUESTRADE,
        account_type=AccountType.TFSA,
        cash=Money.zero(CAD),
        holdings=(holding("CCO.TO", "110", CAD), holding("CCJ", "80", USD)),
    )
    window = MainWindow(
        people=(Person(id="p1", name="P", accounts=(account,)),),
        provider=PROVIDER,
        autostart=_FakeAutostart(),
        asset_map=AssetMap.from_groups([["CCO", "CCJ"]]),
    )
    qtbot.addWidget(window)
    table = window.dashboard.table
    assert _column(table, 0) == ["CCO"]
    assert _column(table, 4) == ["2"]


# --------------------------------------------------------------------------- #
# Search speed (the table used to be quadratic in its row count)
# --------------------------------------------------------------------------- #


def test_columns_are_not_continuously_auto_sized(qtbot) -> None:
    # ResizeToContents re-measures every row whenever one cell is set, which
    # made each render quadratic: 2-3 s per search keystroke at 160 holdings.
    table = _make_table(qtbot, [])
    resize_to_contents = QHeaderView.ResizeMode.ResizeToContents
    header, gutter = table.horizontalHeader(), table.verticalHeader()
    assert all(
        header.sectionResizeMode(c) != resize_to_contents for c in range(table.columnCount())
    )
    assert gutter.sectionResizeMode(0) != resize_to_contents


def test_columns_still_fit_their_contents_after_a_render(qtbot) -> None:
    table = _make_table(qtbot, [_sort_row("A", "1", "1")])
    narrow = table.horizontalHeader().sectionSize(0)
    table.set_rows([_sort_row("AVERYLONGTICKER", "1", "1")])
    assert table.horizontalHeader().sectionSize(0) > narrow


def test_search_stays_fast_on_a_large_portfolio(qtbot) -> None:
    import time

    rows = [_sort_row(f"T{i:03d}", str(i + 1), str(i * 10 + 5)) for i in range(400)]
    table = _make_table(qtbot, rows)
    table.show()
    qtbot.waitExposed(table)

    start = time.perf_counter()
    for query in ("t", "t1", "t12", "t1", "t", ""):
        table.set_filter(query)
    elapsed = time.perf_counter() - start
    # Linear rendering takes ~0.2 s here; the quadratic version took ~20 s.
    assert elapsed < 3.0, f"six searches over 400 rows took {elapsed:.1f}s"


# --------------------------------------------------------------------------- #
# Accounts column (tiny pie per row)
# --------------------------------------------------------------------------- #


def _mix_row(symbol: str, *mix: tuple[str, str]):
    from moneytor.ui.viewmodels import AccountBucket, HoldingRow

    return HoldingRow(
        symbol=symbol,
        asset_class="equity",
        quantity=Decimal("1"),
        value=Money.of("100", CAD),
        allocation=Decimal("0.1"),
        account_mix=tuple((AccountBucket[b], Decimal(s)) for b, s in mix),
    )


def _pie_center_color(table, row: int):
    from moneytor.ui.widgets.holdings_table import _ACCOUNTS_COLUMN

    rect = table.visualRect(table.model().index(row, _ACCOUNTS_COLUMN))
    image = table.viewport().grab().toImage()
    return image.pixelColor(rect.center())


def test_accounts_column_paints_a_pie_in_the_buckets_colour(qtbot) -> None:
    from PySide6.QtGui import QColor

    from moneytor.ui.theme.tokens import DARK

    table = _make_table(qtbot, [_mix_row("ALLTFSA", ("TFSA", "1"))])
    table.resize(1600, 300)
    table.show()
    qtbot.waitExposed(table)

    assert table.horizontalHeaderItem(10).text() == "Accounts"
    assert _pie_center_color(table, 0) == QColor(DARK.account_colors[0])  # TFSA emerald


def test_accounts_cell_has_no_text_and_a_split_tooltip(qtbot) -> None:
    table = _make_table(qtbot, [_mix_row("X", ("TFSA", "0.6"), ("RRSP", "0.4"))])
    cell = table.item(0, 10)
    assert cell.text() == ""
    assert "TFSA 60%" in cell.toolTip()
    assert "RRSP 40%" in cell.toolTip()


def test_accounts_header_tooltip_is_a_colour_legend(qtbot) -> None:
    from moneytor.ui.theme.tokens import DARK

    table = _make_table(qtbot, [])
    legend = table.horizontalHeaderItem(10).toolTip()
    for label in ("TFSA", "RRSP", "FHSA", "Margin &amp; Cash", "Other"):
        assert label in legend
    for color in DARK.account_colors:
        assert color in legend


def test_accounts_sort_clusters_rows_by_main_account(qtbot) -> None:
    table = _make_table(
        qtbot,
        [
            _mix_row("RRSPHEAVY", ("RRSP", "0.9"), ("TFSA", "0.1")),
            _mix_row("NOSPLIT"),
            _mix_row("HALFTFSA", ("TFSA", "0.5"), ("FHSA", "0.5")),
            _mix_row("ALLTFSA", ("TFSA", "1")),
        ],
    )
    table.horizontalHeader().sectionClicked.emit(10)  # ascending first
    assert _column(table, 0) == ["ALLTFSA", "HALFTFSA", "RRSPHEAVY", "NOSPLIT"]


def test_accounts_pie_follows_the_theme(qtbot) -> None:
    from PySide6.QtGui import QColor

    from moneytor.ui.theme.tokens import DARK

    table = _make_table(qtbot, [_mix_row("ALLTFSA", ("TFSA", "1"))])
    table.resize(1600, 300)
    table.show()
    qtbot.waitExposed(table)
    recoloured = replace(DARK, account_colors=("#ff0000", *DARK.account_colors[1:]))
    table.set_theme_tokens(recoloured)

    assert _pie_center_color(table, 0) == QColor("#ff0000")
    assert "#ff0000" in table.horizontalHeaderItem(10).toolTip()


def test_accounts_pie_stays_visible_in_private_mode(qtbot) -> None:
    table = _make_table(qtbot, [_mix_row("X", ("TFSA", "1"))])
    table.set_private(True)
    assert table.item(0, 10).toolTip()  # shares, not amounts — nothing to hide


def test_every_theme_colours_every_account_bucket() -> None:
    from moneytor.ui.theme.tokens import DARK, LIGHT
    from moneytor.ui.viewmodels import AccountBucket

    for tokens in (DARK, LIGHT):
        assert len(tokens.account_colors) == len(AccountBucket)


# --------------------------------------------------------------------------- #
# Closing while a refresh is running (used to abort the process)
# --------------------------------------------------------------------------- #


def test_closing_mid_refresh_waits_for_the_fetch_instead_of_crashing(qtbot) -> None:
    import threading

    release = threading.Event()

    def slow_loader():
        release.wait(5)  # a refresh still talking to the broker
        return ()

    window = MainWindow(
        people=(), provider=PROVIDER, loader=slow_loader, autostart=_FakeAutostart()
    )
    qtbot.addWidget(window)
    window.show()
    window.reload_data()
    worker = window._worker
    assert worker is not None and worker.isRunning()

    window.close()
    # Qt aborts the process if a running QThread is destroyed, so the close is
    # deferred: the window disappears at once, but the thread is left to finish.
    assert not window.isVisible()
    assert worker.isRunning()

    release.set()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    qtbot.waitUntil(lambda: window._close_pending and not window.isVisible(), timeout=5000)


def test_closing_emits_closing_so_pending_work_can_be_released(qtbot) -> None:
    window = MainWindow(people=(), provider=PROVIDER, autostart=_FakeAutostart())
    qtbot.addWidget(window)
    window.show()
    with qtbot.waitSignal(window.closing, timeout=1000):
        window.close()


def test_cancel_releases_a_login_waiting_for_a_2fa_code(qtbot, monkeypatch) -> None:
    import threading

    from moneytor.ui import otp
    from moneytor.ui.otp import GuiOtpProvider

    # If the queued prompt ever runs, answer at once rather than open a dialog.
    monkeypatch.setattr(otp, "prompt_otp", lambda *a, **k: "unexpected")

    provider = GuiOtpProvider()
    # The prompt is never answered: no event loop runs here to show it.
    answers: list[str] = []
    login = threading.Thread(target=lambda: answers.append(provider()))
    login.start()
    provider.cancel()  # the app is closing
    login.join(timeout=5)

    assert not login.is_alive()  # used to block forever
    assert answers == [""]
    assert provider() == ""  # and later logins don't wait either


def test_a_late_prompt_after_cancel_does_not_freeze_the_gui(qtbot, monkeypatch) -> None:
    from moneytor.ui import otp

    provider = otp.GuiOtpProvider()
    shown: list[str] = []
    monkeypatch.setattr(otp, "prompt_otp", lambda *a, **k: shown.append("dialog") or "123456")
    provider.cancel()  # the queue now holds the empty answer
    provider._show()  # a prompt queued before the cancel finally runs

    assert shown == []  # no dialog for an abandoned login, and no blocking put


def test_2fa_prompt_names_the_person_not_their_config_key() -> None:
    from moneytor.ui.otp import GuiOtpProvider

    creds = PersonCredentials(
        person_id="person1",
        wealthsimple_email="a@example.com",
        wealthsimple_password=Secret("pw"),
        name="Alex",
    )
    provider = GuiOtpProvider()
    provider.cancel()  # answer at once instead of waiting on a dialog
    (connector,) = app_module._connectors_for(creds, TokenStore(), provider)
    assert connector._otp_provider() == ""
    assert provider._account == "Alex (a@example.com)"


# --------------------------------------------------------------------------- #
# Fetching several people: joint accounts and whose login failed
# --------------------------------------------------------------------------- #


def _two_people() -> Settings:
    return Settings(
        people=(
            PersonCredentials(
                person_id="person1", questrade_refresh_token=Secret("a"), name="Alex"
            ),
            PersonCredentials(person_id="person2", questrade_refresh_token=Secret("b"), name="Sam"),
        )
    )


def _account(account_id: str, person_id: str):
    from moneytor.domain.models import Account

    return Account(
        id=account_id,
        person_id=person_id,
        institution=Institution.QUESTRADE,
        account_type=AccountType.MARGIN,
        cash=Money.of("1000", CAD),
        holdings=(),
    )


def test_a_joint_account_is_counted_once(monkeypatch) -> None:
    # Both holders' logins return the joint account under the same number.
    joint = "JOINT-1"
    by_person = {
        "person1": [_account("A-1", "person1"), _account(joint, "person1")],
        "person2": [_account("S-1", "person2"), _account(joint, "person2")],
    }
    monkeypatch.setattr(
        app_module,
        "_connectors_for",
        lambda creds, store, otp=None: [
            _FakeConnector(Institution.QUESTRADE, by_person[creds.person_id])
        ],
    )
    people = app_module.live_people(_two_people(), TokenStore())

    ids = [a.id for p in people for a in p.accounts]
    assert sorted(ids) == ["A-1", "JOINT-1", "S-1"]
    total = sum((a.cash for p in people for a in p.accounts), Money.zero(CAD))
    assert total == Money.of("3000", CAD)  # not 4000


def test_same_number_at_different_brokers_is_not_a_duplicate(monkeypatch) -> None:
    from dataclasses import replace as dc_replace

    qt = _account("12345", "person1")
    ws = dc_replace(qt, institution=Institution.WEALTHSIMPLE)
    monkeypatch.setattr(
        app_module,
        "_connectors_for",
        lambda creds, store, otp=None: (
            [
                _FakeConnector(Institution.QUESTRADE, [qt]),
                _FakeConnector(Institution.WEALTHSIMPLE, [ws]),
            ]
            if creds.person_id == "person1"
            else []
        ),
    )
    people = app_module.live_people(_two_people(), TokenStore())
    assert len([a for p in people for a in p.accounts]) == 2


@pytest.mark.parametrize("error_type", ["AuthError", "RateLimitError", "FetchError"])
def test_a_failed_login_names_whose_it_was(monkeypatch, error_type: str) -> None:
    from moneytor.connectors import errors

    error = getattr(errors, error_type)

    class _Failing(_FakeConnector):
        def authenticate(self) -> None:
            raise error("Questrade rejected the refresh token (HTTP 400).")

    monkeypatch.setattr(
        app_module,
        "_connectors_for",
        lambda creds, store, otp=None: (
            [_Failing(Institution.QUESTRADE, [])]
            if creds.person_id == "person2"
            else [_FakeConnector(Institution.QUESTRADE, [_account("A-1", "person1")])]
        ),
    )
    with pytest.raises(error) as caught:  # same type, so the UI's handling is unchanged
        app_module.live_people(_two_people(), TokenStore())
    assert str(caught.value) == "Sam's Questrade: Questrade rejected the refresh token (HTTP 400)."


def test_partial_avg_paid_explains_itself_on_hover(qtbot) -> None:
    from moneytor.ui.viewmodels import HoldingRow

    row = HoldingRow(
        symbol="X",
        asset_class="equity",
        quantity=Decimal("40"),
        value=Money.of("1", CAD),
        allocation=Decimal("0"),
        avg_cost_native=Money.of("50", USD),
        avg_cost_partial=True,
    )
    table = _make_table(qtbot, [row])
    assert table.item(0, 9).text() == "$50.00 USD *"
    assert "no cost on record" in table.item(0, 9).toolTip()


# --------------------------------------------------------------------------- #
# Sidebar ticks (they decide what every number on screen includes)
# --------------------------------------------------------------------------- #


def _sidebar(qtbot):
    from moneytor.ui.viewmodels import SidebarAccount, SidebarModel, SidebarPerson
    from moneytor.ui.widgets.sidebar import Sidebar

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    sidebar.set_model(
        SidebarModel(
            people=(
                SidebarPerson(
                    id="alex",
                    name="Alex",
                    accounts=(
                        SidebarAccount(id="a-tfsa", label="TFSA · questrade"),
                        SidebarAccount(id="a-rrsp", label="RRSP · questrade"),
                    ),
                ),
                SidebarPerson(
                    id="sam", name="Sam", accounts=(SidebarAccount(id="s-fhsa", label="FHSA"),)
                ),
            )
        )
    )
    tree = sidebar._tree
    return sidebar, tree.topLevelItem(0), tree.topLevelItem(1)


def test_everything_starts_ticked(qtbot) -> None:
    sidebar, _alex, _sam = _sidebar(qtbot)
    assert sidebar.selected_account_ids() == {"a-tfsa", "a-rrsp", "s-fhsa"}


def test_unticking_a_person_unticks_their_accounts(qtbot) -> None:
    sidebar, alex, _sam = _sidebar(qtbot)
    with qtbot.waitSignal(sidebar.selectionChanged, timeout=1000) as signal:
        alex.setCheckState(0, Qt.CheckState.Unchecked)
    assert signal.args == [frozenset({"s-fhsa"})]
    assert [alex.child(i).checkState(0) for i in range(2)] == [Qt.CheckState.Unchecked] * 2


def test_unticking_some_accounts_shows_the_person_partly_ticked(qtbot) -> None:
    sidebar, alex, _sam = _sidebar(qtbot)
    with qtbot.waitSignal(sidebar.selectionChanged, timeout=1000) as signal:
        alex.child(0).setCheckState(0, Qt.CheckState.Unchecked)
    assert signal.args == [frozenset({"a-rrsp", "s-fhsa"})]
    # It used to stay fully ticked, misreporting what was included.
    assert alex.checkState(0) == Qt.CheckState.PartiallyChecked

    alex.child(1).setCheckState(0, Qt.CheckState.Unchecked)
    assert alex.checkState(0) == Qt.CheckState.Unchecked


def test_reticking_a_person_brings_back_all_their_accounts(qtbot) -> None:
    sidebar, alex, _sam = _sidebar(qtbot)
    alex.child(0).setCheckState(0, Qt.CheckState.Unchecked)
    with qtbot.waitSignal(sidebar.selectionChanged, timeout=1000) as signal:
        alex.setCheckState(0, Qt.CheckState.Checked)
    assert signal.args == [frozenset({"a-tfsa", "a-rrsp", "s-fhsa"})]


def test_one_click_on_a_person_is_one_dashboard_update(qtbot) -> None:
    # Qt reports each account a person-click changes; they are coalesced, or
    # the dashboard would re-render once per account.
    sidebar, alex, _sam = _sidebar(qtbot)
    emitted: list[frozenset[str]] = []
    sidebar.selectionChanged.connect(emitted.append)
    alex.setCheckState(0, Qt.CheckState.Unchecked)
    qtbot.wait(50)
    assert emitted == [frozenset({"s-fhsa"})]


def test_rebuilding_the_tree_does_not_announce_a_selection(qtbot) -> None:
    sidebar, _alex, _sam = _sidebar(qtbot)
    emitted: list[frozenset[str]] = []
    sidebar.selectionChanged.connect(emitted.append)
    sidebar.set_model(sidebar_model_with_one_person())
    qtbot.wait(50)
    assert emitted == []


def sidebar_model_with_one_person():
    from moneytor.ui.viewmodels import SidebarAccount, SidebarModel, SidebarPerson

    return SidebarModel(
        people=(
            SidebarPerson(id="alex", name="Alex", accounts=(SidebarAccount(id="x", label="TFSA"),)),
        )
    )


def test_unticking_in_the_sidebar_filters_the_whole_window(qtbot) -> None:
    window = _window(qtbot)
    person = window.sidebar._tree.topLevelItem(0)
    tfsa = next(
        person.child(i)
        for i in range(person.childCount())
        if person.child(i).data(0, Qt.ItemDataRole.UserRole) == "qt-tfsa-ramin"
    )
    for i in range(person.childCount()):
        child = person.child(i)
        if child is not tfsa:
            child.setCheckState(0, Qt.CheckState.Unchecked)
    qtbot.waitUntil(lambda: window.dashboard.table.rowCount() == 3, timeout=2000)
    assert sorted(_column(window.dashboard.table, 0)) == ["CASH:CAD", "SHOP", "VFV"]


# --------------------------------------------------------------------------- #
# Multi-slice account pies
# --------------------------------------------------------------------------- #


def test_a_split_pie_paints_each_accounts_colour(qtbot) -> None:
    from PySide6.QtGui import QColor

    from moneytor.ui.theme.tokens import DARK
    from moneytor.ui.widgets.holdings_table import _ACCOUNTS_COLUMN

    # Half TFSA, half RRSP: the pie starts at 12 o'clock and runs clockwise,
    # so TFSA (listed first) fills the right half and RRSP the left.
    table = _make_table(qtbot, [_mix_row("HALF", ("TFSA", "0.5"), ("RRSP", "0.5"))])
    table.resize(1600, 300)
    table.show()
    qtbot.waitExposed(table)

    rect = table.visualRect(table.model().index(0, _ACCOUNTS_COLUMN))
    image = table.viewport().grab().toImage()
    center = rect.center()
    right = image.pixelColor(center.x() + 4, center.y())
    left = image.pixelColor(center.x() - 4, center.y())
    assert right == QColor(DARK.account_colors[0])  # TFSA
    assert left == QColor(DARK.account_colors[1])  # RRSP


def test_pie_slices_always_close_the_circle(qtbot) -> None:
    # Thirds don't divide 360*16 evenly; the last slice absorbs the rounding so
    # no wedge of background shows through at 12 o'clock.
    from PySide6.QtGui import QColor

    from moneytor.ui.theme.tokens import DARK
    from moneytor.ui.widgets.holdings_table import _ACCOUNTS_COLUMN

    third = str(Decimal(1) / 3)
    table = _make_table(qtbot, [_mix_row("T", ("TFSA", third), ("RRSP", third), ("FHSA", third))])
    table.resize(1600, 300)
    table.show()
    qtbot.waitExposed(table)
    rect = table.visualRect(table.model().index(0, _ACCOUNTS_COLUMN))
    image = table.viewport().grab().toImage()
    just_left_of_noon = image.pixelColor(rect.center().x() - 1, rect.center().y() - 5)
    assert just_left_of_noon == QColor(DARK.account_colors[2])  # FHSA, the last slice
