# MoneyTor

A high-performance personal & family financial aggregation **cockpit** for
Canadian brokerages (Wealthsimple, Questrade). It securely aggregates assets,
stock holdings, cash, and GICs across multiple individuals and accounts,
normalizes data into unified holdings, handles CAD/USD conversion, and renders
a modern SaaS-style dashboard with interactive charts and PDF/Markdown reports.

> Build status: **Phase 1 — scaffold** complete. See
> [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) for the full roadmap.

## Quick start

```bash
# Install uv (one time): https://docs.astral.sh/uv/
uv sync                          # create venv + install deps
cp .env.example .env             # then fill in your secrets
uv run python src/main.py        # launch (GUI lands in Phase 6)
```

## Development

```bash
uv run pytest                    # run tests
uv run pytest --cov              # with coverage
uv run ruff check --fix          # lint + autofix
uv run ruff format               # format
uv run mypy                      # type-check
uv run pylint src/               # deep lint
```

## Project layout

```
src/moneytor/
  config/        .env loader, typed settings
  domain/        core models: Person, Account, Holding, Money
  connectors/    broker connectors (Wealthsimple, Questrade) + mock
  fx/            currency conversion service
  aggregation/   pure transforms: normalize, merge, rollup
  reporting/     PDF / Markdown exporters
  persistence/   local cache, asset-mapping files
  ui/            PySide6 widgets, theme, view-models
  autostart.py   launch-at-login backends (XDG / LaunchAgent / HKCU Run)
tests/           unit, integration, fixtures
```

## Security

Never commit secrets. All credentials/tokens live in `.env` (gitignored) and
are accessed only through the insulated config module.
