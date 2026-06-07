# CLAUDE.md — MoneyTor Project Guidelines

## Project Overview
**MoneyTor** is a personal and family financial aggregation application designed to serve as a high-performance, single "cockpit" dashboard. It securely aggregates assets, stock holdings, cash, and GICs across multiple individuals and Canadian brokerages.

### Core Features
- **Multi-Person & Multi-Account Support:** Track financial portfolios for an entire family. Each person can have unique credentials for supported institutions, with multiple underlying accounts (e.g., TFSA, RRSP, Spousal RRSP, Margin, Managed accounts).
- **Supported Institutions:** Wealthsimple and Questrade (designed to be easily extendable to other Canadian institutions).
- **Aggregation Engine:** Normalizes disparate brokerage data. Merges identical assets across different stock exchanges into unified holdings, utilizing automated or file-based mapping and handling CAD/USD currency conversions dynamically.
- **Reporting & Analytics:** Generates multi-currency portfolio analysis, interactive data visualizations (including portfolio distribution pie charts), and exports reports in PDF and Markdown formats. 

---

## Technical Stack
- **Environment & Dependency Management:** `uv` (replacing traditional pip/venv)
- **Language:** Python (targeting Python 3.14 features and strict type hinting)
- **GUI Framework:** PySide6 (PyQt6) or CustomTkinter paired with a modern UI widget library (e.g., `QFluentWidgets`) for a native, hardware-accelerated fluid experience.
- **Data Visualization:** `Plotly` (rendered via web view) or highly styled `PyQtGraph` for smooth, GPU-accelerated interactive charts.
- **Configuration & Secrets:** `pyproject.toml` for dependencies; `.env` file for secure storage of credentials, API tokens, and session keys.

---

## GUI & Visual Standards (SaaS Dashboard Aesthetic)
To ensure the interface looks modern, premium, and clean, all UI code must adhere to the following design system:

### 1. Color Palette & Theming
- **Dynamic Theme Support:** Full, seamless dark mode and light mode toggle.
- **Dark Mode Palette:** Deep slate/charcoal backgrounds (avoid pure `#000000`), crisp white headers, and muted gray secondary text.
- **Accent Colors:** Use a refined primary color (e.g., emerald green or deep indigo) for interactive states, semantic green for positive daily returns, and a soft red for losses.

### 2. Layout & Typography
- **The Cockpit Layout:** 
  - **Left Sidebar:** Collapsible panel containing the family checklist (toggle individuals on/off) and account tree-view (toggle TFSA, RRSP, etc.).
  - **Main Dashboard:** Dynamic grid layout featuring high-level KPI cards at the top, a large main chart section in the center, and a detailed holdings table at the bottom.
- **Spacing & Radii:** Maintain generous padding (16px to 24px) between elements to prevent data crowding. All cards, buttons, and modal windows must have elegant rounded corners (8px to 12px border-radius).
- **Typography:** Enforce clean, highly readable sans-serif fonts (e.g., Segoe UI, Inter, or San Francisco) with distinct font-weight hierarchy between metric numbers and helper labels.

### 3. Interactive Widgets & Visual Polish
- **KPI Cards:** Feature total portfolio value, 24h change, and asset allocation percentages in large, bold fonts with glassmorphism or subtle drop shadows.
- **Smooth Transitions:** Implement subtle hover effects on buttons, checkboxes, and table rows to make the UI feel responsive and tactile.
- **Loading States:** Use animated skeleton loaders or sleek infinite progress rings while fetching API data from Wealthsimple or Questrade, ensuring the GUI never freezes.
- **Holdings Table:** Format currency values perfectly (e.g., `$1,234.56 CAD`), right-align numerical columns, and use clean zebra-striping with thin, elegant borders.

---

## Build & Test Commands

### Environment Setup & Run
* **Sync dependencies:** `uv sync`
* **Launch the GUI application:** `uv run python src/main.py`

### Testing
* **Run all tests:** `uv run pytest`
* **Run tests with coverage:** `uv run pytest --cov`

### Linting & Formatting
The project enforces code quality using pre-commit hooks featuring `Ruff` and supporting linters:
* **Run linter & formatter (Ruff):** `uv run ruff check --fix` and `uv run ruff format`
* **Legacy/Deep Linting Checks:** `uv run pylint src/`

---

## Code Style & Conventions

### Architecture
- **Modular Design:** Keep API fetching, data aggregation, math/currency conversion, and GUI presentation strictly decoupled.
- **Functional Paradigm:** Prefer a functional programming style where applicable (immutability, pure transformation functions for financial data aggregation).

### Typing & Quality
- **Strict Typing:** Always use explicit Python type hints (`from typing import...`). Do not use the `Any` type without a direct, well-justified code comment.
- **Error Handling:** Never use bare `except:`. Always catch explicit exceptions, log meaningful contextual errors, and handle connection failures gracefully without crashing the GUI.

### Data Handling
- **Security First:** Never hardcode passwords or API tokens. Access them strictly via an insulated configuration module reading from `.env`.
- **Currency & Precision:** Use precise decimals for financial calculations; avoid floating-point errors during CAD/USD conversions.

---

## AI Workflow Rules
1. **Test-Driven Modifications:** ALWAYS run the full test suite (`pytest`) and type-checker after making structural or architectural changes.
2. **Review Before Coding:** Present a step-by-step structural plan for approval before generating large blocks of new code or adding complex UI elements.
3. **Dependency Check:** Before introducing a new external package or API client, check `pyproject.toml` to verify if an existing tool can handle the task.
