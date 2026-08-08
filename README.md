# Intraday residual reversion — kdb+/q · C++ · Python

A complete quant research project: do idiosyncratic (factor-stripped) intraday
moves in S&P 100 stocks mean-revert, and can anyone get paid for it?

**Answer** (spoiler, and proudly so): the signal is real — rank IC 0.022,
positive every year out-of-sample, paper alpha +23.6%/yr (t=4.9) with genuine
factor neutrality — and it is consumed, almost to the dollar, by the bid-ask
bounce at execution. It is the market-maker's fee, measurable by anyone,
collectible only by the passive side of the book. Full story: [docs/06_results.md](docs/06_results.md),
or the standalone research write-up: [Residual_Reversion_Report.pdf](Residual_Reversion_Report.pdf).

## Architecture

```
Alpaca 1-min bars ──┐                          ┌── C++/Eigen: 210k rolling
Yahoo daily ────────┼─► kdb+ partitioned HDB ──┤   Carhart betas over IPC
Ken French factors ─┘   (45M rows, q feature   ├── C++ event-driven backtester
                         pipeline: aj, xbar,   └── Python: OLS vs MLP, purged
                         wj, .Q.dpft)              walk-forward CV, attribution
```

Each stage lives in one folder, is documented in one numbered chapter in
`docs/` (with regenerable figures), and was verified against an independent
source before the next stage was built.

## Documentation — read in order

| Chapter | Contents |
|---|---|
| [01 — data](docs/01_data.md) | sources, cleaning with receipts, coverage figure, war stories |
| [02 — kdb+ design](docs/02_kdb_design.md) | partitioned HDB anatomy, how a query walks the tree |
| [03 — factor model](docs/03_factor_model.md) | Carhart betas, C++/IPC engine, the label-shift saga |
| [04 — signal](docs/04_signal.md) | residual autocorrelation, features, OLS beats MLP |
| [05 — backtest](docs/05_backtest.md) | mechanics, cost model, the paper-vs-market decomposition |
| [06 — results](docs/06_results.md) | conclusions, limitations ledger, what's next |

## Reproducing from scratch

One-time setup: [KDB-X](https://kx.com) (free, registration), a free
[Alpaca](https://alpaca.markets) API key in `.env` (`APCA_API_KEY_ID`,
`APCA_API_SECRET_KEY`), `brew install cmake eigen`, `pip install yfinance torch`.

```bash
make ingest                  # download bars (~1h), daily, factors  -> data/raw/
make hdb                     # build the partitioned kdb+ database  -> data/hdb/
cmake -S cpp -B cpp/build && cmake --build cpp/build
~/.kx/bin/q q/serve.q &      # HDB server on port 5001 (leave running)
./cpp/build/betas            # 210k rolling regressions, ~1s
~/.kx/bin/q q/features.q     # bars5 + sig feature tables, ~15 min
python3 python/research/02_baseline_ols.py     # the baseline numbers
python3 python/research/03_mlp.py              # the challenger (loses)
python3 python/research/04_make_predictions.py # OOS prediction file
~/.kx/bin/q q/load_preds.q                     # (restart serve.q after)
./cpp/build/backtest                           # the verdict
python3 python/research/05_attribution.py      # the alpha autopsy
make figures                 # regenerate every figure in docs/figures/
```

## Repo map

```
q/        schema, loaders, cleaning, feature pipeline (each file < ~120 lines, heavily commented)
cpp/      kdb IPC wrapper (RAII), beta engine (Eigen), backtester; vendor/ = KX C API
python/   ingest/ (downloaders) · research/ (models, attribution) · validation/ (purged CV) · figures/
data/     raw/ (per-source subfolders) · hdb/ (kdb+ database) · model/ (datasets, results) · reports/
docs/     the six chapters + figures/
```

Built as a learning project — the docs deliberately include every bug and
dead end (q's right-to-left evaluation, block comments, stale CMake objects,
Finder-corrupted partitions) because the debugging is half the education.
