PY ?= python
.PHONY: install data test bench replay demo backend verify verify-ci frontend clean qaoa

install:
	$(PY) -m pip install -e ".[dev]"
	cd frontend && npm install

data:          ## fetch/verify raw data, OSM layout, processed parquet files, problem-day analysis
	$(PY) scripts/fetch_data.py || true
	$(PY) -m qgrid.data
	$(PY) scripts/problem_day.py

test:
	$(PY) -m pytest -p no:warnings

qaoa:          ## train QAOA parameters + scaling study + demo distributions
	$(PY) scripts/train_qaoa_params.py
	$(PY) scripts/qaoa_study.py

bench:         ## all methods, both price scenarios, 6 scenarios + 30-day set (~15 min on a MacBook)
	$(PY) scripts/run_benchmark.py
	$(PY) scripts/write_results_md.py
	$(PY) scripts/make_manifest.py

replay:        ## replay JSON -> results/replay + frontend/public/replay
	$(PY) scripts/make_replay.py

backend:       ## live API for Judge mode / sandbox / live websocket
	cd backend && $(PY) -m uvicorn qgrid.api:app --port 8000

demo:          ## frontend + backend (frontend alone works offline from replay JSON)
	($(PY) -m uvicorn qgrid.api:app --app-dir backend --port 8000 &) ; cd frontend && npm run dev -- --open '/?live=1'

verify:        ## recompute the headline subset, PASS/FAIL per number vs results/manifest.json
	$(PY) scripts/verify.py

verify-ci:
	$(PY) scripts/verify.py --ci

clean:
	rm -rf .pytest_cache frontend/dist
