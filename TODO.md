# TODO

Known gaps as of **v1.3.0**. Nothing here blocks using the app — it all runs,
and the full suite is green.

---

## Worth doing

**Test the macOS and Windows autostart backends on real machines.** Both are
unit-tested against a temp directory and a fake registry, but neither has ever
run on the OS it targets. The Linux backend is verified end to end
(`desktop-file-validate` passes).

---

## Nice to have

- **Coverage gaps** (90% overall): `ui/app.py` 33%, `ui/widgets/sidebar.py` 54%.
  These are the hardest paths to drive headlessly, but the sidebar's
  tree-building logic is testable
- **Chart values live in the page even in private mode.** The donut renders only
  symbol + percentage, so nothing is on screen — but Plotly embeds the raw
  amounts as figure data, readable by anyone with devtools. Feeding it allocation
  fractions instead of dollars would render identically and remove them
- **Sector overrides are undocumented.** `.cache/sectors.json` maps tickers to
  GICS sectors and fills gaps where Wealthsimple returns none — worth a README
  section, since holdings otherwise show "Unknown"
