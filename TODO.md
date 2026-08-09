# TODO

Known gaps as of **v1.1.1**. Nothing here blocks using the app — it all runs,
and the full suite is green.

---

## Worth doing

**Run tests in CI.** `.github/workflows/` only has the secret scan. Nothing
stops a push that breaks the suite, lint, or types. Add a workflow running
`pytest`, `ruff`, and `mypy` on push and PR.

**Clear the 11 mypy errors.** `uv run mypy src` is not clean:

| File | Count | What |
| --- | --- | --- |
| `connectors/wealthsimple.py` | 7 | `.get()` on a value mypy sees as possibly `None` — needs guards on the GraphQL payload |
| `ui/widgets/holdings_table.py` | 1 | `sorted(key=...)` returns `object`; the key needs a comparable type |
| `fx/live.py`, `ui/main_window.py`, `ui/widgets/lock_screen.py` | 3 | Qt event handlers missing a parameter annotation |

**Test the macOS and Windows autostart backends on real machines.** Both are
unit-tested against a temp directory and a fake registry, but neither has ever
run on the OS it targets. The Linux backend is verified end to end
(`desktop-file-validate` passes).

---

## Nice to have

- **Coverage gaps** (90% overall): `ui/app.py` 33%, `ui/widgets/sidebar.py` 54%,
  `ui/widgets/chart_panel.py` 77%. These are the hardest paths to drive
  headlessly, but the sidebar's tree-building logic is testable
- **Two pylint warnings** in `ui/widgets/chart_panel.py`
  (`consider-using-with`, `import-outside-toplevel`)
- **Sector overrides are undocumented.** `.cache/sectors.json` maps tickers to
  GICS sectors and fills gaps where Wealthsimple returns none — worth a README
  section, since holdings otherwise show "Unknown"
