#!/usr/bin/env bash
# Re-run the whole Q-Grid pipeline after real data files arrive in data/raw/.
#   1. put the files in place (see data/SOURCES.md and `python scripts/fetch_data.py`)
#   2. for tariff A: set prices.A.* in config.yaml from the KERC order and prices.A.status: REAL
#   3. for CEA: write data/raw/cea/emission_factor.yaml (version, fiscal_year,
#      weighted_average_tco2_per_mwh, page) from the PDF
#   4. bash scripts/refresh_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-python}
$PY scripts/fetch_data.py || echo "WARNING: some raw data still missing — PENDING items keep their labelled stand-ins"
$PY -m qgrid.data
$PY scripts/problem_day.py
$PY -m pytest -q
$PY scripts/train_qaoa_params.py
$PY scripts/run_benchmark.py
$PY scripts/qaoa_study.py
$PY scripts/write_results_md.py
[ -f scripts/make_replay.py ] && $PY scripts/make_replay.py || true
echo "Done. See results/benchmark.csv, results/plots/, docs/results.md"
