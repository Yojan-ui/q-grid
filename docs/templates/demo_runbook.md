# Demo runbook — exact click order, what to say, what to do if something fails

_Rendered from `docs/templates/demo_runbook.md`; numbers from `results/`. Spoken lines match [docs/pitch_3min.md](pitch_3min.md).
Rehearse twice with a timer (presenter mode shows it)._

## Before you go on stage (T−10 min)

1. Laptop on power, display mirrored, 1920×1080 (or 1280×720). Do-not-disturb on. Close other heavy apps.
2. Open the deployed link (static build, offline replay, no backend needed), **or** locally: `cd frontend && npm run dev`.
3. Optional live backend (the three live moments compute on the spot): `make backend` in a second terminal → wait for
   `Uvicorn running on http://127.0.0.1:8000`. Without it, the live moments use precomputed answers from the same code and
   say so.
4. Open **`/?demo`** (or click **Demo** in the top bar). It opens Explain at Step 1 in presenter mode and warms the backend.
   Wait for the pill: **Demo ready · live** or **Demo ready · offline**. If it says "no precomputed live moments", run
   `python scripts/make_live.py` before going on.
5. Press **D** if the room needs dark mode. Reset the presenter timer (top bar) to 0:00.
6. Backup: `docs/media/demo_backup.webm` (90 s) open in a second tab, paused at 0:00.

## Click order (3:00)

| # | Do | Say (short) | If it fails |
|---|---|---|---|
| 1 | Step 1 loads; the problem cards show. | Read the problem sentence: "{{headline.step1}}" | Nothing to fail; the replay is local. |
| 2 | → Step 2. | "RVCE, nine building groups, about 500 kWp of solar, two diesel sets." | — |
| 3 | → Step 3. | "Each building solves only its own next 24 hours." | — |
| 4 | → 4a–4e (tiles → qubits → circuit → histogram → decode). | "We tested a quantum circuit honestly." | If 3D stutters, keep talking; the panel carries the story. |
| 5 | Step 4f: click **Measure the {{live.qaoa.n_qubits}}-qubit block**. | "Matches exact search, but saved no work, so it's not in the loop." | Live > 5 s or error: falls back to the precomputed measurement automatically (label says so). |
| 6 | → 4g, → Step 5. Watch the rounds converge. | "Neighbours agree; no central computer." | — |
| 7 | Step 5: click **Take mechanical labs offline**. | "{{live.remove.lines|0}} cables dark; the others re-agree in {{live.remove.rounds_after|0}} rounds; {{live.remove.crit_text}}." | The precomputed result shows (computed in {{live.remove.compute_s|1}} s). Click **Bring … back** to reset. |
| 8 | → 5b, → Step 6 (proposed battery fills before the outage). | "Batteries carry the outage." | — |
| 9 | → Step 6b: click the chip **{{live.rule0.text}}**, then **{{live.rule2.text}}**. | "Checked, then priced. Impossible rules are refused." | Offline: only the chips are precomputed; don't type a new rule without the backend. |
| 10 | → 7a scorecard (pause 3 s), → 7b, → 7c. | "Same days, same data. When the network fails…" | — |
| 11 | → 7d **Is it worth it?** | "{{imp.spoken}}" | — |
| 12 | → 7e bottom line. Stop. | Read the sentence on screen: "{{headline.sentence}}" | — |

## Recovery

- **Browser frozen / blank:** reload (Ctrl+R); add `?stop=5` etc. to jump straight to a step.
- **Backend died mid-demo:** nothing to do. Moments fall back to precomputed answers and say so; the badge turns grey within
  15 s and back to **Live backend** by itself once you restart it (`make backend`).
- **Projector cuts the right side:** press **P** to leave presenter mode, or Ctrl+− once.
- **Everything fails:** play `docs/media/demo_backup.webm` and narrate over it with the 3-minute script.

## Timing targets (presenter timer)

Step 1 0:30 · 2 0:15 · 3 0:15 · 4 0:35 · 5 0:30 · 6 0:20 · 7 0:35.
