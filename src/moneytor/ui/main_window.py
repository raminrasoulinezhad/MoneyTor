"""The application main window: sidebar + dashboard + theme toggle + refresh."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from moneytor.connectors.errors import ConnectorError
from moneytor.domain.enums import Currency
from moneytor.domain.models import Person
from moneytor.fx.provider import FxProvider
from moneytor.ui.theme import Theme, stylesheet_for, tokens_for
from moneytor.ui.viewmodels import SidebarModel, view_model_for
from moneytor.ui.views.dashboard import DashboardView
from moneytor.ui.widgets.banner import ErrorBanner
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
        self.setWindowTitle("MoneyTor")
        self.resize(1180, 760)

        self._people = people
        self._provider = provider
        self._currency = display_currency
        self._theme = theme
        self._selected_ids: frozenset[str] | None = None
        self._loader = loader
        self._clock = clock or _default_clock
        self._worker: FetchWorker | None = None

        self._build_toolbar()

        central = QWidget()
        central.setObjectName("Root")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.banner = ErrorBanner()
        outer.addWidget(self.banner)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.sidebar = Sidebar()
        self.sidebar.selectionChanged.connect(self._on_selection_changed)
        self.dashboard = DashboardView()
        body.addWidget(self.sidebar)
        body.addWidget(self.dashboard, stretch=1)
        outer.addLayout(body, stretch=1)
        self.setCentralWidget(central)

        self.apply_theme(theme)
        self.set_people(people)

    # -- public API --------------------------------------------------------- #

    def set_people(self, people: tuple[Person, ...]) -> None:
        """Replace the data set, rebuild the sidebar, and refresh the view."""
        self._people = people
        self._selected_ids = None
        self.sidebar.set_model(_sidebar_model(people, self._provider, self._currency))
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the dashboard view-model for the current selection."""
        view_model = view_model_for(
            self._people, self._currency, self._provider, self._selected_ids
        )
        self.dashboard.set_view_model(view_model)

    def reload_data(self) -> None:
        """Fetch fresh data off the UI thread via the injected loader."""
        if self._loader is None or (self._worker is not None and self._worker.isRunning()):
            return
        self.dashboard.set_loading(True)
        self._worker = FetchWorker(task=self._loader)
        self._worker.succeeded.connect(self._on_reloaded)
        self._worker.failed.connect(self._on_reload_failed)
        self._worker.start()

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

        self._theme_button = QPushButton("Toggle theme")
        self._theme_button.clicked.connect(self.toggle_theme)
        toolbar.addWidget(self._theme_button)

        self._updated_label = QLabel("")
        self._updated_label.setObjectName("CardSubtitle")
        toolbar.addWidget(self._updated_label)
        self.addToolBar(toolbar)

    def _on_selection_changed(self, account_ids: frozenset[str]) -> None:
        # Empty selection means "show everything".
        self._selected_ids = account_ids or None
        self.refresh()

    def _on_reloaded(self, people: object) -> None:
        self.banner.hide()
        if isinstance(people, tuple):
            self.set_people(people)
        self._updated_label.setText(f"Updated {self._clock()}")

    def _on_reload_failed(self, exc: object) -> None:
        detail = str(exc) if isinstance(exc, ConnectorError) else "Unexpected error."
        self.banner.show_message(f"Could not refresh data: {detail}")


def _sidebar_model(
    people: tuple[Person, ...], provider: FxProvider, currency: Currency
) -> SidebarModel:
    # The full (unfiltered) sidebar always lists every person/account.
    return view_model_for(people, currency, provider).sidebar


def _default_clock() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
