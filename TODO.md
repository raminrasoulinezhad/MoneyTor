# TODO

Known gaps as of **v1.1.1**. Nothing here blocks using the app — it all runs,
and the full suite is green.

---

## Worth doing

**Run tests in CI.** `.github/workflows/` only has the secret scan. Nothing
stops a push that breaks the suite, lint, or types. Add a workflow running
`pytest`, `ruff`, and `mypy` on push and PR — all three are green right now, so
the gate would start clean. Qt needs `QT_QPA_PLATFORM=offscreen`.

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
