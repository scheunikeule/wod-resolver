# wod-resolver

Nightly pipeline: 12nullacht WOD page → **Workout IR** JSON → the timer app.
The app never parses text again; it fetches `wod/today.json`.

- `CLAUDE.md` — the resolver law (the scheduled Claude task reads this first).
- `schema/ir.schema.json` — the IR (COACH-GRAMMAR-AND-IR.md §3).
- `scripts/fetch.py` — page → entries (offline-testable with `--html`).
- `scripts/normalize.py` — spelling-only typo pass + class/HYROX split.
- `scripts/validate.py` — schema · clock arithmetic · pair sanity · **line
  coverage** (nothing silently dropped) · confidence. Exit ≠ 0 → do not publish.
- `test/corpus/` — the real feed (100 class days, Jul 13 – Oct 27 2026).
- `test/expected/` — hand-reviewed IR fixtures (the few-shots). Fixture zero:
  2026-10-27 (typo'd specs, bundled stations, HYROX nested 2x a/b).
- `wod/` — published output: `YYYY-MM-DD.json`, `index.json`, `today.json`.

Run the gate: `python3 scripts/validate.py test/expected/2026-10-27.json test/corpus/2026-10-27.txt`
