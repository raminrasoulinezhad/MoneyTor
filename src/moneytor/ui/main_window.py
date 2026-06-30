# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""The application main window: sidebar + dashboard + theme toggle + refresh."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from moneytor import __version__
from moneytor.aggregation import build_snapshot
from moneytor.connectors.errors import ConnectorError
from moneytor.domain.enums import Currency
from moneytor.domain.models import Person
from moneytor.fx.provider import FxProvider
from moneytor.reporting import build_report, render_markdown, write_pdf
from moneytor.ui.theme import Theme, stylesheet_for, tokens_for
from moneytor.ui.viewmodels import SidebarModel, view_model_for
from moneytor.ui.views.dashboard import DashboardView
from moneytor.ui.widgets.banner import ErrorBanner
from moneytor.ui.widgets.kpi_panel import KpiPanel
from moneytor.ui.widgets.lock_screen import LockScreen
from moneytor.ui.widgets.progress_bar import FetchProgressBar
from moneytor.ui.widgets.sidebar import Sidebar
from moneytor.ui.workers import FetchWorker

PeopleLoader = Callable[[], tuple[Person, ...]]
Clock = Callable[[], str]


class MainWindow(QMainWindow):
    """Cockpit window. Renders people via the dashboard, filtered by sidebar."""

    def __init__(
        self,
        people: tuple[Person, ...],
        provider: FxProvider,
        display_currency: Currency = Currency.CAD,
        theme: Theme = Theme.DARK,
        loader: PeopleLoader | None = None,
        clock: Clock | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"MoneyTor v{__version__}")
        # Wide enough for the full 8-column holdings table (plus the 300px left
        # column) with no horizontal scroll, and tall enough for the chart plus
        # the top ~6 holdings on first launch.
        self.resize(1600, 1000)
        self.setMinimumSize(1280, 720)

        self._people = people
        self._provider = provider
        self._currency = display_currency
        self._theme = theme
        self._selected_ids: frozenset[str] | None = None
        self._loader = loader
        self._clock = clock or _default_clock
        self._worker: FetchWorker | None = None
        self._lock_overlay: LockScreen | None = None

        self._build_toolbar()

        central = QWidget()
        central.setObjectName("Root")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.banner = ErrorBanner()
        outer.addWidget(self.banner)

        # Full-width loading bar shown only while a refresh is in flight.
        self.progress = FetchProgressBar()
        outer.addWidget(self.progress)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Left column: KPI cards on top, then the family/account tree below.
        left_column = QWidget()
        left_column.setObjectName("LeftColumn")
        left_column.setFixedWidth(300)
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        self.kpi_panel = KpiPanel()
        self.sidebar = Sidebar()
        self.sidebar.selectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.kpi_panel)
        left_layout.addWidget(self.sidebar, stretch=1)

        self.dashboard = DashboardView()
        body.addWidget(left_column)
        body.addWidget(self.dashboard, stretch=1)
        outer.addLayout(body, stretch=1)
        self.setCentralWidget(central)

        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        find_shortcut.activated.connect(self.dashboard.focus_search)

        self.apply_theme(theme)
        self.set_people(people)

    # -- public API --------------------------------------------------------- #

    def lock(self, expected_password: str) -> LockScreen:
        """Cover the whole window with a password gate until it is unlocked.

        Returns the overlay so the caller can connect to its ``unlocked`` /
        ``cancelled`` signals (e.g. to defer loading data until after unlock).
        """
        overlay = LockScreen(expected_password, self)
        overlay.setGeometry(self.rect())
        overlay.unlocked.connect(self._dismiss_lock)
        overlay.show()
        overlay.raise_()
        self._lock_overlay = overlay
        return overlay

    def _dismiss_lock(self) -> None:
        if self._lock_overlay is not None:
            self._lock_overlay.hide()
            self._lock_overlay.deleteLater()
            self._lock_overlay = None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Keep the lock overlay covering the full window as it is resized.
        if self._lock_overlay is not None:
            self._lock_overlay.setGeometry(self.rect())

    def set_people(self, people: tuple[Person, ...]) -> None:
        """Replace the data set, rebuild the sidebar, and refresh the view."""
        self._people = people
        self._selected_ids = None
        self.sidebar.set_model(_sidebar_model(people, self._provider, self._currency))
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the view-model for the current selection (KPIs + dashboard)."""
        view_model = view_model_for(
            self._people, self._currency, self._provider, self._selected_ids
        )
        self.kpi_panel.set_kpis(view_model.kpis)
        self.dashboard.set_view_model(view_model)

    def reload_data(self) -> None:
        """Fetch fresh data off the UI thread via the injected loader."""
        if self._loader is None or (self._worker is not None and self._worker.isRunning()):
            return
        self.dashboard.set_loading(True)
        self.progress.begin()
        self._worker = FetchWorker(task=self._loader)
        self._worker.progress.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_reloaded)
        self._worker.failed.connect(self._on_reload_failed)
        self._worker.start()

    def export_report(self, pdf_path: str | Path) -> tuple[Path, Path]:
        """Write a PDF + Markdown portfolio report for the full portfolio.

        Returns the ``(markdown_path, pdf_path)`` written. The Markdown file is
        placed alongside the PDF with a ``.md`` suffix.
        """
        snapshot = build_snapshot(self._people, self._currency, self._provider, as_of=self._clock())
        report = build_report(snapshot, self._provider)
        pdf = Path(pdf_path)
        markdown = pdf.with_suffix(".md")
        write_pdf(report, pdf)
        markdown.write_text(render_markdown(report), encoding="utf-8")
        return markdown, pdf

    def apply_theme(self, theme: Theme) -> None:
        """Apply ``theme`` stylesheet and chart palette across the app."""
        self._theme = theme
        self.setStyleSheet(stylesheet_for(theme))
        self.dashboard.set_theme_tokens(tokens_for(theme))

    def toggle_theme(self) -> None:
        """Switch between dark and light themes."""
        self.apply_theme(Theme.LIGHT if self._theme is Theme.DARK else Theme.DARK)

    @property
    def theme(self) -> Theme:
        return self._theme

    @property
    def last_updated(self) -> str:
        return self._updated_label.text()

    # -- internals ---------------------------------------------------------- #

    def _build_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.reload_data)
        toolbar.addWidget(refresh_button)

        export_button = QPushButton("Export Report")
        export_button.clicked.connect(self._on_export)
        toolbar.addWidget(export_button)

        self._theme_button = QPushButton("Toggle theme")
        self._theme_button.clicked.connect(self.toggle_theme)
        toolbar.addWidget(self._theme_button)

        self._updated_label = QLabel("")
        self._updated_label.setObjectName("CardSubtitle")
        toolbar.addWidget(self._updated_label)
        self.addToolBar(toolbar)

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export portfolio report", "moneytor-report.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        try:
            markdown, pdf = self.export_report(path)
        except OSError as exc:
            self.banner.show_message(f"Could not export report: {exc}")
            return
        QMessageBox.information(self, "Report exported", f"Saved:\n{pdf}\n{markdown}")

    def _on_selection_changed(self, account_ids: frozenset[str]) -> None:
        # Empty selection means "show everything".
        self._selected_ids = account_ids or None
        self.refresh()

    def _on_progress(self, done: int, total: int, label: str) -> None:
        self.progress.set_progress(done, total, label)

    def _on_reloaded(self, people: object) -> None:
        self.progress.finish()
        self.banner.hide()
        if isinstance(people, tuple):
            self.set_people(people)
        self._updated_label.setText(f"Updated {self._clock()}")

    def _on_reload_failed(self, exc: object) -> None:
        self.progress.finish()
        detail = str(exc) if isinstance(exc, ConnectorError) else "Unexpected error."
        self.banner.show_message(f"Could not refresh data: {detail}")


def _sidebar_model(
    people: tuple[Person, ...], provider: FxProvider, currency: Currency
) -> SidebarModel:
    # The full (unfiltered) sidebar always lists every person/account.
    return view_model_for(people, currency, provider).sidebar


def _default_clock() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
