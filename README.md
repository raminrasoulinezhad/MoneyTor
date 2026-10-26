<p align="center">
  <img src="docs/images/logo.png" alt="MoneyTor logo" width="420">
</p>

# MoneyTor

Your family's whole portfolio on one screen.

MoneyTor connects to **Wealthsimple** and **Questrade**, merges everyone's
holdings into a single view, converts it all to one currency, and shows it on a
dashboard with charts and exportable reports.

- Runs entirely on your computer — it talks to your brokers and an exchange-rate
  API, and to no MoneyTor server, because there isn't one
- Multiple people, multiple accounts (TFSA, RRSP, Margin, GIC…)
- Merges the same stock held across different accounts and exchanges
- CAD ⇄ USD conversion, always with exact decimals
- PDF and Markdown reports
- Dark and light themes

> Developers: see [`DEVELOPERS_README.md`](./DEVELOPERS_README.md).

---

## The dashboard

![MoneyTor dashboard](docs/images/app_screenshot.png)

| Area | What it shows |
| --- | --- |
| **KPI cards** (left) | Total value, annual dividends, GIC interest, income, holdings count, top position |
| **Charts** (center) | Two panels, each switching independently between holdings and sectors |
| **Holdings table** (bottom) | Every position merged across accounts, with allocation %, 52-week high distance, price, average price paid, and a pie of which account types hold it |
| **Sidebar** (left) | Toggle people and accounts on and off |
| **⚙ Settings** (top right) | Theme, private mode, start at login, export |

### The Accounts pie

Each row's pie shows how that holding splits across account types, by value:

| Colour | Account type |
| --- | --- |
| 🟢 Green | TFSA |
| 🔵 Blue | RRSP (including spousal) |
| 🟠 Amber | FHSA |
| 🟣 Violet | Margin & Cash (non-registered) |
| ⚪ Grey | Other (managed, GIC) |

- Hover a pie for the exact split; hover the column header for the key
- Click the header to group rows by their main account type
- It follows the sidebar — untick an account and the pies update

### Why are the numbers hidden behind `••••••`?

That screenshot has **private mode** on — a privacy screen for when someone is
looking over your shoulder.

- Hides every dollar figure: total value, dividends, GIC interest, income, and each holding's shares and market value
- Leaves the safe context visible: allocation %, sectors, prices, the account pies
- Turning it **on** is instant; turning it **off** needs your password

---

## Install

MoneyTor uses [**uv**](https://docs.astral.sh/uv/), which installs Python for
you. You don't need Python already.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

<details>
<summary>Windows (PowerShell)</summary>

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
</details>

Then:

```bash
git clone https://github.com/raminrasoulinezhad/MoneyTor.git moneytor
cd moneytor
uv sync
```

---

## Set up your accounts

Your credentials live in a `.env` file that never leaves your computer.

```bash
cp .env.example .env
```

Open `.env` and fill it in.

**App settings**

| Key | What it does |
| --- | --- |
| `MONEYTOR_DISPLAY_CURRENCY` | Currency everything is shown in — `CAD` or `USD` |
| `MONEYTOR_LOG_LEVEL` | How chatty the logs are — `INFO` is fine |
| `MONEYTOR_APP_PASSWORD` | Password asked on launch. Leave blank for no lock |

**Accounts** — one block per person. Replace `PERSON1` with a short name like
`ALEX`. Add as many people as you like.

```dotenv
# Wealthsimple
MONEYTOR__PERSON1__WEALTHSIMPLE_EMAIL=you@example.com
MONEYTOR__PERSON1__WEALTHSIMPLE_PASSWORD=your-password

# Questrade — App Hub → Register a personal app → copy the refresh token
MONEYTOR__PERSON1__QUESTRADE_REFRESH_TOKEN=your-refresh-token
```

- A person can have Wealthsimple, Questrade, or both
- Add `MONEYTOR__PERSON1__NAME=Alex` to show a real name instead of "Person1"
- Wealthsimple may text you a 2FA code on first connection — MoneyTor will ask for it
- 🔒 **Never share `.env`.** It holds real passwords. It is already gitignored

No credentials? MoneyTor still opens, using a demo portfolio.

---

## Run

```bash
uv run python src/main.py
```

### Optional: a desktop icon (Linux)

```bash
./scripts/install-desktop.sh
```

Press **Super** and type "MoneyTor", or double-click the desktop icon.

To remove the launchers later:

```bash
./scripts/install-desktop.sh --uninstall
```

It lists what it will delete and asks first — add `-y` to skip the prompt. Only
the launchers go; MoneyTor, your `.env`, and your cached data stay put.

Prefer MoneyTor to open by itself? Tick **Open MoneyTor when I log in** in
⚙ Settings — it works on Linux, macOS, and Windows, and unticking removes it.
The app still starts locked, so logging in doesn't expose your portfolio.

---

## Fixing a wrong sector

Sectors come from your broker, but Wealthsimple reports almost none, so MoneyTor
ships a built-in ticker → sector table to fill the gaps. The order is:

1. What your broker says
2. What the other broker says, if you hold the same stock there
3. MoneyTor's built-in table

To correct or add one, create `.cache/sectors.json` — your entries beat all three:

```json
{
  "CVE": "Energy",
  "ATH": "Energy"
}
```

- Use the plain ticker — `CVE` also covers `CVE.TO`
- Keep share-class and unit suffixes in full — `TECK.A`, `CAR.UN`
- Stick to the 11 GICS sector names, or `Bullion`, `Crypto`, `Commodities`
- Changes apply on the next launch; no need to refetch

Cash, GICs, bullion, and crypto are bucketed automatically and ignore this file.

---

## One company, two tickers

A stock listed in Canada and the US under the **same** ticker (`AEM` and
`AEM.TO`) already shows as one row. When the tickers differ, MoneyTor merges
the ones it knows about into a single row:

| Company | Shown as | Also includes |
| --- | --- | --- |
| Cameco | `CCO` | `CCJ` |
| Fortuna Mining | `FVI` | `FSM` |
| Altius Minerals | `ALS` | `ATUSF` |
| West Red Lake Gold | `WRLG` | `WRLGF` |

- Hover the symbol to see which tickers were merged
- Searching either ticker finds the row
- Price shows in the first ticker's currency; Avg Paid covers both

To add your own, create `.cache/listings.json` — the first ticker in each group
is the one shown:

```json
[
  ["ABX", "B"]
]
```

⚠️ **Only merge listings that are the same share, one for one.** Merging adds
up share counts, so it is wrong for a US ADR traded at a ratio (often a `…Y`
ticker) or a Canadian CDR. To check a pair: the Canadian price ÷ the US price
should equal today's USD/CAD rate.

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `command not found: uv` | Restart your terminal after installing uv |
| Login fails or asks for a code | Wealthsimple 2FA — enter the texted code when prompted |
| A person won't load | They need *either* a Questrade token *or* both a Wealthsimple email **and** password |
| Values won't unhide | Private mode needs `MONEYTOR_APP_PASSWORD` — the same one used on launch |
| A holding shows the wrong sector | Add it to `.cache/sectors.json` — see [Fixing a wrong sector](#fixing-a-wrong-sector) |

---

## License

[Apache License 2.0](LICENSE) · Copyright (c) 2026 Seyedramin Rasoulinezhad ·
see [NOTICE](NOTICE)
