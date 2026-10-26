# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""One company, two tickers: listings to merge into a single holding.

A stock listed in both Canada and the US usually keeps one ticker (``AEM`` on
both), and those merge on their own once the exchange suffix is stripped.
Some don't — Cameco is ``CCO`` on the TSX and ``CCJ`` on the NYSE — so without
this table the same company shows as two rows, splitting its allocation.

Each group's **first** ticker is the one the merged row shows. Write tickers
without an exchange suffix (``CCO``, not ``CCO.TO``).

**Only add listings that are the same share, 1:1.** Merging sums share counts,
so it is wrong for anything that represents a fraction or a multiple of a
share: a US ADR at a ratio (usually a ``…Y`` OTC ticker), or a Canadian CDR. US
OTC ``…F`` tickers are the ordinary shares themselves and are fine. To check a
pair: the Canadian price divided by the US one should be today's USD/CAD rate.
"""

from __future__ import annotations

from typing import Final

EQUIVALENT_LISTINGS: Final[tuple[tuple[str, ...], ...]] = (
    ("CCO", "CCJ"),  # Cameco — TSX, NYSE
    ("FVI", "FSM"),  # Fortuna Mining — TSX, NYSE
    ("ALS", "ATUSF"),  # Altius Minerals — TSX, US OTC
    ("WRLG", "WRLGF"),  # West Red Lake Gold — TSX-V, US OTC
)
