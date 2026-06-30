# MoneyTor

**MoneyTor** is your personal & family financial **cockpit**. It connects to your
Canadian brokerage accounts (Wealthsimple and Questrade), brings every person's
holdings into one place, converts everything to a single currency, and shows it
all on a clean dashboard with charts — plus exportable PDF and Markdown reports.

> Developers: see [`DEVELOPERS_README.md`](./DEVELOPERS_README.md) for the
> project layout, testing, and contribution guide.

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
charts, and export reports.

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
