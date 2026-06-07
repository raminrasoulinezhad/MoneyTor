"""The application main window: sidebar + dashboard + theme toggle."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QToolBar,
    QWidget,
)

from moneytor.domain.enums import Currency
from moneytor.domain.models import Person
from moneytor.fx.provider import FxProvider
from moneytor.ui.theme import Theme, stylesheet_for, tokens_for
from moneytor.ui.viewmodels import SidebarModel, view_model_for
from moneytor.ui.views.dashboard import DashboardView
from moneytor.ui.widgets.sidebar import Sidebar


class MainWindow(QMainWindow):
    """Cockpit window. Renders people via the dashboard, filtered by sidebar."""

    def __init__(
        self,
        people: tuple[Person, ...],
        provider: FxProvider,
        display_currency: Currency = Currency.CAD,
        theme: Theme = Theme.DARK,
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

        self._build_toolbar()

        central = QWidget()
        central.setObjectName("Root")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.selectionChanged.connect(self._on_selection_changed)
        self.dashboard = DashboardView()

        layout.addWidget(self.sidebar)
        layout.addWidget(self.dashboard, stretch=1)
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

    # -- internals ---------------------------------------------------------- #

    def _build_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self._theme_button = QPushButton("Toggle theme")
        self._theme_button.clicked.connect(self.toggle_theme)
        toolbar.addWidget(self._theme_button)
        self.addToolBar(toolbar)

    def _on_selection_changed(self, account_ids: frozenset[str]) -> None:
        # Empty selection means "show everything".
        self._selected_ids = account_ids or None
        self.refresh()


def _sidebar_model(
    people: tuple[Person, ...], provider: FxProvider, currency: Currency
) -> SidebarModel:
    # The full (unfiltered) sidebar always lists every person/account.
    return view_model_for(people, currency, provider).sidebar
