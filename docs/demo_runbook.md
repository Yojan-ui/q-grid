# Demo runbook — exact click order, what to say, what to do if something fails

_Rendered from `docs/templates/demo_runbook.md`; numbers from `results/`. Rehearse twice with a timer (presenter mode shows it)._

## Before you go on stage (T−10 min)

1. Laptop on power, display mirrored, 1280×720 or 1920×1080. Do-not-disturb on.
2. Terminal 1 (live backend, optional): `make backend` → wait for `Uvicorn running on http://127.0.0.1:8000`.
3. Terminal 2: `cd frontend && npm run dev` (or open the deployed link: offline replay, no backend needed).
4. Open **`http://localhost:5173/?demo`** (or click **Demo** in the top bar). The Demo preset opens Explain at step 1 in
   presenter mode and warms the backend so the first live moment answers fast. Wait for the pill:
   **Demo ready · live** (backend warmed) or **Demo ready · offline** (precomputed live moments from the same code).
   If it says "no precomputed live moments", run `python scripts/make_live.py` before going on.
5. Press **D** if the room needs dark mode. The presenter timer (top bar) starts at 0:00; **reset** before you begin.
6. Backup: `docs/media/backup_demo.webm` (90 s) open in a second tab, paused at 0:00.

## Click order (≈ 3:00, matches docs/pitch_3min.md)

| # | Do | Say (short) | If it fails |
|---|---|---|---|
| 1 | Step 1 loads; let the day replay (18 s). | Problem sentence on screen. | Nothing to fail; replay is local. |
| 2 | → Step 2. | "RVCE, nine buildings, ten cables." | — |
| 3 | → Step 3. | "Each building solves only its own." | — |
| 4 | → through 4a–4e (tiles → qubits → circuit → histogram → decode). | "We tested a quantum circuit honestly." | If 3D stutters, keep talking; the panel carries the story. |
| 5 | Step 4f: click **Measure the 5-qubit block**. | "Matches exact search — but saved no work, so it's not in the loop." | Live > 5 s or error: it falls back to the precomputed measurement automatically (label says so). |
| 6 | → 4g, → Step 5. Watch the rounds converge. | "Neighbours agree, no central computer." | — |
| 7 | Step 5: click **Take mechanical labs offline**. | "3 cables dark; others re-agree in 55 rounds; critical load still served." | Precomputed result shows (took 0.8 s). Click **Bring … back** to reset. |
| 8 | → 5b, → Step 6 (battery fills before the outage). | "Batteries carry the outage." | — |
| 9 | → Step 6b (faculty rules): click the chip **no DG**, then **EV charging only after 10 pm**. | "Checked, then priced. Impossible rules are refused." | Offline: only the three chips are precomputed; don't type a new rule without the backend. |
| 10 | → 7a scorecard (pause 3 s), → 7b, → 7c. | "Same days, same data. When the network fails…" | — |
| 11 | → 7d **Is it worth it?** | "About Rs 7.9 lakh of nodes; pays back in 0.4 years with battery wear counted (assumed costs)." | — |
| 12 | → 7e bottom line. Stop. | Read the sentence on screen. | — |

## Recovery

- **Browser frozen / blank:** reload (`⌘R`); add `?stop=5` etc. to jump straight to a step.
- **Backend died mid-demo:** nothing to do — moments fall back to precomputed answers and say so; the badge turns grey
  within 15 s, and turns back to **Live backend** by itself once you restart it (`make backend`). Tested by
  `frontend/scripts/check-recovery.mjs`.
- **Projector cuts the right side:** press **P** again to leave presenter mode, or `⌘−` once.
- **Everything fails:** play `docs/media/backup_demo.webm` and narrate over it.

## Timing targets (presenter timer)

Step 1 0:25 · 2 0:15 · 3 0:15 · 4 0:35 · 5 0:30 · 6 0:20 · 7 0:40.
