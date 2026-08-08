# Top-level entry points. Each target is safe to re-run: downloads checkpoint
# per file and skip work already done.
#
#   make universe   write the S&P 100 ticker list
#   make factors    Ken French Carhart factors (daily)
#   make daily      Stooq daily history (for beta estimation run-up)
#   make bars       Alpaca 1-minute bars (the long one: ~45-90 min first time)
#   make ingest     all of the above, in order

PY := python3
Q := $(HOME)/.kx/bin/q

.PHONY: ingest universe factors daily bars hdb figures

ingest: universe factors daily bars

# rebuild the kdb+ database from raw CSVs (~2 min). Finder drops .DS_Store
# files into browsed folders and they break q's directory parsing — sweep first.
hdb:
	find data -name .DS_Store -delete
	$(Q) q/load_csv.q
	$(Q) q/load_flat.q

figures:
	$(PY) python/figures/make_figures.py

# C++ engines (server must be running: ~/.kx/bin/q q/serve.q &)
cpp-build:
	cmake -S cpp -B cpp/build && cmake --build cpp/build

betas: cpp-build
	./cpp/build/betas

features:
	$(Q) q/features.q

backtest: cpp-build
	./cpp/build/backtest

universe:
	$(PY) python/ingest/universe.py

factors:
	$(PY) python/ingest/download_factors.py

daily: universe
	$(PY) python/ingest/download_daily.py

bars: universe
	$(PY) python/ingest/download_bars.py

report:
	$(PY) python/figures/make_report.py
