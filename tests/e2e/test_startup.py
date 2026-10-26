# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""End-to-end start-up: the real ``build_window`` against a real ``.env`` and cache.

Each test runs in its own temporary working directory, so ``.env`` and
``.cache/`` are throwaway and nothing touches the developer's real files. No
test reaches the network: credentials are only configured where the fetch path
is replaced.
"""

from __future__ import annotations

import os
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from moneytor.domain.enums import AccountType, AssetClass, Currency, Institution
from moneytor.domain.models import Account, Holding, Person
from moneytor.domain.money import Money
from moneytor.persistence.snapshot_cache import SnapshotCache
from moneytor.ui import app as app_module

CAD = Currency.CAD


def _real_people() -> tuple[Person, ...]:
    holding = Holding(
        symbol="REAL",
        exchange="TSX",
        asset_class=AssetClass.EQUITY,
        quantity=Decimal("10"),
        book_value=Money.of("900", CAD),
        market_value=Money.of("1000", CAD),
    )
    account = Account(
        id="REAL-1",
        person_id="person1",
        institution=Institution.QUESTRADE,
        account_type=AccountType.TFSA,
        cash=Money.of("50", CAD),
        holdings=(holding,),
    )
    return (Person(id="person1", name="Person1", accounts=(account,)),)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clean working directory standing in for the project root."""
    monkeypatch.chdir(tmp_path)
    # A developer's own MONEYTOR_* variables would leak into every test.
    for key in [k for k in os.environ if k.startswith("MONEYTOR")]:
        monkeypatch.delenv(key)
    return tmp_path


def _write_env(home: Path, *lines: str) -> None:
    (home / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _start(qtbot):
    window = app_module.build_window()
    qtbot.addWidget(window)
    return window


def _symbols(window) -> list[str]:
    table = window.dashboard.table
    return [table.item(r, 0).text() for r in range(table.rowCount())]


# --------------------------------------------------------------------------- #
# A mistake in .env
# --------------------------------------------------------------------------- #

_TYPO = "MONEYTOR__PERSON1_NAME=Alex"  # one underscore short of a valid key


def test_env_typo_is_shown_on_screen(home: Path, qtbot) -> None:
    _write_env(home, _TYPO, "MONEYTOR__PERSON1__QUESTRADE_REFRESH_TOKEN=x")
    window = _start(qtbot)
    assert window.banner.isVisible()
    assert "problem in your .env" in window.banner.message
    assert "MONEYTOR__PERSON1_NAME" in window.banner.message


def test_env_typo_still_shows_the_cached_portfolio(home: Path, qtbot) -> None:
    SnapshotCache().save(_real_people(), CAD)
    _write_env(home, _TYPO)
    window = _start(qtbot)
    assert _symbols(window) == ["REAL", "CASH:CAD"]


def test_env_typo_never_replaces_the_cache_with_demo_data(home: Path, qtbot) -> None:
    # The original bug: a typo meant "no credentials", so Refresh loaded the
    # demo portfolio — and saved it over the user's real cache.
    SnapshotCache().save(_real_people(), CAD)
    _write_env(home, _TYPO)
    window = _start(qtbot)

    window.reload_data()
    qtbot.waitUntil(lambda: "Could not refresh" in window.banner.message, timeout=5000)

    cached = SnapshotCache().load()
    assert cached is not None
    assert [a.id for p in cached.people for a in p.accounts] == ["REAL-1"]
    assert _symbols(window) == ["REAL", "CASH:CAD"]  # the screen kept the real data too
    assert "MONEYTOR__PERSON1_NAME" in window.banner.message


def test_env_typo_does_not_switch_off_the_password_gate(home: Path, qtbot) -> None:
    SnapshotCache().save(_real_people(), CAD)
    _write_env(home, "MONEYTOR_APP_PASSWORD=s3cret", _TYPO)
    window = _start(qtbot)
    assert window.is_locked
    assert window.dashboard.table.rowCount() == 0  # nothing loaded behind the gate


def test_invalid_display_currency_is_reported_not_ignored(home: Path, qtbot) -> None:
    _write_env(home, "MONEYTOR_DISPLAY_CURRENCY=EUR")
    window = _start(qtbot)
    assert "MONEYTOR_DISPLAY_CURRENCY" in window.banner.message


# --------------------------------------------------------------------------- #
# Normal start-ups
# --------------------------------------------------------------------------- #


def test_no_env_opens_the_demo_portfolio_without_caching_it(home: Path, qtbot) -> None:
    window = _start(qtbot)
    assert window.dashboard.table.rowCount() > 0
    assert not window.banner.isVisible()

    window.reload_data()  # Refresh in demo mode
    qtbot.waitUntil(lambda: window.last_updated.startswith("Updated"), timeout=5000)
    assert not (home / ".cache" / "snapshot.json").exists()


def test_cached_launch_shows_configured_names(home: Path, qtbot) -> None:
    SnapshotCache().save(_real_people(), CAD)
    _write_env(
        home,
        "MONEYTOR__PERSON1__NAME=Alex",
        "MONEYTOR__PERSON1__QUESTRADE_REFRESH_TOKEN=x",
    )
    window = _start(qtbot)
    tree = window.sidebar._tree
    assert tree.topLevelItem(0).text(0) == "Alex"
    assert _symbols(window) == ["REAL", "CASH:CAD"]


def test_password_gate_holds_data_until_unlocked(home: Path, qtbot) -> None:
    SnapshotCache().save(_real_people(), CAD)
    _write_env(home, "MONEYTOR_APP_PASSWORD=s3cret", "MONEYTOR__PERSON1__QUESTRADE_REFRESH_TOKEN=x")
    window = _start(qtbot)
    assert window.is_locked
    assert window.dashboard.table.rowCount() == 0

    overlay = window._lock_overlay
    overlay._input.setText("s3cret")
    overlay._attempt()
    assert not window.is_locked
    assert _symbols(window) == ["REAL", "CASH:CAD"]


# --------------------------------------------------------------------------- #
# Cached launches say how old the data is, and value it at its own rate
# --------------------------------------------------------------------------- #


def test_cached_launch_says_when_the_data_was_fetched(home: Path, qtbot) -> None:
    SnapshotCache().save(_real_people(), CAD, as_of="2026-10-01 09:30")
    window = _start(qtbot)
    assert window.last_updated.startswith(
        "Cached data from 2026-10-01 09:30 — Refresh for live prices"
    )


def test_cache_without_a_date_is_still_marked_as_cached(home: Path, qtbot) -> None:
    SnapshotCache().save(_real_people(), CAD)  # written before fetch times were stored
    window = _start(qtbot)
    assert window.last_updated.startswith("Cached data from an unknown date")


def test_cached_launch_converts_at_the_cached_rate(home: Path, qtbot) -> None:
    usd = replace(
        _real_people()[0].accounts[0].holdings[0],
        symbol="AAPL",
        exchange="NASDAQ",
        market_value=Money.of("100", Currency.USD),
    )
    people = (
        replace(
            _real_people()[0],
            accounts=(replace(_real_people()[0].accounts[0], holdings=(usd,)),),
        ),
    )
    SnapshotCache().save(people, CAD, as_of="2026-10-01 09:30", usd_cad=Decimal("1.4123"))
    window = _start(qtbot)

    # 100 USD at the cached 1.4123, not the built-in 1.36 placeholder.
    table = window.dashboard.table
    assert table.item(0, 5).text() == "$141.23 CAD"
    assert "USD/CAD 1.4123" in window.last_updated
    assert "estimate" not in window.last_updated


def test_old_cache_without_a_rate_flags_the_placeholder_rate(home: Path, qtbot) -> None:
    SnapshotCache().save(_real_people(), CAD, as_of="2026-10-01 09:30")
    window = _start(qtbot)
    assert "(estimate)" in window.last_updated


def test_export_from_cached_data_carries_the_data_date_not_today(home: Path, qtbot) -> None:
    SnapshotCache().save(_real_people(), CAD, as_of="2026-10-01 09:30", usd_cad=Decimal("1.4"))
    window = _start(qtbot)
    markdown, _pdf = window.export_report(home / "report.pdf")
    text = markdown.read_text(encoding="utf-8")
    assert "2026-10-01 09:30 (cached)" in text
