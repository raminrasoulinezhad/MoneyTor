# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Bundled ticker → GICS sector defaults.

Wealthsimple returns no sector at all and Questrade leaves some securities
unclassified, so without this table most holdings would show "Unknown" and the
sector donut would be meaningless. Entries are a fallback only: a sector the
broker reports wins, and the user's own ``.cache/sectors.json`` overrides both.

Tickers are listed without an exchange suffix — ``SectorMap`` strips ``.TO``,
``.V`` and friends before looking one up, so ``"CVE"`` covers ``CVE.TO`` too.
Share-class and unit suffixes (``.A``, ``.UN``) are *not* stripped and must be
written out in full.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

DEFAULT_SECTORS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        # --- Energy ---------------------------------------------------------
        "AAV": "Energy",
        "AKT": "Energy",
        "ATH": "Energy",
        "BIR": "Energy",
        "CCO": "Energy",  # uranium: GICS files fuel miners under Energy
        "CEI": "Energy",
        "CJ": "Energy",
        "CVE": "Energy",
        "ENB": "Energy",
        "EQT": "Energy",
        "FRU": "Energy",
        "GFR": "Energy",
        "HWX": "Energy",
        "IPO": "Energy",
        "KEL": "Energy",
        "NXE": "Energy",
        "PEY": "Energy",
        "PNE": "Energy",
        "POU": "Energy",
        "PPL": "Energy",
        "PRQ": "Energy",
        "PXT": "Energy",
        "RGSI": "Energy",
        "SCR": "Energy",
        "SGY": "Energy",
        "TOU": "Energy",
        "TPZ": "Energy",
        "TRP": "Energy",
        "WCP": "Energy",
        # --- Materials ------------------------------------------------------
        "AAG": "Materials",
        "AGAG": "Materials",
        "ALS": "Materials",
        "AYA": "Materials",
        "BEX": "Materials",
        "BRC": "Materials",
        "BTO": "Materials",
        "CGNT": "Materials",
        "CS": "Materials",
        "EMPR": "Materials",
        "FDY": "Materials",
        "FEO": "Materials",
        "FNV": "Materials",
        "FVI": "Materials",
        "GGD": "Materials",
        "HSTR": "Materials",
        "IFP": "Materials",
        "IVN": "Materials",
        "JAG": "Materials",
        "LUG": "Materials",
        "LUN": "Materials",
        "LUNR": "Materials",
        "MAXX": "Materials",
        "MN": "Materials",
        "MTA": "Materials",
        "MUX": "Materials",
        "NAM": "Materials",
        "NEXM": "Materials",
        "NFGC": "Materials",
        "NGEX": "Materials",
        "NICU": "Materials",
        "OGN": "Materials",
        "SICO": "Materials",
        "SLVR": "Materials",
        "TECK.A": "Materials",
        "TECK.B": "Materials",
        "TUD": "Materials",
        "WEF": "Materials",
        "WRLG": "Materials",
        # --- Utilities ------------------------------------------------------
        "CPX": "Utilities",
        "FTS": "Utilities",
        "H": "Utilities",
        "MXG": "Utilities",
        "NPI": "Utilities",
        "PBK": "Utilities",
        "TA": "Utilities",
        # --- Industrials ----------------------------------------------------
        "WCN": "Industrials",
        "WM": "Industrials",
        # --- Information Technology -----------------------------------------
        "AAPL": "Information Technology",
        "CSU": "Information Technology",
        "INFY": "Information Technology",
        "NOW": "Information Technology",
        "SHOP": "Information Technology",
        # --- Health Care ----------------------------------------------------
        "GUTS": "Health Care",
        "KITS": "Health Care",
        "WELL": "Health Care",
        # --- Consumer -------------------------------------------------------
        "AMZN": "Consumer Discretionary",
        "DOL": "Consumer Discretionary",
        "ATD": "Consumer Staples",
        # --- Real Estate ----------------------------------------------------
        "CAR.UN": "Real Estate",
        "INO.UN": "Real Estate",
        "LAND": "Real Estate",
        "MEQ": "Real Estate",
        # --- Non-GICS buckets -----------------------------------------------
        "CORN": "Commodities",
    }
)
