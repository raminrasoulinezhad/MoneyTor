# MoneyTor — developer guide

Financial aggregation cockpit for Canadian brokerages. See
[`README.md`](./README.md) to install and run it; this file covers the code.

---

## Commands

```bash
uv sync                       # create venv + install deps
uv run python src/main.py     # launch the app

uv run pytest                 # tests
uv run pytest --cov           # tests with coverage
uv run ruff check --fix       # lint + autofix
uv run ruff format            # format
uv run mypy src               # type-check
uv run pylint src/            # deep lint
uv run pre-commit run -a      # everything the hooks enforce
```

Qt needs a display. Headless (CI, SSH):
`QT_QPA_PLATFORM=offscreen uv run pytest`.

---

## Layout

```
src/
  main.py                GUI entrypoint
  moneytor/
    config/              .env loader, typed settings, log redaction
    domain/              Person, Account, Holding, Money, Currency
    connectors/          Wealthsimple, Questrade, mock + error types
    fx/                  currency conversion
    aggregation/         pure transforms: normalize, merge, roll up
    reporting/           PDF / Markdown exporters
    persistence/         snapshot cache, token store
    ui/                  PySide6 widgets, theme, view-models
    autostart.py         launch-at-login (XDG / LaunchAgent / HKCU Run)
tests/
  unit/                  pure logic
  integration/           connectors and GUI
  fixtures/              sanitized broker payloads
```

---

## Architecture

Data flows one way. Nothing skips a layer, and nothing below the UI imports Qt.

```
connectors ─┐
            ├─▸ aggregation (pure) ─▸ view-models ─▸ PySide6 UI
fx ─────────┘
```

- **Functional core, imperative shell** — money math is pure and total; I/O, network, and Qt live at the edges
- **`Decimal` everywhere** for money. Never `float`
- **Frozen dataclasses** for domain models
- **Connectors return domain models**, never raw payloads, and raise `ConnectorError` subclasses rather than network exceptions
- **The UI imports view-models**, never connectors

---

## Conventions

- Explicit type hints. `Any` only with a comment saying why
- No bare `except`. Catch specific exceptions, log context, never crash the GUI
- Secrets only via `.env` through `config/` — never hardcoded, never logged
  (`config/logging.py` redacts them)
- Every `.py` and `.sh` file carries the Apache-2.0 SPDX header; the
  `insert-license` hook maintains it

---

## Versioning

`src/moneytor/__init__.py` holds `__version__` and is the **only** place the
version lives — `pyproject.toml` reads it from there. Bump it per semver:

| Bump | When |
| --- | --- |
| major | breaking change |
| minor | new feature |
| patch | fix |

---

## Testing

- Unit tests for pure code; integration tests against fixtures and a mock connector
- Real credentials are never needed — and never in CI
- GUI tests run offscreen via `pytest-qt`; `conftest.py` sets `QT_QPA_PLATFORM`
- Autostart tests write to `tmp_path` and a fake registry, so they never touch
  your real login session

---

## Security

- `.env` is gitignored; `.env.example` is the committed template
- `gitleaks` runs as a pre-commit hook **and** over full history in CI
  (`.github/workflows/secret-scan.yml`) — a local hook can be skipped, CI cannot
- No secrets in fixtures, snapshots, logs, or reports
