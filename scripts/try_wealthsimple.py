# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Interactive smoke test for the live Wealthsimple connector.

Run it yourself so you can type the 2FA code when prompted:

    uv run python scripts/try_wealthsimple.py

It uses PERSON1's WEALTHSIMPLE_EMAIL / WEALTHSIMPLE_PASSWORD from .env, logs in
(prompting for a 2FA code via the terminal), fetches accounts, and prints a
summary. No secrets are printed. The rotated refresh token is saved to
.cache/tokens.json so future logins skip 2FA until it expires.
"""

from __future__ import annotations

import sys

from moneytor.config.settings import load_settings
from moneytor.connectors.errors import ConnectorError
from moneytor.connectors.wealthsimple import WealthsimpleConnector
from moneytor.persistence.token_store import TokenStore


def main() -> int:
    settings = load_settings()
    creds = next(
        (
            c
            for c in settings.people
            if c.wealthsimple_email is not None and c.wealthsimple_password is not None
        ),
        None,
    )
    if creds is None:
        print("No person has Wealthsimple credentials configured in .env.")
        return 1

    def cli_otp() -> str:
        return input(
            f"Enter the Wealthsimple 2FA code for {creds.wealthsimple_email} "
            f"(person '{creds.person_id}'): "
        ).strip()

    print(f"Logging in to Wealthsimple as {creds.person_id} ({creds.wealthsimple_email}) ...")
    connector = WealthsimpleConnector(
        person_id=creds.person_id,
        email=creds.wealthsimple_email,
        password=creds.wealthsimple_password,
        otp_provider=cli_otp,
        token_store=TokenStore(),
    )

    try:
        connector.authenticate()
        accounts = connector.fetch_accounts()
    except ConnectorError as exc:
        print(f"\nFAILED: {type(exc).__name__}: {exc}")
        return 1

    print(f"\nSuccess — fetched {len(accounts)} account(s):")
    for account in accounts:
        print(
            f"  - {account.account_type.value} {account.id}: "
            f"{len(account.holdings)} holding(s), cash={account.cash}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
