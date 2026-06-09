"""Application bootstrap: build demo data and launch the cockpit."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import QApplication

from moneytor.connectors import MockConnector
from moneytor.domain.enums import Currency, Institution
from moneytor.domain.models import Person
from moneytor.fx.provider import StaticFxProvider
from moneytor.persistence import SnapshotCache

from .main_window import MainWindow

# A modest demo FX table; live rates arrive in Phase 8.
_DEMO_RATES = {
    (Currency.USD, Currency.CAD): Decimal("1.36"),
    (Currency.CAD, Currency.USD): Decimal("0.74"),
}

_FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "mock_accounts.json"


def demo_provider() -> StaticFxProvider:
    """A static FX provider for demo/offline use."""
    return StaticFxProvider(rates=_DEMO_RATES)


def demo_people() -> tuple[Person, ...]:
    """Load the bundled mock portfolio as a single demo person."""
    connector = MockConnector.from_fixture(Institution.QUESTRADE, _FIXTURE)
    connector.authenticate()
    accounts = connector.fetch_accounts()
    return (Person(id="ramin", name="Ramin", accounts=accounts),)


def run_app(argv: list[str] | None = None) -> int:
    """Create the QApplication, show the cockpit, and run the event loop.

    Cold-starts from the snapshot cache when present (instant, offline), and
    refreshes re-fetch and re-cache via the injected loader.
    """
    app = QApplication.instance() or QApplication(argv or sys.argv)
    currency = Currency.CAD
    cache = SnapshotCache()

    cached = cache.load()
    people = cached.people if cached else demo_people()

    def loader() -> tuple[Person, ...]:
        fetched = demo_people()
        cache.save(fetched, currency)
        return fetched

    window = MainWindow(
        people=people,
        provider=demo_provider(),
        display_currency=currency,
        loader=loader,
    )
    window.show()
    return app.exec()
