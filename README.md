<p align="center">
  <img src="docs/images/logo.png" alt="MoneyTor logo" width="420">
</p>

# MoneyTor

**MoneyTor** is your personal & family financial **cockpit**. It connects to your
Canadian brokerage accounts (Wealthsimple and Questrade), brings every person's
holdings into one place, converts everything to a single currency, and shows it
all on a clean dashboard with charts — plus exportable PDF and Markdown reports.

> Developers: see [`DEVELOPERS_README.md`](./DEVELOPERS_README.md) for the
> project layout, testing, and contribution guide.

---

## A look at the cockpit

![MoneyTor dashboard](docs/images/app_screenshot.png)

The dashboard puts everything on one screen:

- **KPI cards** (left) — total portfolio value, estimated annual dividends, GIC
  interest, combined income, holdings count, and your top position.
- **Two charts** (center) — each picks its own view independently, so you can
  show holdings on one side and sector allocation on the other.
- **Holdings table** (bottom) — every position merged across accounts and
  brokerages, with allocation %, distance from the 52-week high, and unit price.
- **Sidebar** (left) — toggle individual people and accounts on and off.
- **⚙ Settings** (top right) — everything you can change lives behind this one
  button; see [Settings](#settings) below.

### Why are the numbers hidden behind `••••••`?

That screenshot was taken with **private mode** switched on. Private mode is a
one-click privacy screen for when someone is looking over your shoulder or
you're sharing your display. It masks every dollar figure — the total value, the
dividend / GIC / income estimates, and each holding's share count and market
value — while leaving non-sensitive context (allocation %, sectors, unit prices)
visible.

Turning private mode **on** is instant. Turning it **off** (revealing the
numbers again) requires your password, so a bystander can't simply switch it
back. See [Set up your accounts](#2-set-up-your-accounts-env) for the password.

### Settings

The **⚙ Settings** button in the top-right corner opens a panel over the
dashboard with four things:

| Setting | What it does |
| --- | --- |
| **Theme** | Switch between the dark and light themes. |
| **Private mode** | Hide every dollar figure (see above). |
| **Open MoneyTor when I log in** | Start MoneyTor automatically when you sign in to your computer. |
| **Export report…** | Write a PDF and a Markdown copy of the full portfolio. |

**Open MoneyTor when I log in** registers MoneyTor with whatever your operating
system already uses for startup apps — an autostart entry on Linux
(`~/.config/autostart/moneytor.desktop`), a login item on macOS
(`~/Library/LaunchAgents/io.moneytor.app.plist`), or a startup entry on Windows.
Unticking it removes that entry again. Because MoneyTor reads the real entry
rather than remembering its own answer, the tick stays accurate even if you
later turn MoneyTor off through your system's own startup-apps settings.

> The app still starts locked, so it will sit at the password gate until you
> unlock it — logging in doesn't expose your portfolio.

---

## 1. Install

MoneyTor uses [**uv**](https://docs.astral.sh/uv/) to manage Python and all
dependencies for you — you don't need to install Python yourself.

```bash
# 1. Install uv (one time)
#    macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
#    Windows (PowerShell):
#    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Get MoneyTor and install everything
git clone <repository-url> moneytor
cd moneytor
uv sync
```

That's it — `uv sync` downloads the correct Python version and every package
MoneyTor needs into a local environment.

---

## 2. Set up your accounts (`.env`)

Your account credentials live in a file called `.env`. This file stays on your
computer and is **never** shared or committed.

**Step 1 — create your `.env` from the template:**

```bash
cp .env.example .env
```

**Step 2 — open `.env` in any text editor and fill in your details.**

### General settings

| Setting | What it does | Example |
| --- | --- | --- |
| `MONEYTOR_DISPLAY_CURRENCY` | Currency everything is shown in | `CAD` or `USD` |
| `MONEYTOR_LOG_LEVEL` | How chatty the logs are | `INFO` |
| `MONEYTOR_APP_PASSWORD` | Optional password asked on launch. Leave blank for no lock. | `my-secret` |

### Your accounts

Credentials are entered **per person**. Replace `PERSON1` with a short name for
each person (e.g. `RAMIN`, `ALEX`). You can add as many people as you like.

**Wealthsimple** — needs your email and password:

```dotenv
MONEYTOR__PERSON1__WEALTHSIMPLE_EMAIL=you@example.com
MONEYTOR__PERSON1__WEALTHSIMPLE_PASSWORD=your-password
```

> On first connection Wealthsimple may text you a one-time code (2FA).
> MoneyTor will prompt you to enter it in the app.

**Questrade** — needs a personal refresh token. Generate one in Questrade under
**App Hub → Register a personal app**, then paste the refresh token:

```dotenv
MONEYTOR__PERSON1__QUESTRADE_REFRESH_TOKEN=your-refresh-token
```

A person can have Wealthsimple, Questrade, or both. A second person just gets
their own lines:

```dotenv
MONEYTOR__PERSON2__WEALTHSIMPLE_EMAIL=partner@example.com
MONEYTOR__PERSON2__WEALTHSIMPLE_PASSWORD=their-password
```

> 🔒 **Keep `.env` private.** It contains your real passwords and tokens. It is
> already excluded from version control — don't share it or paste it anywhere.

---

## 3. Run

```bash
uv run python src/main.py
```

The dashboard opens, connects to your accounts, and shows your combined
portfolio. From there you can toggle people and accounts on/off, explore the
charts, and — via **⚙ Settings** — switch themes, hide values, export reports,
and have MoneyTor open by itself next time you log in.

### Optional: add a desktop icon (Linux)

To launch MoneyTor from your app grid or a desktop shortcut instead of the
terminal:

```bash
./scripts/install-desktop.sh
```

Then press **Super** and type "MoneyTor", or double-click the desktop icon.
To remove it later: `./scripts/install-desktop.sh --uninstall`.

---

## Troubleshooting

- **"command not found: uv"** — restart your terminal after installing uv, or
  follow the path instructions printed by the installer.
- **Login fails / asks for a code** — Wealthsimple uses two-factor auth; enter
  the code it texts you when MoneyTor prompts.
- **A person won't load** — make sure that person has *either* a Questrade
  refresh token *or* both a Wealthsimple email and password (not just one of the
  two).

---

## License

MoneyTor is licensed under the [Apache License, Version 2.0](LICENSE).
Copyright (c) 2026 Seyedramin Rasoulinezhad. See [NOTICE](NOTICE) for the
attribution notice that must accompany redistributions.
