PY ?= python
.PHONY: install data test bench replay demo frontend clean

install:
	$(PY) -m pip install -e ".[dev]"
	cd frontend && npm install

data:          ## Phase 1: fetch real data and build processed parquet files
	$(PY) scripts/fetch_data.py
	$(PY) -m qgrid.data

test:
	$(PY) -m pytest

bench:         ## Phase 5: run all baselines + ours -> results/benchmark.csv
	$(PY) scripts/run_benchmark.py

replay:        ## Phase 6: export replay JSON -> results/replay + frontend/public/replay
	$(PY) scripts/make_replay.py

demo:          ## Phase 7: offline demo from replay JSON (backend optional)
	cd frontend && npm run dev

clean:
	rm -rf .pytest_cache frontend/dist
