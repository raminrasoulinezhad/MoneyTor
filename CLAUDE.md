# CLAUDE.md — MoneyTor project guidelines

**MoneyTor** aggregates a family's assets, holdings, cash, and GICs across
Canadian brokerages into one dashboard.

Read [`DEVELOPERS_README.md`](./DEVELOPERS_README.md) first — it has the
commands, layout, architecture, and versioning rules. This file adds the design
system and the working rules those docs don't cover.

---

## Stack

| Concern | Choice |
| --- | --- |
| Python | `>=3.12`, strict type hints |
| Packaging | `uv` (not pip/venv) |
| GUI | PySide6 |
| Charts | Plotly, rendered in a web view |
| Config | `pyproject.toml` for deps, `.env` for secrets |

Adding a dependency? Check `pyproject.toml` first — prefer what's already there.

---

## Design system

The UI should read as a modern SaaS dashboard.

**Color**
- Dark and light themes, both fully supported, toggled at runtime
- Dark mode on deep slate/charcoal — never pure `#000000`
- One accent (emerald) for interaction; semantic green for gains, soft red for losses
- All colors come from `ui/theme/tokens.py` — never hardcode a hex in a widget

**Layout**
- Left sidebar: family checklist + account tree
- Main area: KPI cards on top, charts in the middle, holdings table below
- 16–24px padding between elements; 8–12px corner radius
- Clean sans-serif, with clear weight hierarchy between metrics and labels

**Polish**
- Hover states on buttons, checkboxes, and table rows
- Progress bar or skeleton while fetching — the GUI never freezes
- Currency formatted in full (`$1,234.56 CAD`), numeric columns right-aligned,
  zebra striping with thin borders

---

## Rules

- **Decoupled layers.** API fetch ▸ aggregation ▸ money math ▸ presentation. No layer reaches across
- **Pure core.** Financial transforms are pure functions; side effects at the edges
- **`Decimal` only** for money. Never `float`
- **Strict typing.** `Any` needs a comment justifying it
- **No bare `except`.** Catch specific exceptions, log context, keep the GUI alive
- **Secrets from `.env` only**, through `config/`. Never hardcoded, never logged
- **Bump `__version__`** in `src/moneytor/__init__.py` per semver on every change

---

## Workflow

1. **Plan before large changes** — present the structure for approval before generating a big block of new code or a complex widget
2. **Test after structural changes** — `uv run pytest` and `uv run mypy src`, every time
3. **Keep docs true** — if behaviour changes, the README changes in the same commit
