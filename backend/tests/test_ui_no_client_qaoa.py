"""Every QAOA result in the demo comes from the pipeline (Qiskit Aer shots stored in the replay), never from
the browser. Fails if the frontend simulates or samples QAOA itself, or if the replay's shot tables are
missing or inconsistent with the plan the UI shows as QAOA's answer."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"
REPLAY = ROOT / "results" / "replay"

# signatures of client-side QAOA / sampling: statevector maths, circuit layers, random draws, seeded RNGs
FORBIDDEN = [
    (r"Math\.random\s*\(", "random numbers"),
    (r"\bmulberry32\b|\bxorshift\b|\bseedrandom\b", "seeded RNG"),
    (r"\bstatevector\w*\s*\(", "statevector simulation"),
    (r"\bqaoaLayers\b|\bisingNormalised\b", "QAOA layer simulation"),
    (r"\bsample\s*\(\s*\w+\s*,\s*\d+", "sampling shots from probabilities"),
    (r"from\s+['\"][./]*lib/qaoa['\"]", "in-browser QAOA module"),
    (r"\.probs\b", "QAOA probability vector used for display"),
]


def _sources():
    return [p for p in SRC.rglob("*") if p.suffix in {".ts", ".tsx", ".js", ".jsx"}]


def test_frontend_has_no_client_side_qaoa():
    assert _sources(), "frontend sources not found"
    assert not (SRC / "lib" / "qaoa.ts").exists(), "in-browser QAOA module must not exist"
    hits = []
    for p in _sources():
        text = p.read_text(encoding="utf-8")
        for pat, why in FORBIDDEN:
            for m in re.finditer(pat, text):
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{p.relative_to(ROOT)}:{line} {why}: {m.group(0)}")
    assert not hits, "client-side QAOA in the UI:\n" + "\n".join(hits)


def _scenarios():
    files = sorted(REPLAY.glob("scenario_*.json"))
    if not files:
        pytest.skip("replay not generated (make replay)")
    return files


def test_replay_qaoa_results_come_from_pipeline_shots():
    for f in _scenarios():
        sc = json.loads(f.read_text())
        live = sc.get("live_solve") or []
        assert live, f"{f.name}: no live_solve records"
        for rec in live:
            q = rec["qaoa"]
            shots = q.get("shots")
            assert shots, f"{f.name} {rec['zone']}@{rec['time']}: no measured shots in replay"
            assert "qiskit-aer" in q.get("backend", ""), f"{f.name}: shots not from Qiskit Aer"
            assert sum(s["count"] for s in shots) == 256
            assert all(len(s["bits"]) == rec["n_qubits"] for s in shots)
            valid = [s for s in shots if s["feasible"]]
            if not valid:
                assert q["best_bits"] is None
                continue
            # the plan shown as QAOA's answer is the cheapest valid measured plan
            best = min(valid, key=lambda s: s["objective"])
            assert abs(best["objective"] - q["best_objective"]) < 1e-6, f"{f.name} {rec['zone']}@{rec['time']}"
            assert q["best_bits"] in {s["bits"] for s in valid if abs(s["objective"] - best["objective"]) < 1e-6}


def test_zone_and_cable_counts_consistent():
    """Every scenario, the search-space file and the README agree on the number of zones and cables."""
    files = _scenarios()
    counts = {(len(json.loads(f.read_text())["campus"]["zones"]), len(json.loads(f.read_text())["campus"]["lines"])) for f in files}
    assert len(counts) == 1, f"zone/cable counts differ between scenarios: {counts}"
    (nz, nl), = counts
    ss = json.loads((REPLAY / "search_space.json").read_text())
    assert len(ss["local_qubo_qubits"]) == nz
    assert ss["centralised_full_day"]["vars_per_slot"]["_tie_lines"] == 2 * nl   # p and n bit per cable
    readme = (ROOT / "README.md").read_text()
    assert f"{nz} zones" in readme
