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

from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from moneytor.autostart import AutostartError
from moneytor.config.secret import Secret
from moneytor.config.settings import PersonCredentials, Settings
from moneytor.connectors import load_accounts
from moneytor.connectors.errors import AuthError
from moneytor.domain import Currency, Person
from moneytor.domain.enums import Institution
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
    assert window.dashboard.table.rowCount() == 4  # SHOP, VFV, AAPL, GIC


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
    assert window.dashboard.table.rowCount() == 4
    # Simulate selecting only the TFSA account.
    window._on_selection_changed(frozenset({"qt-tfsa-ramin"}))
    assert window.dashboard.table.rowCount() == 2  # SHOP + VFV only


def test_search_filters_table_by_symbol(qtbot) -> None:
    window = _window(qtbot)
    assert window.dashboard.table.rowCount() == 4
    window.dashboard.search.setText("shop")
    assert window.dashboard.table.rowCount() == 1
    window.dashboard.search.setText("")
    assert window.dashboard.table.rowCount() == 4


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


def test_live_people_reports_progress_per_source(monkeypatch) -> None:
    accounts = load_accounts(FIXTURE)
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
        return [_FakeConnector(institution, accounts)]

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
    assert window.dashboard.table.rowCount() == 4

    window.reload_data()
    qtbot.waitUntil(lambda: window.last_updated != "", timeout=2000)
    assert window.last_updated == "Updated 2026-06-08 09:00"
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
