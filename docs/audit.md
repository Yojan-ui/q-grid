# Q-Grid audit (branch `harden`)

Every item from the specs we have been given (explainer, Verify, Try it, Operate, Deploy, dark mode, scorecard, impact,
live moments, demo-day tooling), checked on the production build at 1440×900 unless noted. Status: **done** (works,
checked), **partial** (works with a stated gap), **missing**, **broken**, or **cut**. Broken and partial items found
in this pass were fixed first; what remains partial is listed with the reason. Screenshots: `docs/media/audit/`.

Automated checks behind this table (all pass on the build):
`pytest` (backend, incl. `test_numbers.py`, `test_live.py`, `test_operate.py`) · `frontend/scripts/check-numbers.mjs`
(0 untraced numbers on 23 screens, no card with > 3 numbers) · `check-contrast.mjs` (WCAG AA, 6,508 text elements,
both themes, 1440×900 + 1280×720, incl. Operate and Deploy) · `capture.mjs` (no overlap, no clipping, no panel scroll,
no console errors, 60 fps headless, at 1280×720 / 1440×900 / 1920×1080) · `check-spacing.mjs` (4/8 px grid) ·
`check-recovery.mjs` (backend killed and restarted) · `check-speed.mjs` (first screen 333 ms on the local build).

## Explain (the story)

| Item | Status | Notes | Screenshot |
|---|---|---|---|
| Step 1 · the problem (generated headline) | done | Sentence generated from the scorecard; stand-in badge; one-day figures labelled “that day” and consistent with that day’s status-quo run (test) | [explain-1](media/audit/explain-1.jpg) |
| Step 2 · the campus | done | Zone chips + 3D selection; device list | [explain-2](media/audit/explain-2.jpg) |
| Step 3 · the decisions | done | Current design’s on/off counts | [explain-3](media/audit/explain-3.jpg) |
| Step 4a–4e · qubits, QUBO, circuit, measure, decode | done | **Fixed:** 4e/4f said QAOA “differs from exact” when it had found an equally cheap setting (tie at the optimum); now compared by cost | [4a](media/audit/explain-4a.jpg) [4b](media/audit/explain-4b.jpg) [4c](media/audit/explain-4c.jpg) [4d](media/audit/explain-4d.jpg) [4e](media/audit/explain-4e.jpg) |
| Step 4f · verdict (quantum not in the loop) | done | **Fixed:** 3D tag said “fallback tier”; now “QAOA = exact search (same cost)” | [explain-4f](media/audit/explain-4f.jpg) |
| Step 4g · who does what | done | | [explain-4g](media/audit/explain-4g.jpg) |
| Step 5 / 5b · neighbours agree, prices | done | | [5](media/audit/explain-5.jpg) [5b](media/audit/explain-5b.jpg) |
| Step 6 · storage | done | **Fixed:** diesel hours came from the earlier prototype’s benchmark; now from the replay runs. Headline now follows the data | [explain-6](media/audit/explain-6.jpg) |
| Step 6b · faculty rules | done | | [explain-6b](media/audit/explain-6b.jpg) |
| Step 7a · scorecard | done | Re-run with battery wear priced; 3 key cards | [explain-7a](media/audit/explain-7a.jpg) |
| Step 7f · Sankey | done | From the replay run (`make_sankey.py`) | [explain-7f](media/audit/explain-7f.jpg) |
| Step 7b · across campuses | done | Cards cut to Q-Grid + closest alternative (≤ 3 numbers) | [explain-7b](media/audit/explain-7b.jpg) |
| Step 7c · comms failure | done | | [explain-7c](media/audit/explain-7c.jpg) |
| Step 7d · is it worth it? | done | Payback / NPV / Monte Carlo from `impact.json` | [explain-7d](media/audit/explain-7d.jpg) |
| Step 7e · bottom line (generated) | done | | [explain-7e](media/audit/explain-7e.jpg) |
| Run-wide: current design in the charts | done | **Fixed (broken):** the frontend swapped the old Benders run over the current design whenever the replay still carried it | — |

## Live moments (offline: precomputed by the same code; live: backend, each < 5 s)

| Item | Status | Notes | Screenshot |
|---|---|---|---|
| Solve a slot (QAOA block vs exact) | done | 0.1 s live | [live-qaoa](media/audit/live-qaoa.jpg) |
| Remove a building | done | **Fixed:** removing the hostels took 28.6 s (the cut-off pump house was re-solved every coordination round); now ≤ 3.0 s for every building, same results | [live-remove](media/audit/live-remove.jpg) |
| Type a rule (3 presets: binding, cheap, rejected) | done | ≈ 1.8 s live | [live-rule](media/audit/live-rule.jpg) [rejected](media/audit/live-rule-rejected.jpg) |
| Backend restart during a demo | done | Falls back with a label within 15 s, returns to live by itself (`check-recovery.mjs`) | — |

## Verify

| Item | Status | Notes | Screenshot |
|---|---|---|---|
| Scorecard with click-to-provenance | done | **Rebuilt:** showed the earlier prototype’s benchmark (contradicted the scorecard) | [verify](media/audit/verify.jpg) [provenance](media/audit/verify-provenance.jpg) |
| Design history, QAOA check, data status, hashes | done | Data status lists the exact missing files | [verify](media/audit/verify.jpg) |

## Operate (control room)

| Item | Status | Notes | Screenshot |
|---|---|---|---|
| Services on one clock (safety, controller, MPC + ADMM, economics), WebSocket | done | Live 1×, fast-forward 60×, pause tested through the API | [operate](media/audit/operate.jpg) |
| Live Open-Meteo forecast, cached, labelled; loads and tariff labelled | done | | [operate](media/audit/operate.jpg) |
| Hardware (ESP32 over MQTT, LIVE HARDWARE badge) | **partial** | Implemented to the contract in docs/hardware.md; tested only without a node (simulated, labelled). No ESP32 or broker was available | [operate-devices](media/audit/operate-devices.jpg) |
| Campus map, building cards (≤ 3 numbers), Gantt, plan vs actual, status sentence | done | | [operate](media/audit/operate.jpg) |
| Events log, ADMM messages, device health | done | | [messages](media/audit/operate-messages.jpg) [devices](media/audit/operate-devices.jpg) |
| Manual override with confirmation, safety still clamps, audit trail | done | Refused without confirmation (API test) | [override](media/audit/operate-override.jpg) |
| Rules box | done | | [rules](media/audit/operate-rules.jpg) |
| Daily report + PDF export | done | One A4 page (print test) | [report](media/audit/operate-report.jpg) |
| Offline recorded session | done | Same engine, labelled “Recorded session (offline)” | [operate](media/audit/operate.jpg) |

## Deploy

| Item | Status | Notes | Screenshot |
|---|---|---|---|
| Interactive architecture | done | Keyboard-operable | [deploy](media/audit/deploy.jpg) |
| Rollout phases 0–3 | done | Durations labelled estimates | [rollout](media/audit/deploy-rollout.jpg) |
| BOM, payback, NPV | done | From the economics module | [economics](media/audit/deploy-economics.jpg) |
| Safety and security, roles | done | | [safety](media/audit/deploy-safety.jpg) |
| RVCE checklist, shadow-mode simulator | done | Shadow report from the scorecard’s RVCE days | [shadow](media/audit/deploy-shadow.jpg) |

## Look, tooling, deployment, documents

| Item | Status | Notes | Screenshot |
|---|---|---|---|
| Dark mode (all screens, 3D at night, no flash, D key) | done | | [1](media/audit/dark-explain-1.jpg) [4d](media/audit/dark-explain-4d.jpg) [operate](media/audit/dark-operate.jpg) [deploy](media/audit/dark-deploy.jpg) [menu](media/audit/theme-menu.jpg) |
| Presenter mode, projector sizes | done | | [presenter](media/audit/presenter.jpg) |
| Demo preset (`?demo`) | done | New: step 1, presenter, backend warmed, readiness pill | [demo-preset](media/audit/demo-preset.jpg) |
| Data badge (x real / y pending, files listed) | done | 3 real, 6 pending | [data-badge](media/audit/data-badge.jpg) |
| One-page summary PDF | done | One A4 page, printed light | — |
| Static deploy (Vercel config, offline build) | **partial** | `frontend/vercel.json` and `npm run build:static` ready; not deployed (needs your Vercel account) — README has the link placeholder | — |
| Backup video (90 s) and hero GIF | done | `docs/media/backup_demo.webm`, `docs/media/hero.gif` | — |
| README, pitch scripts, Q&A, runbook | **partial** | Rendered from results with no missing numbers; team members and faculty guide are placeholders for you to fill | — |
| Speed (first screen < 3 s, 3D and modes lazy) | done | 333 ms locally | — |

## Real data status

`scripts/refresh_all.sh` was not re-run: `data/raw/tariff/`, `data/raw/cea/` and `data/raw/iex/` are empty and there is
no calendar or RVCE meter data, so a re-run would reproduce the same results. `python scripts/data_status.py` (run as
part of this pass): **3 real** (NASA POWER, OpenStreetMap, BDG2), **6 pending**, still missing:

- `data/raw/iex/*.xlsx` — IEX 15-minute day-ahead prices for 2023
- `data/raw/tariff/KERC_tariff_order_BESCOM_FY2023-24.pdf`, `data/raw/tariff/KERC_solar_export_tariff.pdf` (then `prices.A.status: REAL`)
- `data/raw/cea/*.pdf` and `data/raw/cea/emission_factor.yaml`
- `data/raw/rvce_calendar.csv`
- `data/raw/rvce_meters/*.csv` and 12 months of BESCOM bills
- `data/raw/lab_schedule.csv` filled in by RVCE (currently a template)

## Cut

- **Try it** tab (what-if sandbox, stress tests, operator rule box on the earlier prototype’s model and solver): superseded
  by the three live moments and Operate’s rules box; the old what-if numbers did not match the current design.
- **Verify → earlier-prototype benchmark table** and its **“Solve a slot live”** demo (old QUBO model via `/solve`):
  contradicted the scorecard; replaced by the scorecard with provenance and the current QAOA block check.
- The backend endpoints `/whatif`, `/rules/parse` and `/solve` stay in the API (tests use them) but no screen calls them.
