"""Application bootstrap: load credentials, build connectors, launch the cockpit."""

from __future__ import annotations

import logging
import sys
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import QApplication

from moneytor.aggregation import SectorMap, apply_sector_map
from moneytor.config.errors import ConfigError
from moneytor.config.logging import setup_logging
from moneytor.config.settings import PersonCredentials, Settings, load_settings
from moneytor.connectors import (
    Connector,
    MockConnector,
    QuestradeConnector,
    WealthsimpleConnector,
)
from moneytor.connectors.wealthsimple import OtpProvider
from moneytor.domain.enums import Institution
from moneytor.domain.models import Account, Person
from moneytor.fx.live import SnapshotFxProvider
from moneytor.persistence import SnapshotCache
from moneytor.persistence.token_store import TokenStore

from .main_window import MainWindow
from .otp import GuiOtpProvider

_LOG = logging.getLogger(__name__)

# Fallback USD->CAD used before the first fetch / when the rate API is offline.
_FALLBACK_USD_CAD = Decimal("1.36")

_FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "mock_accounts.json"
# Optional user-maintained ticker -> GICS sector overrides (fills broker gaps).
_SECTOR_MAP_PATH = Path(".cache") / "sectors.json"


def _load_sector_map() -> SectorMap:
    """Load the optional ticker->sector override file, or an empty map."""
    if not _SECTOR_MAP_PATH.exists():
        return SectorMap()
    try:
        return SectorMap.from_file(_SECTOR_MAP_PATH)
    except (OSError, ValueError) as exc:
        _LOG.warning("Ignoring invalid sector map %s: %s", _SECTOR_MAP_PATH, exc)
        return SectorMap()


def demo_people() -> tuple[Person, ...]:
    """Load the bundled mock portfolio as one or more demo people."""
    connector = MockConnector.from_fixture(Institution.QUESTRADE, _FIXTURE)
    connector.authenticate()
    accounts = connector.fetch_accounts()

    people_accounts: dict[str, list[Account]] = {}
    for account in accounts:
        people_accounts.setdefault(account.person_id, []).append(account)

    return tuple(
        Person(
            id=person_id,
            name=f"Demo {person_id.capitalize()}",
            accounts=tuple(person_accounts),
        )
        for person_id, person_accounts in sorted(people_accounts.items())
    )


def _connectors_for(
    creds: PersonCredentials,
    token_store: TokenStore,
    otp_provider: OtpProvider | None = None,
) -> list[Connector]:
    """Build the live connectors a person has credentials for."""
    connectors: list[Connector] = []
    if creds.questrade_refresh_token is not None:
        connectors.append(
            QuestradeConnector(
                person_id=creds.person_id,
                seed_refresh_token=creds.questrade_refresh_token.reveal(),
                token_store=token_store,
            )
        )
    if creds.wealthsimple_email is not None and creds.wealthsimple_password is not None:
        # Give the 2FA prompt this person's name + email so the user knows
        # which account the code is for.
        account_otp: OtpProvider | None = otp_provider
        if isinstance(otp_provider, GuiOtpProvider):
            account_otp = otp_provider.for_account(creds.person_id, creds.wealthsimple_email)
        connectors.append(
            WealthsimpleConnector(
                person_id=creds.person_id,
                email=creds.wealthsimple_email,
                password=creds.wealthsimple_password,
                otp_provider=account_otp,
                token_store=token_store,
            )
        )
    return connectors


def live_people(
    settings: Settings,
    token_store: TokenStore,
    otp_provider: OtpProvider | None = None,
) -> tuple[Person, ...]:
    """Authenticate and fetch every configured person's accounts.

    Connector failures (auth/rate-limit/transport) propagate as ``ConnectorError``
    so the UI surfaces them via the error banner instead of crashing. Wealthsimple
    2FA is satisfied by ``otp_provider`` (a GUI prompt in the app).
    """
    people: list[Person] = []
    for creds in settings.people:
        accounts: list[Account] = []
        for connector in _connectors_for(creds, token_store, otp_provider):
            connector.authenticate()
            accounts.extend(connector.fetch_accounts())
        if accounts:
            people.append(
                Person(
                    id=creds.person_id,
                    name=creds.person_id.capitalize(),
                    accounts=tuple(accounts),
                )
            )
    return tuple(people)


def _load_settings_safely() -> Settings:
    """Load settings, degrading to demo mode (no people) on a config error."""
    try:
        return load_settings()
    except ConfigError as exc:
        _LOG.error("Invalid configuration; starting in demo mode: %s", exc)
        return Settings()


def run_app(argv: list[str] | None = None) -> int:
    """Create the QApplication, show the cockpit, and run the event loop.

    Cold-starts from the snapshot cache when present (instant, offline). When
    credentials are configured in ``.env`` the Refresh button (and an automatic
    cold-start fetch) pulls live data through the real connectors; otherwise the
    app stays in demo mode with the bundled fixture.
    """
    app = QApplication.instance() or QApplication(argv or sys.argv)
    settings = _load_settings_safely()
    # Configure logging with secret redaction before anything can log.
    setup_logging(settings.log_level, settings.secret_values())
    currency = settings.display_currency
    cache = SnapshotCache()
    token_store = TokenStore()
    has_credentials = bool(settings.people)
    # Created on the GUI thread; its dialog is marshalled there when a worker
    # thread requests a 2FA code during a Wealthsimple login.
    otp_provider = GuiOtpProvider()
    # One provider instance, shared with the window and refreshed on every fetch
    # so USD<->CAD stays reasonably current without a live feed.
    provider = SnapshotFxProvider(_FALLBACK_USD_CAD)
    sector_map = _load_sector_map()

    def loader() -> tuple[Person, ...]:
        provider.refresh()  # off the UI thread, alongside the data fetch
        if has_credentials:
            fetched = live_people(settings, token_store, otp_provider)
        else:
            fetched = demo_people()
        fetched = apply_sector_map(fetched, sector_map)
        cache.save(fetched, currency)
        return fetched

    cached = cache.load()
    if cached is not None:
        # Re-apply the sector overrides on cached loads too — the cache predates
        # any edits to sectors.json, and brokers that omit sectors (Wealthsimple)
        # would otherwise stay "Unknown" until the next live fetch.
        people: tuple[Person, ...] = apply_sector_map(cached.people, sector_map)
    elif has_credentials:
        people = ()  # filled by the cold-start reload below
    else:
        people = apply_sector_map(demo_people(), sector_map)

    window = MainWindow(
        people=people,
        provider=provider,
        display_currency=currency,
        loader=loader,
    )
    otp_provider.parent_widget = window  # center the 2FA dialog on the window
    window.show()

    # With credentials but no cache, fetch live immediately (off-thread, with
    # the loading state and error banner) so the user sees real data on launch.
    if has_credentials and cached is None:
        window.reload_data()

    return app.exec()
