# 06 — Results and conclusions

*What was found, what it means, and what it earns the right to build next.*

## The findings, in causal order

1. **Factor-stripping works.** Residual (market-stripped) 5-minute returns
   autocorrelate at −0.038 vs −0.008 raw — the Carhart machinery isolates a
   reversion signal 5× stronger than raw prices show ([04](04_signal.md), fig 04).
2. **The signal is real and consistent.** OLS on seven features: rank IC 0.022
   at the 10-minute horizon, positive in every walk-forward year 2021–2026,
   IC t-stats 3.7–13.1. Alpha decay visible after 2023 and disclosed.
3. **Linear wins.** An MLP on identical features loses to OLS (IC 0.0209 vs
   0.0223) — at this signal-to-noise, nonlinear capacity buys variance, not
   insight. Pre-registered, reported.
4. **The paper alpha is genuine alpha.** Attribution of the paper-fill P&L on
   the Carhart factors: **α = +23.6%/yr (Newey-West t = 4.93)**, market beta
   0.019, R² = 0.018 — the neutralization held; 98% of P&L variance is
   idiosyncratic. This is what the whole pipeline was built to produce.
5. **Execution consumes it — precisely.** Market-order fills forfeit ~$950/day
   of the ~$904/day paper edge: the bid-ask bounce. Net of any realistic
   slippage, every taker configuration loses ([05](05_backtest.md), figs 07/09).

## The one-paragraph conclusion

Short-horizon residual reversion in large-cap US equities is real, measurable,
statistically robust — and it is **the fee that liquidity providers charge**,
not free money lying on the sidewalk. It can be seen by anyone with bar data;
it can be *collected* only by resting passive orders in the queue, i.e. by
bearing adverse-selection risk as a quasi-market-maker. A bar-level simulator
cannot honestly model queue position, which is exactly why this project's
conclusion motivates its natural sequel: **a C++ feed handler for IEX's free
tick-level DEEP/TOPS pcap data feeding this same kdb+ schema**, enabling a
maker-style backtest with real queue dynamics.

## Limitations ledger (accumulated across chapters)

Survivorship bias (today's index members) · IEX-only feed (volumes relative-only;
prices proxy the tape) · ~6-year window (Alpaca free-tier floor) · daily betas
applied intraday · bar fills, not order-book fills · no borrow costs · factor
data lags ~1 month (Ken French refresh cadence).

## What this project demonstrates (the résumé paragraph)

A full quant research loop, every stage verified against an independent source:
a 45M-row partitioned kdb+ tick store built and queried in q; a C++/Eigen
engine running 210k weighted regressions over kdb+ IPC in under a second; a
leakage-controlled ML comparison (purged walk-forward, embargo) with the
discipline to report the simple model winning; an event-driven C++ backtester
whose cost model, not whose optimism, delivered the verdict; and factor
attribution proving the measured edge was genuinely idiosyncratic. The result
is a negative for the strategy and a positive for the process — which is the
outcome that real research produces most of the time, and the skill the
project set out to build.

*Reproduce everything*: `make ingest hdb`, run `betas`, `q q/features.q`,
the Phase 5 scripts, `backtest`, `make figures` — see the [README](../README.md).
