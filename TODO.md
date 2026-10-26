# TODO

Known gaps as of **v1.7.0**. Nothing here blocks using the app — it all runs,
and the full suite is green.

---

## Worth doing

**Test the macOS and Windows autostart backends on real machines.** Both are
unit-tested against a temp directory and a fake registry, but neither has ever
run on the OS it targets. The Linux backend is verified end to end
(`desktop-file-validate` passes).

---

## Nice to have

- **One failed login blocks the whole refresh.** If one person's token has
  expired, nobody's data refreshes. Keeping the others' fresh data would need
  clear marking of which parts are stale
- **Questrade account-type codes are unverified.** FHSA, RESP, LIRA and RRIF
  are mapped from memory (their docs block automated reads). An unrecognised
  type now shows as "Other" with a logged warning, never as Cash
- **Unticking every account shows everything**, not nothing — by design, but
  surprising
- **Chart values live in the page even in private mode.** The donut renders only
  symbol + percentage, so nothing is on screen — but Plotly embeds the raw
  amounts as figure data, readable by anyone with devtools. Feeding it allocation
  fractions instead of dollars would render identically and remove them
- **The bundled sector table is hand-maintained.** `aggregation/default_sectors.py`
  covers the tickers seen so far; a new holding your broker doesn't classify
  still shows "Unknown" until it's added there or to `.cache/sectors.json`
