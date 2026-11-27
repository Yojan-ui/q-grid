# Agent C (frontend & product) handoff: branch `agent/ui`

Based on `real-data` (6de0bd2). Commits: 333fdc4 (features), dbe8f51 (checks + layout fixes), 6e82b0c (screenshots), plus this file.
Only `frontend/` (not `frontend/public/replay/`), `docs/handoff/agent-ui/` and `docs/media/agent-ui/` were touched.

## What changed

1. **Plan tab (investment planner).** The top bar now reads Explain | Operate | Deploy | Plan | Verify (`?mode=plan`).
   - Inputs: one slider per roof group, snapping to `step_kwp` up to `max_extra_kwp`. Under each slider: "today X kWp, after Y kWp". There is also a battery kWh slider (`step_kwh`, `max_kwh`), contract-demand buttons (`contract_demand_options`), **Show the optimum** and Reset.
   - Outputs come from the closest case in `cases`, with distance counted in grid steps per input. A pill reads "computed case" for an exact match. Otherwise it reads "nearest computed case", followed by a sentence naming that case's inputs. The figures: payback, 10-year NPV, investment (with annual saving), peak kVA (with contract), diesel L/yr, CO₂ t/yr.
   - Nothing is interpolated or computed in the browser. The only derived figure is existing + extra kWp, registered with `reg()`.
   - Labels: `generated_by` and `status` pills. `labels.tariff` gets a "stand-in tariff" badge and `labels.costs` an "assumed costs" badge; the same badges sit on the Payback and Investment figures. There is also an assumptions table.
   - Missing state: when `replay/planner.json` is absent, or is not a planner file, the tab says "The investment planner is not generated yet". It names `python scripts/plan_investment.py`, `results/replay/planner.json` and `frontend/public/replay/planner.json`, and offers a "Check again" button. It shows no numbers.
2. **PROPOSED badges** (`src/story/Badges.tsx`): a small "proposed" pill (or "unconfirmed" for PENDING); nothing is shown for EXISTING or a missing field. Where it appears:
   - **Step 2:** the Solar and Batteries key figures (if any zone's asset is PROPOSED or PENDING), the "joined by N cables" sentence (if `cables_status` is PROPOSED), and every device row in the building card.
   - **EV chargers:** listed as a device row only when PROPOSED or PENDING, labelled "not in the schedule model".
   - **Step 2 3D device labels:** "Battery · proposed".
   - **Operate building cards:** a "proposed" line listing the proposed assets.
   - **Deploy:** a new "On campus today, and what is proposed" table (building × solar / battery / diesel / EV, plus a cables line). The bill-of-materials note switches its wording when anything is proposed.
3. **Data-provenance dialog** (`src/panels/Sources.tsx`): an "i" button next to Step 1's day figures, Step 2's support line and the Plan header.
   - With `data_provenance` present, it lists input, value, source and page, and status.
   - Without it, it falls back to `replay/data_status.json` (what is real, what is pending).
   - In both cases it has an "Open Verify: data status" button, which switches mode through a `qgrid:mode` window event that App listens for.
4. **Step 1 problem cards.** When `problem_points` is present, up to four cards appear in a 2×2 grid, colour-keyed by `key` (outages, diesel, demand_charges, roofs). The day paragraph and the day chart move into a "One day up close" fold, so the panel does not scroll at 1280x720. Without `problem_points`, Step 1 is unchanged.
5. **Numbers inside replay text.** `regText()` (lib/numcheck.ts) registers numbers that appear inside replay strings, so check-numbers can trace them to loaded data. This covers problem_points, value_label, planner labels, notes and assumption strings.
6. **Layout fix.** At 1280 px the top bar now has five tabs and "Q-Grid" overlapped the Explain tab. The brand no longer shrinks, and the PDF button reads "Summary PDF" below 1400 px.

## Files
- New: `frontend/src/views/Plan.tsx`, `frontend/src/panels/Sources.tsx`, `frontend/src/story/Badges.tsx`, `frontend/scripts/ui_shots.mjs`, `frontend/scripts/fixture-server.mjs`
- Changed: `frontend/src/App.tsx`, `lib/data.ts` (types + `loadPlanner()`), `lib/labels.ts` (asset status helpers, EV device), `lib/numcheck.ts` (`regText`), `story/Panel.tsx`, `story/Stage.tsx`, `views/Operate.tsx`, `views/Deploy.tsx`, `index.css`
- Check scripts: `check-numbers.mjs` and `check-contrast.mjs` now also scan Plan and Verify. `capture.mjs` and `check-contrast.mjs` now include step 7f.

**Test fixture (fake data, not replay).** `node frontend/scripts/fixture-server.mjs --upstream http://localhost:5281 --port 5282 [--no-planner] [--no-scenario]` proxies a vite dev server. It adds every new field, with every value labelled FIXTURE. Nothing fake was written to `public/replay` or `results/`.

## Checks run (dev server on :5281, fixture proxy on :5282, production build preview on :5284)
| Check | Result |
|---|---|
| `npx tsc -b` | pass |
| `npx oxlint src` | 0 errors (only the existing set-state-in-effect warnings in App.tsx) |
| pytest `test_numbers.py`, `test_ui_no_client_qaoa.py` | 9 passed |
| `check-spacing.mjs` | 0 values off the 4 px grid |
| `check-numbers.mjs` on real replay | 0 untraced numbers, 0 cards with more than 3 numbers (all 20 stops + Operate, Deploy, Plan, Verify) |
| `check-numbers.mjs` with fixture fields | 0 / 0 (covers the filled-in Plan, problem cards and badges) |
| `check-contrast.mjs` on real replay, 1440x900 + 1280x720, both themes | token pairs 124/124 AA; DOM scan 7288 elements, 0 violations |
| `check-contrast.mjs` with fixture fields, 1440x900, both themes | 0 violations |
| `capture.mjs` at 1280x720, 1440x900, 1920x1080 | no overlaps, no panel scroll, no top-bar clipping |
| `ui_shots.mjs` (panel scroll, top-bar clip and overflow, horizontal scroll) | 0 problems, real and fixture, at 1280x720 / 1440x900 / 1920x1080 |
| `vite build` | pass |

**Console error.** Under the dev server, capture.mjs reports one console error: "Attempted to synchronously unmount a root while React was already rendering". It also occurs on the untouched base commit 6de0bd2, and comes from React StrictMode double-mounting drei `<Html>` labels in dev. The production build reports **no** console errors at any of the three sizes.

`check-recovery.mjs` was not run: it kills the backend on :8000 (`pkill -f uvicorn`), which another agent or the lead may be using. Nothing in this branch touches the live/recovery path.

## Screenshots (`docs/media/agent-ui/`, 1440x900, JPEG q72, offline, production build)
- Real replay, both themes:
  - `light-*.jpg` / `dark-*.jpg` for explain-1 … explain-7e (including 6b and 7f), explain-2-zone (Hostels selected), sources (provenance dialog fallback), operate, deploy, plan (the "not generated yet" state) and verify.
- Fixture layout previews, both themes:
  - `fixture-{light,dark}-*.jpg` for explain-1 (problem cards), explain-2-zone (badges), sources (provenance table), operate, deploy (asset table) and plan (filled-in planner).
  - **These show fake FIXTURE values.** They exist only to judge layout.

## Replay fields the UI reads (for the lead to generate)
All are optional. When a field is absent, the UI shows the current behaviour or a clear "not generated" state.

`scenario_<key>.json`
- `campus.zones[i].asset_status`: `{pv, battery, dg, ev}`, each `"EXISTING" | "PROPOSED" | "PENDING"`. Any key may be omitted. `ev` is shown only as a status: EV load is not in the schedule model.
- `campus.cables_status`: `"PROPOSED" | "EXISTING"`.
- `data_provenance`: `[{item, value_label, source, page, status}]`.
  - `page` may be null.
  - `status` is styled green for REAL / EXISTING / VERIFIED and amber otherwise.
  - Numbers inside `value_label` and `page` are registered as replay text.
- `problem_points`: `[{key, title, text}]`.
  - Up to 4 are shown.
  - `key` ∈ outages | diesel | demand_charges | roofs; it sets the colour of the card's left edge, and other keys get no colour.
  - Keep `text` to about 2 lines (about 110 characters) so Step 1 does not scroll at 1280x720.
- Already read and unchanged: `provenance`, `problem`, `campus.zones[i].{pv_kwp, battery_kwh, battery_kw, dg_kw, …}`.

`planner.json` (`results/replay/` → copied to `frontend/public/replay/` by make_replay's copy loop)
- `status`: shown as a pill, green if REAL or FINAL.
- `generated_by`: shown as a pill and in the footer.
- `labels.tariff`, `labels.costs`: each shown with its badge.
- `roof_groups[]`: `{key, label, existing_kwp, max_extra_kwp, step_kwp}`.
- `battery`: `{max_kwh, step_kwh}`.
- `contract_demand_options`: e.g. `[1000, 1300, 1600]`. The default selection is the first option.
- `cases[]`: `{extra_kwp: {<group key>: kWp}, battery_kwh, contract_kva, capex_rs, annual_saving_rs, payback_years|null, npv10_rs, peak_kva, diesel_litres_year, co2_t_year}`.
  - The default selection is 0 extra kWp everywhere and 0 kWh battery, so a case with all zeros at each contract option avoids a "nearest" answer at start-up.
  - When `payback_years` is null, the UI shows "not reached", or "nothing added" if `capex_rs` is 0.
- `optimum`: the same fields as a case, plus `note`. The "Show the optimum" button moves the sliders to its inputs.
- `assumptions[]`: `{name, value: number | string | [lo, hi] | null, unit, source}`.
- The loader accepts the file only if `cases` and `roof_groups` are arrays and `battery` exists; otherwise it shows the missing state.

## Open questions
1. Should EV chargers with status EXISTING be listed? Today they are hidden, since EV load is not modelled.
2. Should the Plan tab also appear in presenter mode? It does now: only `devonly` controls are hidden.
3. Plan defaults to the first contract-demand option. If RVCE's current contract demand is known, put it first, or add a `current` field and I'll default to it.
4. The provenance "i" is placed in Step 1, Step 2 and Plan. A top-bar entry could be added, but the bar is at its width limit at 1280 px.
