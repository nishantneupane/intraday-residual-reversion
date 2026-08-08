// backtester.hpp — event-driven intraday backtest of the residual-reversion
// signal (PLAN.md §4.4-4.5, docs/05_backtest.md).
//
// MECHANICS, in order of one simulated day:
//   - buckets are the 78 five-minute bars, 09:30 .. 15:55 (NY time)
//   - at each DECISION bucket (every 2nd bucket = every 10 min, matching the
//     10-minute prediction horizon), rank all stocks by pred:
//       * ENTER long  if rank among top  `n_enter`  (short: bottom n_enter)
//       * EXIT a held position only when its rank leaves the top/bottom
//         `n_exit` — asymmetric bands (hysteresis) so borderline names
//         don't churn in and out every rebalance
//       * the short side's per-name notional is scaled by the ratio of the
//         legs' summed market betas -> net market beta ~ 0
//   - orders execute at the NEXT bucket's OPEN (no same-bar fills — the
//     decision uses bucket t's close, the fill happens 5 minutes later)
//   - at the second-to-last bucket everything is liquidated (intraday
//     strategy: no overnight positions, so the `gap` feature is information,
//     never risk)
//   - marking: position P&L accrues close-to-open and open-to-close around
//     each fill, so fills at opens are priced exactly
//
// COSTS (all per side unless noted):
//   - SEC fee: sell notional x sec_fee_rate      (sells only)
//   - FINRA TAF: shares sold x taf_per_share, capped per trade (sells only)
//   - slippage: traded notional x s, for EVERY s in `slip_bps_scenarios`.
//     Because targets don't depend on fills, net P&L is LINEAR in the
//     slippage rate: one simulation prices every scenario exactly.
//
// Sizing: `notional_per_name` per position, `n_enter` names per side ->
// ~$1M gross book. All cash figures in USD.

#pragma once

#include <string>
#include <vector>

class KdbConnection;

struct BacktestConfig {
  int n_enter = 10;                 // enter band: top/bottom N by prediction
  int n_exit = 25;                  // exit band: leave only when outside top/bottom N
  int rebalance_every = 2;          // decision every k-th bucket (2 = 10 min)
  bool paper_fill = false;          // true: fill AT the decision price (an
                                    // unattainable benchmark that includes the
                                    // bid-ask bounce; used to DECOMPOSE gross
                                    // P&L into "measured signal" vs "what
                                    // market-order execution forfeits")
  double notional_per_name = 50'000.0;
  double sec_fee_rate = 27.80e-6;   // per $ sold (SEC 31 fee, parameterized)
  double taf_per_share = 0.000166;  // FINRA TAF, sells
  double taf_cap = 8.30;            // per-trade TAF cap
  std::vector<double> slip_bps_scenarios = {0.0, 0.5, 1.0, 2.0, 5.0};
  double beta_scale_min = 0.5, beta_scale_max = 2.0;
};

struct DayResult {
  int date;                         // q date (days since 2000-01-01)
  double gross_pnl = 0;             // before all costs
  double fees = 0;                  // SEC + TAF
  double traded_notional = 0;       // sum |fill $| both sides (slippage base)
  double sold_notional = 0;
  int n_trades = 0;
  // net(s) = gross - fees - traded_notional * s
};

// Simulate every date present in the preds table. Returns one row per day.
std::vector<DayResult> run_backtest(KdbConnection& conn, const BacktestConfig& cfg);
