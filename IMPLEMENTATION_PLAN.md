# MoneyTor — Implementation Plan

> A step-by-step build reference for implementing the MoneyTor financial
> aggregation cockpit. Follow phases in order. Each step lists its
> **deliverables**, **acceptance criteria**, and **tests** so progress is
> verifiable. This document is the source of truth for *what to build next*.

---

## 0. Guiding Principles (from `CLAUDE.md`)

- **Decoupled layers:** API fetching ▸ aggregation ▸ math/currency ▸ presentation. No layer reaches across boundaries.
- **Functional core, imperative shell:** pure transformation functions for all financial math; side effects (I/O, network, GUI) isolated at the edges.
- **Strict typing:** explicit type hints everywhere. `Any` only with a justifying comment.
- **Security first:** no hardcoded secrets — all credentials via `.env` through one insulated config module.
- **Precise money:** `Decimal` for every monetary value and FX conversion. Never `float`.
- **Graceful errors:** no bare `except`; catch explicit exceptions, log context, never crash the GUI.
- **Test-driven structural changes:** run `uv run pytest` + type-checker after architectural changes.

---

## 1. Prerequisites & Environment (BLOCKER — do first)

| Item | Current state | Action |
| --- | --- | --- |
| `uv` package manager | **Not installed** | Install via `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python 3.14 | Only 3.12.3 present | `uv python install 3.14` (uv manages the toolchain) |
| Git repo | Initialized, branch `master`, no commits | Keep; first commit will include scaffold |

**Decision needed:** CLAUDE.md says Python 3.14. If 3.14 features aren't required immediately, we can pin `>=3.12` to unblock dev and bump later. *Recommend pinning `requires-python = ">=3.12"` and using 3.14 in CI once stable.*

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        GUI (PySide6)                          │  presentation
│   Sidebar · KPI cards · Charts (Plotly) · Holdings table      │
└───────────────▲───────────────────────────────▲──────────────┘
                │ view-models (plain dataclasses) │
┌───────────────┴───────────────────────────────┴──────────────┐
│                     Aggregation Engine                        │  pure / functional
│   normalize ▸ merge identical assets ▸ FX convert ▸ rollups   │
└───────────────▲───────────────────────────────▲──────────────┘
                │ normalized domain models        │
┌───────────────┴──────────┐        ┌─────────────┴──────────────┐
│   Connectors (per broker) │        │   FX / Currency service     │  imperative shell
│   Wealthsimple, Questrade │        │   rate fetch + Decimal conv │
└───────────────▲──────────┘        └─────────────────────────────┘
                │
┌───────────────┴───────────────────────────────────────────────┐
│      Config / Secrets  (.env loader)  ·  Logging  ·  Cache      │  infrastructure
└────────────────────────────────────────────────────────────────┘
```

### Proposed package layout
```
moneytor/
├── pyproject.toml
├── .env.example                 # template; real .env is gitignored
├── .gitignore
├── .pre-commit-config.yaml
├── README.md
├── IMPLEMENTATION_PLAN.md
├── src/
│   ├── main.py                  # GUI entrypoint
│   └── moneytor/
│       ├── __init__.py
│       ├── config/              # .env loader, settings dataclasses
│       ├── domain/              # core models: Person, Account, Holding, Money
│       ├── connectors/          # base + wealthsimple + questrade
│       ├── fx/                  # currency conversion service
│       ├── aggregation/         # pure transforms: normalize, merge, rollup
│       ├── reporting/           # PDF / Markdown exporters
│       ├── persistence/         # local cache, asset-mapping files
│       └── ui/                  # PySide6 widgets, theme, view-models
│           ├── theme/
│           ├── widgets/
│           └── views/
└── tests/
    ├── conftest.py
    ├── fixtures/                # sample broker payloads (sanitized)
    ├── unit/
    └── integration/
```

---

## 3. Domain Model (the contract everything depends on)

Define these first — every other layer consumes them.

| Model | Key fields | Notes |
| --- | --- | --- |
| `Money` | `amount: Decimal`, `currency: Currency` | immutable; arithmetic guarded by currency match |
| `Currency` | enum `CAD`, `USD` | extendable |
| `Person` | `id`, `name`, `accounts: list[Account]` | top of the family tree |
| `Account` | `id`, `person_id`, `institution`, `account_type`, `holdings`, `cash: Money` | `account_type`: TFSA/RRSP/Spousal/Margin/Managed/GIC |
| `Institution` | enum `WEALTHSIMPLE`, `QUESTRADE` | |
| `Holding` | `symbol`, `exchange`, `quantity: Decimal`, `book_value: Money`, `market_value: Money`, `asset_class` | |
| `UnifiedHolding` | merged view across exchanges; `sources: list[Holding]` | aggregation output |
| `PortfolioSnapshot` | timestamp, totals by currency, allocations, per-person rollups | top-level view-model |

**Acceptance:** all models are frozen dataclasses with full type hints; `Money` arithmetic raises on currency mismatch; 100% unit-tested.

---

## 4. Phased Build Plan

### Phase 1 — Project Scaffold & Tooling
**Goal:** a runnable, lint-clean, test-green empty project.

Steps:
1. `uv init` → create `pyproject.toml` with metadata, `requires-python`.
2. Add dev deps: `pytest`, `pytest-cov`, `ruff`, `pylint`, `mypy` (or `pyright`).
3. Add runtime deps incrementally (don't front-load): `python-dotenv`, `pydantic` *(evaluate vs. plain dataclasses)*, `httpx`.
4. Create `.gitignore` (`.env`, `.venv`, `__pycache__`, `*.pyc`, build artifacts, cache dir).
5. Create `.env.example` documenting every required key.
6. Configure `ruff` + `pylint` + formatter in `pyproject.toml`.
7. Add `.pre-commit-config.yaml` (ruff check, ruff format, trailing-whitespace).
8. Create `src/` package skeleton with empty `__init__.py` files.
9. Add one trivial passing test to prove the harness works.

**Acceptance:** `uv sync`, `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` all pass. First git commit.

---

### Phase 2 — Config & Secrets Layer
**Goal:** insulated, typed access to all secrets/settings.

Steps:
1. `config/settings.py`: typed settings object loaded from `.env` (fail fast with clear error if a required key is missing).
2. Per-person credential schema (multiple people, each with per-institution creds).
3. Logging setup (structured, no secrets in logs — add a redaction filter).

**Acceptance:** unit tests for missing-key errors and successful load from a temp `.env`; secrets never appear in `repr`/logs.

---

### Phase 3 — Domain Models & Money/FX Core (pure)
**Goal:** the functional financial core.

Steps:
1. Implement all `domain/` models from §3 as frozen dataclasses.
2. Implement `Money` with `Decimal`, currency-safe `+`, `-`, scalar `*`, comparison, formatting (`$1,234.56 CAD`).
3. `fx/` service interface (`get_rate(base, quote, at) -> Decimal`) with an injectable provider; start with a static/cached provider, add live fetch later.
4. Pure conversion helpers: `convert(money, target_currency, rate) -> Money`.

**Acceptance:** exhaustive unit tests incl. rounding, half-even banker's rounding policy, mismatch errors. **Zero floats** in money paths (add a lint/test guard).

---

### Phase 4 — Connector Framework + Mock Connector
**Goal:** broker-agnostic fetch contract, testable without real credentials.

Steps:
1. `connectors/base.py`: `Connector` protocol → `authenticate()`, `fetch_accounts() -> list[Account]`, returns normalized domain models.
2. `MockConnector` returning fixture data (drives all downstream dev without hitting real APIs).
3. Define sanitized fixture payloads under `tests/fixtures/`.
4. Robust error types: `AuthError`, `RateLimitError`, `ConnectorError` — never bubble raw network exceptions to GUI.

**Acceptance:** integration test: `MockConnector` → domain models; error paths covered.

---

### Phase 5 — Aggregation Engine (pure)
**Goal:** normalize + merge + roll up into a `PortfolioSnapshot`.

Steps:
1. Normalize raw holdings into canonical symbols (handle exchange suffixes, e.g. `SHOP.TO` vs `SHOP`).
2. Asset-mapping resolution: automated rules + file-based overrides (`persistence/asset_map.*`).
3. Merge identical assets across exchanges → `UnifiedHolding` (sum quantity, weighted book value, FX-normalized market value).
4. Currency rollups (per-currency and a chosen display currency).
5. Compute allocations (%), per-person and per-account rollups, 24h change.

**Acceptance:** property-based + example tests; merging is associative/commutative; totals reconcile to source within rounding tolerance.

---

### Phase 6 — GUI Foundation (PySide6)
**Goal:** the cockpit shell with theme system, fed by mock data.

Steps:
1. `ui/theme/`: design tokens (colors, spacing, radii, fonts) → dark + light QSS, runtime toggle.
2. `main.py`: main window, `QStackedWidget`/grid cockpit layout.
3. Collapsible **left sidebar**: family checklist + account tree-view (toggle people/accounts).
4. **KPI cards** (total value, 24h change, allocation %) with shadows/glassmorphism.
5. **Holdings table**: right-aligned numerics, currency formatting, zebra striping, hover.
6. Async data loading with skeleton loaders / progress ring — GUI never freezes (use `QThread`/`asyncio` worker).

**Acceptance:** app launches via `uv run python src/main.py`, renders mock portfolio, theme toggles live, sidebar filters update the dashboard. No blocking calls on the UI thread.

---

### Phase 7 — Charts (Plotly via web view)
**Goal:** interactive portfolio distribution + trend visuals.

Steps:
1. Add `plotly` + `PySide6` web view (or PyQtGraph fallback — decide based on perf).
2. Portfolio distribution pie/donut (by asset, by account, by person — toggleable).
3. Main chart section wired to filtered snapshot.

**Acceptance:** charts re-render on sidebar filter changes; styled to match theme.

---

### Phase 8 — Real Connectors
**Goal:** live Wealthsimple + Questrade data.

Steps:
1. Questrade connector (OAuth refresh-token flow; token persistence).
2. Wealthsimple connector (session/2FA handling as required).
3. Retry/backoff, rate-limit handling, graceful degradation per person/account.
4. Map live payloads → domain models via the same contract as `MockConnector`.

**Acceptance:** integration tests against recorded payloads (VCR-style); manual smoke test with real creds documented in README. Secrets only from `.env`.

---

### Phase 9 — Reporting & Export
**Goal:** PDF + Markdown reports.

Steps:
1. Markdown report generator from `PortfolioSnapshot`.
2. PDF exporter (e.g. via HTML→PDF or reportlab — pick during phase).
3. Include charts/tables; multi-currency sections.

**Acceptance:** golden-file tests for Markdown; PDF generates without error and opens.

---

### Phase 10 — Caching, Polish & Hardening
**Goal:** production-feel reliability.

Steps:
1. Local snapshot cache (offline view, faster cold start).
2. Refresh scheduling / manual refresh button with last-updated indicator.
3. Error toasts/banners for connector failures (per CLAUDE.md graceful handling).
4. Performance pass; finalize coverage targets; full lint/type clean.

**Acceptance:** `uv run pytest --cov` meets target; `ruff`, `pylint`, type-checker clean; app resilient to a single broker being down.

---

## 5. Cross-Cutting Concerns (apply in every phase)

- **Testing:** unit tests for pure code; integration tests behind mock/recorded payloads; never require real creds in CI.
- **Security:** `.env` gitignored; redaction in logs; no secrets in fixtures, snapshots, or reports.
- **Money:** `Decimal` only; centralized rounding policy; FX conversions auditable.
- **Decoupling:** GUI imports view-models, never connectors directly; aggregation never imports GUI.
- **Docs:** keep this plan + README current; check items off as completed.

---

## 6. Open Decisions (resolve before/at relevant phase)

1. **Python version:** pin `>=3.12` now and target 3.14 in CI? *(recommended)*
2. **Models:** plain frozen dataclasses vs. Pydantic? *(dataclasses for the pure core; Pydantic only at connector boundary if validation pays off)*
3. **Charts:** Plotly-in-webview vs. PyQtGraph? *(start Plotly for richness; revisit if perf suffers)*
4. **Type-checker:** `mypy` vs. `pyright`? *(pick one, run in CI)*
5. **Async strategy:** `QThread` workers vs. `asyncio` + `qasync`? *(affects Phase 6)*

---

## 7. Suggested Milestones / Commit Cadence

- **M1:** Phases 1–3 → typed pure core, green tests. *(foundation)*
- **M2:** Phases 4–5 → end-to-end mock data → aggregated snapshot.
- **M3:** Phases 6–7 → cockpit GUI rendering mock portfolio with charts.
- **M4:** Phase 8 → live broker data.
- **M5:** Phases 9–10 → reporting, caching, hardening → v1.0.

---

*Next action: get approval on §6 decisions, then execute **Phase 1**.*
