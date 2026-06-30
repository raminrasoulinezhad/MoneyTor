# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Typed application settings loaded from the environment / ``.env``.

The loader is the single insulated boundary between raw environment variables
and the rest of the app (per CLAUDE.md "Security First"). It fails fast with a
clear :class:`ConfigError` when configuration is missing or malformed.

Per-person credentials use a double-underscore namespace::

    MONEYTOR__<person>__<FIELD>=value

e.g. ``MONEYTOR__ramin__WEALTHSIMPLE_EMAIL=...``. Recognised fields:

    QUESTRADE_REFRESH_TOKEN
    WEALTHSIMPLE_EMAIL
    WEALTHSIMPLE_PASSWORD
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from moneytor.domain.enums import Currency

from .errors import ConfigError
from .secret import Secret

_PREFIX = "MONEYTOR__"
_QUESTRADE_TOKEN = "QUESTRADE_REFRESH_TOKEN"
_WS_EMAIL = "WEALTHSIMPLE_EMAIL"
_WS_PASSWORD = "WEALTHSIMPLE_PASSWORD"
_KNOWN_PERSON_FIELDS = frozenset({_QUESTRADE_TOKEN, _WS_EMAIL, _WS_PASSWORD})

_VALID_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"})


@dataclass(frozen=True)
class PersonCredentials:
    """Credentials for one person across the institutions they use."""

    person_id: str
    questrade_refresh_token: Secret | None = None
    wealthsimple_email: str | None = None
    wealthsimple_password: Secret | None = None

    def secret_values(self) -> list[str]:
        """Revealed secret strings belonging to this person (for redaction)."""
        out: list[str] = []
        if self.questrade_refresh_token is not None:
            out.append(self.questrade_refresh_token.reveal())
        if self.wealthsimple_password is not None:
            out.append(self.wealthsimple_password.reveal())
        return out


@dataclass(frozen=True)
class Settings:
    """Fully-validated application configuration."""

    log_level: str = "INFO"
    display_currency: Currency = Currency.CAD
    fx_provider: str = "static"
    fx_api_key: Secret | None = None
    app_password: Secret | None = None
    people: tuple[PersonCredentials, ...] = field(default_factory=tuple)

    def secret_values(self) -> list[str]:
        """All revealed secret strings in this config (for log redaction)."""
        out: list[str] = []
        if self.fx_api_key is not None:
            out.append(self.fx_api_key.reveal())
        if self.app_password is not None:
            out.append(self.app_password.reveal())
        for person in self.people:
            out.extend(person.secret_values())
        return [s for s in out if s]


def _resolve_env(
    env_file: str | Path | None,
    environ: Mapping[str, str] | None,
) -> dict[str, str]:
    """Merge ``.env`` file values with the process environment.

    Real environment variables take precedence over file values (standard
    dotenv semantics). ``environ`` is injectable for testing.
    """
    base = dict(os.environ if environ is None else environ)
    if env_file is None:
        return base
    path = Path(env_file)
    if not path.exists():
        return base
    file_values = {k: v for k, v in dotenv_values(path).items() if v is not None}
    return {**file_values, **base}


def _parse_person_fields(env: Mapping[str, str]) -> dict[str, dict[str, str]]:
    """Group ``MONEYTOR__<person>__<FIELD>`` keys by person."""
    people: dict[str, dict[str, str]] = {}
    for key, value in env.items():
        if not key.startswith(_PREFIX):
            continue
        parts = key.split("__")
        if len(parts) != 3 or not parts[1] or not parts[2]:
            raise ConfigError(
                f"Malformed credential key {key!r}; expected MONEYTOR__<person>__<FIELD>."
            )
        _, person, fld = parts
        people.setdefault(person.lower(), {})[fld.upper()] = value
    return people


def _build_person(person_id: str, fields: Mapping[str, str]) -> PersonCredentials:
    unknown = set(fields) - _KNOWN_PERSON_FIELDS
    if unknown:
        raise ConfigError(
            f"Unknown credential field(s) for person {person_id!r}: "
            f"{sorted(unknown)}. Known fields: {sorted(_KNOWN_PERSON_FIELDS)}."
        )

    ws_email = fields.get(_WS_EMAIL)
    ws_password = fields.get(_WS_PASSWORD)
    if (ws_email is None) != (ws_password is None):
        missing = _WS_PASSWORD if ws_email is not None else _WS_EMAIL
        raise ConfigError(
            f"Person {person_id!r} has incomplete Wealthsimple credentials; "
            f"missing MONEYTOR__{person_id}__{missing}."
        )

    questrade = fields.get(_QUESTRADE_TOKEN)
    if questrade is None and ws_email is None:
        raise ConfigError(
            f"Person {person_id!r} has no usable credentials; provide a "
            f"Questrade refresh token and/or Wealthsimple email + password."
        )

    return PersonCredentials(
        person_id=person_id,
        questrade_refresh_token=Secret(questrade) if questrade else None,
        wealthsimple_email=ws_email,
        wealthsimple_password=Secret(ws_password) if ws_password else None,
    )


def load_settings(
    env_file: str | Path | None = ".env",
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Load and validate :class:`Settings`.

    Args:
        env_file: Path to a ``.env`` file, or ``None`` to skip file loading.
            Missing files are ignored (environment-only configuration is valid).
        environ: Environment mapping to use instead of ``os.environ`` (testing).

    Raises:
        ConfigError: If any value is missing, malformed, or invalid.
    """
    env = _resolve_env(env_file, environ)

    log_level = env.get("MONEYTOR_LOG_LEVEL", "INFO").upper()
    if log_level not in _VALID_LOG_LEVELS:
        raise ConfigError(
            f"Invalid MONEYTOR_LOG_LEVEL {log_level!r}; expected one of "
            f"{sorted(_VALID_LOG_LEVELS)}."
        )

    raw_currency = env.get("MONEYTOR_DISPLAY_CURRENCY", Currency.CAD.value)
    try:
        display_currency = Currency(raw_currency.upper())
    except ValueError as exc:
        valid = [c.value for c in Currency]
        raise ConfigError(
            f"Invalid MONEYTOR_DISPLAY_CURRENCY {raw_currency!r}; expected one of {valid}."
        ) from exc

    fx_provider = env.get("MONEYTOR_FX_PROVIDER", "static")
    fx_api_key_raw = env.get("MONEYTOR_FX_API_KEY")
    app_password_raw = env.get("MONEYTOR_APP_PASSWORD")

    person_fields = _parse_person_fields(env)
    people = tuple(_build_person(pid, fields) for pid, fields in sorted(person_fields.items()))

    settings = Settings(
        log_level=log_level,
        display_currency=display_currency,
        fx_provider=fx_provider,
        fx_api_key=Secret(fx_api_key_raw) if fx_api_key_raw else None,
        app_password=Secret(app_password_raw) if app_password_raw else None,
        people=people,
    )
    logging.getLogger(__name__).debug(
        "Loaded settings: currency=%s provider=%s people=%d",
        settings.display_currency.value,
        settings.fx_provider,
        len(settings.people),
    )
    return settings
