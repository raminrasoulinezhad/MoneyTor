"""Tests for the config & secrets layer (Phase 2)."""

from __future__ import annotations

import logging

import pytest

from moneytor.config import (
    ConfigError,
    RedactionFilter,
    Secret,
    load_settings,
    setup_logging,
)
from moneytor.domain import Currency

# --------------------------------------------------------------------------- #
# Secret
# --------------------------------------------------------------------------- #


def test_secret_never_discloses_in_text_representations() -> None:
    secret = Secret("super-secret-token")
    assert "super-secret-token" not in repr(secret)
    assert "super-secret-token" not in str(secret)
    assert "super-secret-token" not in f"{secret}"
    assert secret.reveal() == "super-secret-token"


# --------------------------------------------------------------------------- #
# load_settings — happy paths
# --------------------------------------------------------------------------- #


def test_defaults_when_environment_is_empty() -> None:
    settings = load_settings(env_file=None, environ={})
    assert settings.log_level == "INFO"
    assert settings.display_currency is Currency.CAD
    assert settings.fx_provider == "static"
    assert settings.people == ()
    assert settings.app_password is None  # ungated when unset


def test_app_password_loaded_and_redacted() -> None:
    settings = load_settings(env_file=None, environ={"MONEYTOR_APP_PASSWORD": "5205"})
    assert settings.app_password is not None
    assert settings.app_password.reveal() == "5205"
    # Included in the redaction set so it never leaks into logs.
    assert "5205" in settings.secret_values()


def test_loads_full_person_credentials() -> None:
    settings = load_settings(
        env_file=None,
        environ={
            "MONEYTOR_DISPLAY_CURRENCY": "usd",
            "MONEYTOR_FX_API_KEY": "fx-key",
            "MONEYTOR__ramin__QUESTRADE_REFRESH_TOKEN": "qt-token",
            "MONEYTOR__ramin__WEALTHSIMPLE_EMAIL": "r@example.com",
            "MONEYTOR__ramin__WEALTHSIMPLE_PASSWORD": "ws-pass",
        },
    )
    assert settings.display_currency is Currency.USD
    assert settings.fx_api_key is not None and settings.fx_api_key.reveal() == "fx-key"
    assert len(settings.people) == 1
    person = settings.people[0]
    assert person.person_id == "ramin"
    assert person.wealthsimple_email == "r@example.com"
    assert person.wealthsimple_password is not None
    assert person.wealthsimple_password.reveal() == "ws-pass"
    assert set(settings.secret_values()) == {"fx-key", "qt-token", "ws-pass"}


def test_loads_from_env_file(tmp_path) -> None:
    env = tmp_path / ".env"
    env.write_text("MONEYTOR_DISPLAY_CURRENCY=USD\nMONEYTOR__alex__QUESTRADE_REFRESH_TOKEN=tok\n")
    settings = load_settings(env_file=env, environ={})
    assert settings.display_currency is Currency.USD
    assert settings.people[0].person_id == "alex"


def test_people_are_sorted_deterministically() -> None:
    settings = load_settings(
        env_file=None,
        environ={
            "MONEYTOR__zoe__QUESTRADE_REFRESH_TOKEN": "z",
            "MONEYTOR__amy__QUESTRADE_REFRESH_TOKEN": "a",
        },
    )
    assert [p.person_id for p in settings.people] == ["amy", "zoe"]


# --------------------------------------------------------------------------- #
# load_settings — error paths (fail fast with clear messages)
# --------------------------------------------------------------------------- #


def test_invalid_currency_raises() -> None:
    with pytest.raises(ConfigError, match="MONEYTOR_DISPLAY_CURRENCY"):
        load_settings(env_file=None, environ={"MONEYTOR_DISPLAY_CURRENCY": "EUR"})


def test_invalid_log_level_raises() -> None:
    with pytest.raises(ConfigError, match="MONEYTOR_LOG_LEVEL"):
        load_settings(env_file=None, environ={"MONEYTOR_LOG_LEVEL": "LOUD"})


def test_partial_wealthsimple_credentials_raise() -> None:
    with pytest.raises(ConfigError, match="WEALTHSIMPLE_PASSWORD"):
        load_settings(
            env_file=None,
            environ={"MONEYTOR__ramin__WEALTHSIMPLE_EMAIL": "r@example.com"},
        )


def test_person_with_no_usable_credentials_raises() -> None:
    # A malformed-but-known structure: person namespace present yet empty of
    # recognised fields is impossible, so use an unknown field instead.
    with pytest.raises(ConfigError, match="Unknown credential field"):
        load_settings(
            env_file=None,
            environ={"MONEYTOR__ramin__ROBINHOOD_TOKEN": "x"},
        )


def test_malformed_credential_key_raises() -> None:
    with pytest.raises(ConfigError, match="Malformed credential key"):
        load_settings(env_file=None, environ={"MONEYTOR__ramin": "x"})


# --------------------------------------------------------------------------- #
# RedactionFilter / setup_logging
# --------------------------------------------------------------------------- #


def test_redaction_filter_scrubs_secret_substrings() -> None:
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="auth failed for token=%s",
        args=("hunter2",),
        exc_info=None,
    )
    RedactionFilter(["hunter2"]).filter(record)
    assert "hunter2" not in record.getMessage()
    assert "***" in record.getMessage()


def test_setup_logging_emits_redacted_output(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(level="INFO", secrets=["topsecret"])
    logging.getLogger("test").info("leaking topsecret here")
    err = capsys.readouterr().err
    assert "topsecret" not in err
    assert "***" in err
