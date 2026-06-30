# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Tests for the aggregation engine (Phase 5)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from moneytor.aggregation import (
    AssetMap,
    SectorMap,
    account_value,
    allocation_by_symbol,
    annual_dividend_income,
    annual_gic_interest,
    apply_sector_map,
    build_snapshot,
    gic_interest_rate,
    merge_holdings,
    normalize_sector,
    person_value,
    totals_by_currency,
)
from moneytor.connectors import load_accounts
from moneytor.domain import (
    AccountType,
    AssetClass,
    Currency,
    Holding,
    Institution,
    Money,
    Person,
)
from moneytor.domain.models import Account
from moneytor.fx import StaticFxProvider

CAD = Currency.CAD
USD = Currency.USD
FIXTURE = Path(__file__).parent.parent / "fixtures" / "mock_accounts.json"

PROVIDER = StaticFxProvider(rates={(USD, CAD): Decimal("1.35"), (CAD, USD): Decimal("0.74")})


def _holding(symbol: str, exchange: str, currency: Currency, qty: str, mv: str) -> Holding:
    return Holding(
        symbol=symbol,
        exchange=exchange,
        asset_class=AssetClass.EQUITY,
        quantity=Decimal(qty),
        book_value=Money.of("0", currency),
        market_value=Money.of(mv, currency),
    )


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SHOP.TO", "SHOP"),
        ("shop.to", "SHOP"),
        ("ABC.VN", "ABC"),  # TSX Venture venue suffix stripped
        ("BRK.B", "BRK.B"),  # share-class dot preserved
        ("AAPL", "AAPL"),
        (" vfv.to ", "VFV"),
    ],
)
def test_canonical_symbol(raw: str, expected: str) -> None:
    assert AssetMap().canonical(raw) == expected


def test_asset_map_override_wins() -> None:
    amap = AssetMap(overrides={"shop.to": "SHOP", "SHOPIFY": "SHOP"})
    assert amap.canonical("SHOPIFY") == "SHOP"
    assert amap.canonical("SHOP.TO") == "SHOP"


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #


def test_merge_unifies_same_asset_across_exchanges_and_currencies() -> None:
    holdings = [
        _holding("SHOP.TO", "TSX", CAD, "10", "1000.00"),
        _holding("SHOP", "NYSE", USD, "5", "400.00"),  # 400 USD -> 540 CAD
    ]
    unified = merge_holdings(holdings, CAD, PROVIDER)
    assert len(unified) == 1
    shop = unified[0]
    assert shop.symbol == "SHOP"
    assert shop.total_quantity == Decimal("15")
    assert shop.total_market_value == Money.of("1540.00", CAD)
    assert len(shop.sources) == 2


def test_annual_dividend_income_sums_yield_times_value_in_display_currency() -> None:
    cad = replace(
        _holding("VFV", "TSX", CAD, "25", "3100.00"), dividend_yield=Decimal("0.012")
    )  # 3100 * 0.012 = 37.20 CAD
    usd = replace(
        _holding("AAPL", "NASDAQ", USD, "5", "950.75"), dividend_yield=Decimal("0.005")
    )  # 950.75 USD -> 1283.51 CAD; * 0.005 = 6.4176 CAD
    no_yield = _holding("SHOP", "TSX", CAD, "10", "1200.50")  # no dividend -> contributes 0
    account = Account(
        id="a",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.TFSA,
        cash=Money.zero(CAD),
        holdings=(cad, usd, no_yield),
    )
    snapshot = build_snapshot((Person(id="p", name="P", accounts=(account,)),), CAD, PROVIDER)
    assert annual_dividend_income(snapshot) == Money.of("43.62", CAD)


def test_annual_dividend_income_zero_without_yields() -> None:
    holdings = (_holding("SHOP", "TSX", CAD, "10", "1200.50"),)
    account = Account(
        id="a",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.TFSA,
        cash=Money.zero(CAD),
        holdings=holdings,
    )
    snapshot = build_snapshot((Person(id="p", name="P", accounts=(account,)),), CAD, PROVIDER)
    assert annual_dividend_income(snapshot) == Money.zero(CAD)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Oaken GIC 4.50% 2027", Decimal("0.045")),
        ("GIC 3% 1yr", Decimal("0.03")),
        ("Tangerine GIC 5.25 % cashable", Decimal("0.0525")),
        ("GIC-2026", None),  # no rate encoded
        ("plain savings", None),
    ],
)
def test_gic_interest_rate_parsing(text: str, expected: Decimal | None) -> None:
    assert gic_interest_rate(text) == expected


def test_annual_gic_interest_sums_rate_times_value_in_display_currency() -> None:
    # Rate parsed from the name; value FX-converted to the display currency.
    cad_gic = replace(
        _holding("GIC-OAKEN", "", CAD, "1", "2000.00"),
        asset_class=AssetClass.GIC,
        name="Oaken GIC 4.50% 2027",
    )  # 2000 * 0.045 = 90.00 CAD
    usd_gic = replace(
        _holding("GIC-USD", "", USD, "1", "1000.00"),
        asset_class=AssetClass.GIC,
        name="US GIC 2.00%",
    )  # 1000 USD -> 1350 CAD; * 0.02 = 27.00 CAD
    no_rate = replace(
        _holding("GIC-PLAIN", "", CAD, "1", "500.00"), asset_class=AssetClass.GIC
    )  # no rate in name/symbol -> contributes 0
    equity = _holding("SHOP", "TSX", CAD, "10", "1200.50")  # not a GIC -> ignored
    account = Account(
        id="a",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.GIC,
        cash=Money.zero(CAD),
        holdings=(cad_gic, usd_gic, no_rate, equity),
    )
    snapshot = build_snapshot((Person(id="p", name="P", accounts=(account,)),), CAD, PROVIDER)
    assert annual_gic_interest(snapshot) == Money.of("117.00", CAD)


def test_annual_gic_interest_includes_fixed_income_gics() -> None:
    # Questrade/Wealthsimple file GICs as Bond -> FIXED_INCOME, with the rate in
    # the name. These must still count toward GIC interest.
    gic = replace(
        _holding("5VZCXB2CACAD", "", CAD, "1", "12800.00"),
        asset_class=AssetClass.FIXED_INCOME,
        name="HSLC HOME TRUST COMPANY MAT 07/08/2026 2.55% 90D",
    )  # 12800 * 0.0255 = 326.40 CAD
    account = Account(
        id="a",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.MARGIN,
        cash=Money.zero(CAD),
        holdings=(gic,),
    )
    snapshot = build_snapshot((Person(id="p", name="P", accounts=(account,)),), CAD, PROVIDER)
    assert annual_gic_interest(snapshot) == Money.of("326.40", CAD)


def test_merge_is_order_independent() -> None:
    a = _holding("SHOP.TO", "TSX", CAD, "10", "1000.00")
    b = _holding("SHOP", "NYSE", USD, "5", "400.00")
    forward = merge_holdings([a, b], CAD, PROVIDER)
    reverse = merge_holdings([b, a], CAD, PROVIDER)
    assert forward[0].total_market_value == reverse[0].total_market_value
    assert forward[0].total_quantity == reverse[0].total_quantity


def test_merge_collapses_venue_suffix_and_fills_missing_metadata() -> None:
    # Same asset from two sources: one carries the name, the other the sector.
    venue = replace(
        _holding("ABC.VN", "TSXV", CAD, "10", "100.00"), name="Alpha Beta Corp", sector=""
    )
    plain = replace(_holding("ABC", "TSX", CAD, "5", "50.00"), name="", sector="Energy")
    unified = merge_holdings([venue, plain], CAD, PROVIDER)
    assert len(unified) == 1
    abc = unified[0]
    assert abc.symbol == "ABC"  # .VN suffix stripped, merged with plain "ABC"
    assert abc.total_quantity == Decimal("15")
    assert abc.name == "Alpha Beta Corp"  # filled from the source that has it
    assert abc.sector == "Energy"  # filled from the other source


def test_merge_results_sorted_by_symbol() -> None:
    holdings = [
        _holding("VFV", "TSX", CAD, "1", "10"),
        _holding("AAPL", "NASDAQ", USD, "1", "10"),
    ]
    unified = merge_holdings(holdings, CAD, PROVIDER)
    assert [u.symbol for u in unified] == ["AAPL", "VFV"]


# --------------------------------------------------------------------------- #
# Rollups & reconciliation
# --------------------------------------------------------------------------- #


def _fixture_people() -> tuple[Person, ...]:
    accounts = load_accounts(FIXTURE)
    return (Person(id="ramin", name="Ramin", accounts=accounts),)


def test_totals_by_currency_reconciles_to_sources() -> None:
    totals = totals_by_currency(_fixture_people())
    # CAD: cash 1500 + SHOP 1200.50 + VFV 3100 + GIC 2000 = 7800.50
    # USD: cash 300 + AAPL 950.75 = 1250.75
    assert totals[CAD] == Money.of("7800.50", CAD)
    assert totals[USD] == Money.of("1250.75", USD)


def test_account_value_cross_currency() -> None:
    accounts = load_accounts(FIXTURE)
    usd_account = accounts[1]  # margin, USD
    # (300 + 950.75) USD * 1.35 = 1688.5125 -> 1688.51
    assert account_value(usd_account, CAD, PROVIDER) == Money.of("1688.51", CAD)


def test_person_value_sums_accounts() -> None:
    person = _fixture_people()[0]
    # CAD account 5800.50 + USD account 1688.51 (converted) + GIC account 2000 = 9489.01
    assert person_value(person, CAD, PROVIDER) == Money.of("9489.01", CAD)


def test_empty_account_value_is_cash_only() -> None:
    account = Account(
        id="x",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.CASH,
        cash=Money.of("42", CAD),
    )
    assert account_value(account, CAD, PROVIDER) == Money.of("42.00", CAD)


# --------------------------------------------------------------------------- #
# Snapshot & allocation
# --------------------------------------------------------------------------- #


def test_build_snapshot_end_to_end() -> None:
    snapshot = build_snapshot(_fixture_people(), CAD, PROVIDER, as_of="2026-06-06")
    assert snapshot.display_currency is CAD
    assert snapshot.as_of == "2026-06-06"
    symbols = {u.symbol for u in snapshot.unified_holdings}
    assert symbols == {"SHOP", "VFV", "AAPL", "GIC-OAKEN-2027"}


def test_allocation_sums_to_one() -> None:
    snapshot = build_snapshot(_fixture_people(), CAD, PROVIDER)
    allocations = allocation_by_symbol(snapshot)
    assert sum(allocations.values()) == pytest.approx(Decimal("1"), abs=Decimal("0.001"))


def test_allocation_empty_portfolio() -> None:
    snapshot = build_snapshot((), CAD, PROVIDER)
    assert allocation_by_symbol(snapshot) == {}


# --------------------------------------------------------------------------- #
# Sector mapping
# --------------------------------------------------------------------------- #


def _person_with(holding: Holding) -> Person:
    account = Account(
        id="a1",
        person_id="p1",
        institution=Institution.QUESTRADE,
        account_type=AccountType.TFSA,
        cash=Money.zero(CAD),
        holdings=(holding,),
    )
    return Person(id="p1", name="P", accounts=(account,))


def test_sector_map_fills_only_empty_sectors() -> None:
    sector_map = SectorMap({"shop": "Information Technology", "vfv": "Diversified"})
    no_sector = _person_with(_holding("SHOP", "TSX", CAD, "1", "10"))
    already = _person_with(replace(_holding("VFV", "TSX", CAD, "1", "10"), sector="Broker Sector"))

    filled = apply_sector_map((no_sector, already), sector_map)
    assert filled[0].accounts[0].holdings[0].sector == "Information Technology"
    assert filled[1].accounts[0].holdings[0].sector == "Broker Sector"  # not overwritten


def test_sector_map_unmapped_symbol_stays_empty() -> None:
    filled = apply_sector_map((_person_with(_holding("ZZZ", "TSX", CAD, "1", "10")),), SectorMap())
    assert filled[0].accounts[0].holdings[0].sector == ""


def test_sector_carried_into_unified_holding() -> None:
    holding = replace(_holding("SHOP", "TSX", CAD, "1", "10"), sector="Information Technology")
    unified = merge_holdings((holding,), CAD, PROVIDER)
    assert unified[0].sector == "Information Technology"


def test_cash_and_gic_use_distinct_synthetic_sectors() -> None:
    # Cash reports as "Cash"; GICs as the distinct "Cash-Equivalent" sector,
    # both overriding whatever (if anything) the broker supplied.
    cash = replace(
        _holding("CASH:USD", "", USD, "100", "100"),
        asset_class=AssetClass.CASH,
    )
    gic = replace(
        _holding("GIC-2026", "", CAD, "1", "5000"),
        asset_class=AssetClass.GIC,
        sector="Financials",  # broker classification is ignored
    )
    unified = {u.symbol: u for u in merge_holdings((cash, gic), CAD, PROVIDER)}
    assert unified["CASH:USD"].sector == "Cash"
    assert unified["GIC-2026"].sector == "Cash-Equivalent"


@pytest.mark.parametrize("symbol", ["GOLD", "gold", "IAUM"])
def test_bullion_symbols_classified_as_bullion(symbol: str) -> None:
    holding = replace(_holding(symbol, "", CAD, "1", "100"), sector="Materials")
    unified = merge_holdings((holding,), CAD, PROVIDER)
    assert unified[0].sector == "Bullion"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FinancialServices", "Financials"),
        ("BasicMaterials", "Materials"),
        ("ConsumerDefensive", "Consumer Staples"),
        ("Healthcare", "Health Care"),
        ("Technology", "Information Technology"),
        ("Energy", "Energy"),  # already canonical
        ("Information Technology", "Information Technology"),  # GICS passes through
        ("", ""),
        ("Something Novel", "Something Novel"),  # unknown passes through
    ],
)
def test_normalize_sector_maps_to_gics(raw: str, expected: str) -> None:
    assert normalize_sector(raw) == expected


# --------------------------------------------------------------------------- #
# Merge — additional numerical edge cases
# --------------------------------------------------------------------------- #


def test_merge_same_symbol_same_currency_sums_across_accounts() -> None:
    # The same security held in two accounts (same currency) must aggregate.
    unified = merge_holdings(
        [
            _holding("SHOP", "TSX", CAD, "10", "1000.00"),
            _holding("SHOP", "TSX", CAD, "15", "1500.00"),
        ],
        CAD,
        PROVIDER,
    )
    assert len(unified) == 1
    assert unified[0].total_quantity == Decimal("25")
    assert unified[0].total_market_value == Money.of("2500.00", CAD)


def test_merge_empty_input_returns_empty() -> None:
    assert merge_holdings([], CAD, PROVIDER) == ()


def test_merge_keeps_first_non_none_dividend_yield() -> None:
    # When sources disagree, the first non-None yield (in input order) wins.
    first_blank = replace(_holding("X", "TSX", CAD, "1", "10"), dividend_yield=None)
    has_yield = replace(_holding("X", "NYSE", USD, "1", "10"), dividend_yield=Decimal("0.03"))
    assert merge_holdings([first_blank, has_yield], CAD, PROVIDER)[0].dividend_yield == Decimal(
        "0.03"
    )
    conflicting_first = replace(
        _holding("X", "TSX", CAD, "1", "10"), dividend_yield=Decimal("0.02")
    )
    assert merge_holdings([conflicting_first, has_yield], CAD, PROVIDER)[
        0
    ].dividend_yield == Decimal("0.02")


def test_merge_takes_asset_class_from_first_member() -> None:
    equity = _holding("X", "TSX", CAD, "1", "10")  # EQUITY
    bond = replace(_holding("X", "TSX", CAD, "1", "10"), asset_class=AssetClass.FIXED_INCOME)
    assert merge_holdings([equity, bond], CAD, PROVIDER)[0].asset_class is AssetClass.EQUITY
    assert merge_holdings([bond, equity], CAD, PROVIDER)[0].asset_class is AssetClass.FIXED_INCOME


# --------------------------------------------------------------------------- #
# Allocation — division-by-zero, single symbol, precision
# --------------------------------------------------------------------------- #


def _snapshot_of(*holdings: Holding):
    account = Account(
        id="a",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.TFSA,
        cash=Money.zero(CAD),
        holdings=holdings,
    )
    return build_snapshot((Person(id="p", name="P", accounts=(account,)),), CAD, PROVIDER)


def test_allocation_single_symbol_is_one() -> None:
    alloc = allocation_by_symbol(_snapshot_of(_holding("AAA", "TSX", CAD, "1", "500")))
    assert alloc == {"AAA": Decimal("1.0000")}


def test_allocation_all_zero_values_returns_zeros_not_div_by_zero() -> None:
    alloc = allocation_by_symbol(
        _snapshot_of(_holding("AAA", "TSX", CAD, "1", "0"), _holding("BBB", "TSX", CAD, "1", "0"))
    )
    assert alloc == {"AAA": Decimal("0"), "BBB": Decimal("0")}


def test_allocation_respects_places_parameter() -> None:
    snapshot = _snapshot_of(
        _holding("AAA", "TSX", CAD, "1", "1"), _holding("BBB", "TSX", CAD, "1", "2")
    )
    alloc = allocation_by_symbol(snapshot, places=2)
    # 1/3 and 2/3 rounded to 2 places.
    assert alloc == {"AAA": Decimal("0.33"), "BBB": Decimal("0.67")}


# --------------------------------------------------------------------------- #
# Dividend / GIC interest — extra branches
# --------------------------------------------------------------------------- #


def test_annual_dividend_income_explicit_zero_yield_contributes_zero() -> None:
    holding = replace(_holding("AAA", "TSX", CAD, "1", "1000"), dividend_yield=Decimal("0"))
    assert annual_dividend_income(_snapshot_of(holding)) == Money.zero(CAD)


def test_annual_dividend_income_empty_snapshot_is_zero() -> None:
    assert annual_dividend_income(build_snapshot((), CAD, PROVIDER)) == Money.zero(CAD)


def test_annual_gic_interest_falls_back_to_rate_in_symbol() -> None:
    # Rate absent from the name but present in the symbol -> still counted.
    gic = replace(
        _holding("GIC 3% 2026", "", CAD, "1", "1000.00"),
        asset_class=AssetClass.GIC,
        name="Generic GIC",
    )
    assert annual_gic_interest(_snapshot_of(gic)) == Money.of("30.00", CAD)


def test_annual_gic_interest_empty_snapshot_is_zero() -> None:
    assert annual_gic_interest(build_snapshot((), CAD, PROVIDER)) == Money.zero(CAD)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("GIC 3% bonus 4%", Decimal("0.03")),  # first percentage wins
        ("GIC\t5%\t2027", Decimal("0.05")),  # tab whitespace
        ("GIC 03% 1yr", Decimal("0.03")),  # leading zero
        ("GIC 0% promo", Decimal("0")),  # explicit zero rate
        ("", None),  # empty string
    ],
)
def test_gic_interest_rate_edge_cases(text: str, expected: Decimal | None) -> None:
    assert gic_interest_rate(text) == expected


# --------------------------------------------------------------------------- #
# Account / person / totals — extra rollup cases
# --------------------------------------------------------------------------- #


def test_account_value_converts_mixed_currency_holdings() -> None:
    account = Account(
        id="a",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.MARGIN,
        cash=Money.of("100", CAD),
        holdings=(_holding("C", "TSX", CAD, "1", "500"), _holding("U", "NYSE", USD, "1", "300")),
    )
    # 100 CAD + 500 CAD + (300 USD * 1.35 = 405) = 1005.00 CAD
    assert account_value(account, CAD, PROVIDER) == Money.of("1005.00", CAD)


def test_person_value_with_no_accounts_is_zero() -> None:
    person = Person(id="p", name="P", accounts=())
    assert person_value(person, CAD, PROVIDER) == Money.zero(CAD)


def test_totals_by_currency_empty_people_is_empty() -> None:
    assert totals_by_currency(()) == {}


def test_totals_by_currency_sums_duplicate_currency_across_accounts() -> None:
    def cad_account(id_: str, cash: str) -> Account:
        return Account(
            id=id_,
            person_id="p",
            institution=Institution.QUESTRADE,
            account_type=AccountType.TFSA,
            cash=Money.of(cash, CAD),
            holdings=(_holding("AAA", "TSX", CAD, "1", "100"),),
        )

    person = Person(id="p", name="P", accounts=(cad_account("a", "10"), cad_account("b", "20")))
    totals = totals_by_currency((person,))
    # cash 10 + 20 + holdings 100 + 100 = 230
    assert totals[CAD] == Money.of("230", CAD)


# --------------------------------------------------------------------------- #
# Snapshot — asset map applied during merge
# --------------------------------------------------------------------------- #


def test_asset_map_from_file_loads_overrides(tmp_path: Path) -> None:
    path = tmp_path / "assets.json"
    path.write_text('{"SHOP.TO": "SHOP", "shopify": "SHOP"}', encoding="utf-8")
    amap = AssetMap.from_file(path)
    assert amap.canonical("SHOPIFY") == "SHOP"
    assert amap.canonical("SHOP.TO") == "SHOP"


def test_asset_map_from_file_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "assets.json"
    path.write_text('["not", "an", "object"]', encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        AssetMap.from_file(path)


def test_sector_map_from_file_loads_and_normalizes(tmp_path: Path) -> None:
    path = tmp_path / "sectors.json"
    path.write_text('{"AAPL": "Technology"}', encoding="utf-8")
    smap = SectorMap.from_file(path)
    assert smap.get("aapl") == "Information Technology"  # normalized to GICS


def test_sector_map_from_file_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "sectors.json"
    path.write_text('"just a string"', encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        SectorMap.from_file(path)


def test_build_snapshot_applies_asset_map_override() -> None:
    account = Account(
        id="a",
        person_id="p",
        institution=Institution.QUESTRADE,
        account_type=AccountType.TFSA,
        cash=Money.zero(CAD),
        holdings=(
            _holding("SHOPIFY", "TSX", CAD, "1", "10"),
            _holding("SHOP", "TSX", CAD, "1", "10"),
        ),
    )
    snapshot = build_snapshot(
        (Person(id="p", name="P", accounts=(account,)),),
        CAD,
        PROVIDER,
        asset_map=AssetMap({"SHOPIFY": "SHOP"}),
    )
    assert [u.symbol for u in snapshot.unified_holdings] == ["SHOP"]
    assert snapshot.unified_holdings[0].total_quantity == Decimal("2")
