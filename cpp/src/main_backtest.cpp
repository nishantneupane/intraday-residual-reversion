// main_backtest.cpp — Phase 6 entry point: simulate, summarize, export.
// Run:  q q/serve.q      (server must have the preds table loaded)
//       ./cpp/build/backtest
// Writes data/model/backtest_daily.csv (one row per day) for the Python
// figure/attribution layers.

#include <cmath>
#include <cstdio>
#include <iostream>
#include <numeric>

#include "backtester.hpp"
#include "kdb_conn.hpp"

static double sharpe(const std::vector<double>& daily) {
  const double n = (double)daily.size();
  const double mean = std::accumulate(daily.begin(), daily.end(), 0.0) / n;
  double var = 0;
  for (double x : daily) var += (x - mean) * (x - mean);
  var /= (n - 1);
  return mean / std::sqrt(var) * std::sqrt(252.0);
}

int main(int argc, char** argv) {
  try {
    KdbConnection conn("localhost", 5001);
    BacktestConfig cfg;
    // usage: backtest [rebalance_every] [n_exit] [paper 0|1] [out.csv]
    if (argc > 1) cfg.rebalance_every = std::atoi(argv[1]);
    if (argc > 2) cfg.n_exit = std::atoi(argv[2]);
    if (argc > 3) cfg.paper_fill = std::atoi(argv[3]) != 0;
    const char* out_csv = argc > 4 ? argv[4] : "data/model/backtest_daily.csv";
    std::printf("config: rebalance every %d buckets, exit band %d, %s fills\n",
                cfg.rebalance_every, cfg.n_exit,
                cfg.paper_fill ? "PAPER (decision-price)" : "market (next-open)");
    std::vector<DayResult> days = run_backtest(conn, cfg);
    std::cout << "simulated " << days.size() << " days\n";

    FILE* fh = std::fopen(out_csv, "w");
    std::fprintf(fh, "qdate,gross,fees,traded,sold,trades\n");
    for (const auto& d : days)
      std::fprintf(fh, "%d,%.2f,%.2f,%.2f,%.2f,%d\n", d.date, d.gross_pnl,
                   d.fees, d.traded_notional, d.sold_notional, d.n_trades);
    std::fclose(fh);

    const double avg_traded =
        std::accumulate(days.begin(), days.end(), 0.0,
                        [](double a, const DayResult& d) { return a + d.traded_notional; }) /
        days.size();
    std::printf("avg daily traded notional: $%.0fk (on ~$1M gross book)\n",
                avg_traded / 1e3);

    std::printf("%-12s %12s %10s %10s\n", "scenario", "total P&L", "$/day", "Sharpe");
    for (double s_bps : cfg.slip_bps_scenarios) {
      const double s = s_bps * 1e-4;
      std::vector<double> net;
      net.reserve(days.size());
      for (const auto& d : days)
        net.push_back(d.gross_pnl - d.fees - d.traded_notional * s);
      const double total = std::accumulate(net.begin(), net.end(), 0.0);
      std::printf("%5.1f bp slip %12.0f %10.0f %10.2f\n",
                  s_bps, total, total / days.size(), sharpe(net));
    }
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "FAILED: " << e.what() << "\n";
    return 1;
  }
}
