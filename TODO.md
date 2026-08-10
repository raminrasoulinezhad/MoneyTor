# TODO

Known gaps as of **v1.1.1**. Nothing here blocks using the app — it all runs,
and the full suite is green.

---

## Worth doing

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
  (`consider-using-with`, `import-outside-toplevel`). pylint is deliberately
  not in CI — its score is a float, which makes a poor pass/fail gate. Clearing
  these would let it join as `--fail-under=10`
- **Sector overrides are undocumented.** `.cache/sectors.json` maps tickers to
  GICS sectors and fills gaps where Wealthsimple returns none — worth a README
  section, since holdings otherwise show "Unknown"
