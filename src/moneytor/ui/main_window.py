# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""The application main window: sidebar + dashboard + settings + refresh."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from moneytor import __version__
from moneytor.aggregation import build_snapshot
from moneytor.autostart import Autostart, AutostartError, autostart_for
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
from moneytor.ui.widgets.settings_dialog import SettingsDialog
from moneytor.ui.widgets.sidebar import Sidebar
from moneytor.ui.workers import FetchWorker

PeopleLoader = Callable[[], tuple[Person, ...]]
Clock = Callable[[], str]

_THEME_NAMES = {Theme.DARK: "Dark", Theme.LIGHT: "Light"}
_LAUNCH_NOTE = "MoneyTor will start automatically the next time you sign in to this computer."


class MainWindow(QMainWindow):
    """Cockpit window. Renders people via the dashboard, filtered by sidebar."""

    # The cockpit composes a dozen collaborating widgets plus the data, theme,
    # lock and autostart state they are driven from; splitting that across
    # smaller objects would only move the wiring somewhere less obvious.
    # pylint: disable=too-many-instance-attributes

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        people: tuple[Person, ...],
        provider: FxProvider,
        display_currency: Currency = Currency.CAD,
        theme: Theme = Theme.DARK,
        loader: PeopleLoader | None = None,
        clock: Clock | None = None,
        autostart: Autostart | None = None,
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
        # Set the first time the window is locked; enables the Log out button.
        self._expected_password: str | None = None
        self._private = False
        # Backend for the "open at login" toggle; injectable so tests never
        # touch the real user session configuration.
        self._autostart = autostart if autostart is not None else autostart_for()
        self._settings_dialog: SettingsDialog | None = None

        self._build_toolbar()
        self._build_body()

        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        find_shortcut.activated.connect(self.dashboard.focus_search)

        self.apply_theme(theme)
        self.set_people(people)

    def _build_body(self) -> None:
        """Assemble the central widget: banner, progress bar, then the columns."""
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

    # -- public API --------------------------------------------------------- #

    def lock(self, expected_password: str) -> LockScreen:
        """Cover the whole window with a password gate until it is unlocked.

        Returns the overlay so the caller can connect to its ``unlocked`` /
        ``cancelled`` signals (e.g. to defer loading data until after unlock).
        Remembers the password so the user can re-lock later via Log out.
        """
        self._expected_password = expected_password
        self._logout_button.setVisible(True)
        # The settings dialog is application-modal and would stay usable on top
        # of the overlay, so locking must dismiss it.
        if self._settings_dialog is not None:
            self._settings_dialog.hide()
        overlay = LockScreen(expected_password, self)
        overlay.setGeometry(self.rect())
        overlay.unlocked.connect(self._dismiss_lock)
        overlay.show()
        overlay.raise_()
        self._lock_overlay = overlay
        return overlay

    def log_out(self) -> None:
        """Re-lock the window, returning to the password gate.

        No-op when no password is configured (the gate was never shown). The
        opaque overlay hides the loaded portfolio until the password is
        re-entered; Quit on the gate closes the app, as on launch.
        """
        if self._expected_password is None or self._lock_overlay is not None:
            return
        overlay = self.lock(self._expected_password)
        overlay.cancelled.connect(self.close)

    def set_private(self, private: bool) -> None:
        """Hide (or reveal) absolute monetary values across the dashboard.

        Masks the total portfolio value, the dividend/GIC-interest/income KPIs,
        and each holding's share count and market value. The state persists
        across refreshes (the widgets re-apply it on every render).
        """
        self._private = private
        self.kpi_panel.set_private(private)
        self.dashboard.set_private(private)
        self._sync_settings()

    @property
    def private_mode(self) -> bool:
        return self._private

    def open_settings(self) -> SettingsDialog:
        """Show the in-app settings dialog, building it on first use.

        Returns the dialog so callers (and tests) can drive it. Reused across
        opens so it keeps its position on screen.
        """
        if self._settings_dialog is None:
            self._settings_dialog = self._build_settings_dialog()
        dialog = self._settings_dialog
        dialog.clear_error()
        self._sync_settings()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def _dismiss_lock(self) -> None:
        if self._lock_overlay is not None:
            self._lock_overlay.hide()
            self._lock_overlay.deleteLater()
            self._lock_overlay = None

    def resizeEvent(self, event: QResizeEvent) -> None:
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
        if self._settings_dialog is not None:
            # A dialog is its own top-level window, so it does not inherit the
            # main window's stylesheet; restyle it explicitly.
            self._settings_dialog.setStyleSheet(stylesheet_for(theme))
            self._sync_settings()  # the toggle now offers the way back

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

        self._updated_label = QLabel("")
        self._updated_label.setObjectName("CardSubtitle")
        toolbar.addWidget(self._updated_label)

        # Push the Log out / Settings buttons to the far right of the toolbar.
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Only meaningful when a password gate is configured; revealed by lock().
        self._logout_button = QPushButton("Log out")
        self._logout_button.clicked.connect(self.log_out)
        self._logout_button.setVisible(False)
        toolbar.addWidget(self._logout_button)

        # Top-right gear: private mode, theme, export, and start-at-login all
        # live behind this one button.
        self._settings_button = QPushButton("⚙  Settings")
        self._settings_button.clicked.connect(self.open_settings)
        toolbar.addWidget(self._settings_button)

        self.addToolBar(toolbar)

    def _build_settings_dialog(self) -> SettingsDialog:
        dialog = SettingsDialog(self)
        dialog.setStyleSheet(stylesheet_for(self._theme))
        dialog.privateModeRequested.connect(self._on_private_requested)
        dialog.themeToggleRequested.connect(self.toggle_theme)
        dialog.exportRequested.connect(self._on_export)
        dialog.launchAtLoginRequested.connect(self._on_launch_at_login_requested)
        return dialog

    def _sync_settings(self) -> None:
        """Push the window's current state into the settings dialog, if open."""
        if self._settings_dialog is None:
            return
        other = Theme.LIGHT if self._theme is Theme.DARK else Theme.DARK
        supported = self._autostart.supported
        self._settings_dialog.sync(
            private=self._private,
            theme_name=_THEME_NAMES[self._theme],
            other_theme_name=_THEME_NAMES[other],
            launch_at_login=self._autostart.is_enabled(),
            launch_supported=supported,
            launch_note=_LAUNCH_NOTE if supported else self._autostart.reason,
        )

    def _on_launch_at_login_requested(self, enabled: bool) -> None:
        assert self._settings_dialog is not None  # only the dialog emits this
        self._settings_dialog.clear_error()
        try:
            self._autostart.set_enabled(enabled)
        except AutostartError as exc:
            self._settings_dialog.show_error(str(exc))
        # Re-read from the OS either way, so the checkbox shows what is really
        # registered rather than what was asked for.
        self._sync_settings()

    def _on_export(self) -> None:
        # Parent to the settings dialog while it is up: it is application-modal,
        # so a file chooser parented to the window behind it would not accept input.
        parent = self._modal_parent()
        path, _ = QFileDialog.getSaveFileName(
            parent, "Export portfolio report", "moneytor-report.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        try:
            markdown, pdf = self.export_report(path)
        except OSError as exc:
            self._report_error(f"Could not export report: {exc}")
            return
        QMessageBox.information(parent, "Report exported", f"Saved:\n{pdf}\n{markdown}")

    def _modal_parent(self) -> QWidget:
        """The widget to parent a nested dialog to (the settings dialog, if shown)."""
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            return self._settings_dialog
        return self

    def _report_error(self, message: str) -> None:
        """Show ``message`` inline in settings when open, else in the banner."""
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.show_error(message)
            return
        self.banner.show_message(message)

    def _on_selection_changed(self, account_ids: frozenset[str]) -> None:
        # Empty selection means "show everything".
        self._selected_ids = account_ids or None
        self.refresh()

    def _on_private_requested(self, private: bool) -> None:
        # Enabling private mode is free; revealing values requires the password.
        if private:
            self.set_private(True)
            return
        if self._verify_reveal_password():
            self.set_private(False)
        else:
            # Refused: re-render the dialog so its checkbox snaps back to ticked.
            self._sync_settings()

    def _verify_reveal_password(self) -> bool:
        """Prompt for the password; True if it matches (or none is configured)."""
        if self._expected_password is None:
            return True
        entered, accepted = QInputDialog.getText(
            self._modal_parent(),
            "Exit private mode",
            "Enter your password to reveal values:",
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return False
        if entered == self._expected_password:
            return True
        QMessageBox.warning(self._modal_parent(), "Private mode", "Incorrect password.")
        return False

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
