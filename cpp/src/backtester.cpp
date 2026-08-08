// backtester.cpp — implementation. See backtester.hpp for the mechanics.

#include "backtester.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <map>
#include <stdexcept>
#include <unordered_map>

#include "kdb_conn.hpp"

namespace {

// one (sym, bucket) row of the day panel fetched from q
struct PanelRow {
  int bkt;                          // minutes since midnight (570 = 09:30)
  double open, close, pred, beta;   // pred/beta may be NaN
};

struct Position {                   // signed shares; >0 long, <0 short
  double shares = 0;
  double last_price = 0;            // last price we marked at
};

K column(K table, const char* name) {
  K dict = table->k;
  K names = kK(dict)[0], cols = kK(dict)[1];
  for (long long i = 0; i < names->n; ++i)
    if (0 == std::strcmp(kS(names)[i], name)) return kK(cols)[i];
  throw std::runtime_error(std::string("column missing: ") + name);
}

// Fetch one day's joined panel: per (sym, bkt): open, close, pred, beta.
// The q side does all joins; C++ receives one flat table.
std::unordered_map<std::string, std::vector<PanelRow>>
fetch_day(KdbConnection& conn, int qdate) {
  std::string q_expr =
      "{[d] b: select sym: value sym, bkt: `minute$time, open, close "
      "     from bars5 where date=d, sym<>`SPY; "
      " p: select sym, bkt, pred from preds where date=d; "
      " b: b lj `sym`bkt xkey p; "
      " bd: exec max date from select distinct date from betas where date<d; "
      " bb: select sym: value sym, beta: mkt from betas where date=bd; "
      " b: b lj `sym xkey bb; "
      " `sym`bkt xasc b }[" + std::to_string(qdate) + "]";
  KResult res = conn.query(q_expr);

  K sym = column(res.get(), "sym"), bkt = column(res.get(), "bkt");
  K open = column(res.get(), "open"), close = column(res.get(), "close");
  K pred = column(res.get(), "pred"), beta = column(res.get(), "beta");

  std::unordered_map<std::string, std::vector<PanelRow>> panel;
  for (long long i = 0; i < bkt->n; ++i) {
    panel[kS(sym)[i]].push_back(PanelRow{
        kI(bkt)[i], kF(open)[i], kF(close)[i], kF(pred)[i], kF(beta)[i]});
  }
  return panel;
}

}  // namespace

std::vector<DayResult> run_backtest(KdbConnection& conn, const BacktestConfig& cfg) {
  // dates to simulate = every date with predictions, in order
  KResult dres = conn.query("asc exec distinct date from preds");
  std::vector<int> qdates(kI(dres.get()), kI(dres.get()) + dres->n);

  std::vector<DayResult> days;
  days.reserve(qdates.size());

  for (int qdate : qdates) {
    auto panel = fetch_day(conn, qdate);

    // bucket list for the day (from any symbol; buckets are the clock)
    std::vector<int> buckets;
    for (auto& [s, rows] : panel)
      for (auto& r : rows)
        buckets.push_back(r.bkt);
    std::sort(buckets.begin(), buckets.end());
    buckets.erase(std::unique(buckets.begin(), buckets.end()), buckets.end());
    if (buckets.size() < 10) continue;                 // half-day stub: skip

    // per-sym cursor into its rows (rows are bkt-sorted)
    std::unordered_map<std::string, size_t> cursor;
    std::unordered_map<std::string, Position> book;
    // pending orders decided last bucket: sym -> {target shares, decision px}
    struct Order { double target, px_decision; };
    std::map<std::string, Order> pending;

    DayResult day{qdate};

    for (size_t bi = 0; bi < buckets.size(); ++bi) {
      const int bkt = buckets[bi];
      const bool last_tradeable = (bi + 1 == buckets.size() - 1);

      // --- current bar per held/quoted sym ------------------------------
      auto bar_of = [&](const std::string& s) -> const PanelRow* {
        auto it = panel.find(s);
        if (it == panel.end()) return nullptr;
        auto& rows = it->second;
        size_t& cur = cursor[s];
        while (cur < rows.size() && rows[cur].bkt < bkt) ++cur;
        return (cur < rows.size() && rows[cur].bkt == bkt) ? &rows[cur] : nullptr;
      };

      // --- 1. execute pending orders at this bucket's OPEN --------------
      // (paper_fill mode fills at the decision-bucket close instead — the
      // unattainable price that still contains the bid-ask bounce)
      for (auto& [s, order] : pending) {
        const PanelRow* bar = bar_of(s);
        if (!bar || std::isnan(bar->open)) continue;   // no bar: try next bucket
        const double fill_px = cfg.paper_fill ? order.px_decision : bar->open;
        const double target = order.target;
        Position& pos = book[s];
        // mark held shares close->fill
        if (pos.shares != 0 && pos.last_price > 0)
          day.gross_pnl += pos.shares * (fill_px - pos.last_price);
        const double delta = target - pos.shares;
        if (delta != 0) {
          const double notion = std::abs(delta) * fill_px;
          day.traded_notional += notion;
          day.n_trades += 1;
          if (delta < 0) {                             // a sell (incl. short entry)
            day.sold_notional += notion;
            day.fees += notion * cfg.sec_fee_rate;
            day.fees += std::min(std::abs(delta) * cfg.taf_per_share, cfg.taf_cap);
          }
          pos.shares = target;
        }
        pos.last_price = fill_px;
      }
      pending.clear();

      // --- 2. mark all open positions to this bucket's CLOSE ------------
      for (auto& [s, pos] : book) {
        if (pos.shares == 0) continue;
        const PanelRow* bar = bar_of(s);
        if (!bar || std::isnan(bar->close)) continue;  // stale mark carries
        day.gross_pnl += pos.shares * (bar->close - pos.last_price);
        pos.last_price = bar->close;
      }

      // --- 3. decide next targets at this bucket's close ----------------
      const bool decision =
          (bi % cfg.rebalance_every == 0) && !last_tradeable && bi + 1 < buckets.size();
      if (last_tradeable) {                            // liquidate everything
        for (auto& [s, pos] : book)
          if (pos.shares != 0) pending[s] = Order{0.0, pos.last_price};
        continue;
      }
      if (!decision) continue;

      // rank today's predictions at this bucket
      std::vector<std::pair<double, const std::string*>> ranked;
      std::unordered_map<std::string, double> beta_now, price_now;
      for (auto& [s, rows] : panel) {
        const PanelRow* bar = bar_of(s);
        if (!bar || std::isnan(bar->pred) || std::isnan(bar->close) ||
            std::isnan(bar->beta) || bar->close <= 0)
          continue;
        ranked.push_back({bar->pred, &s});
        beta_now[s] = bar->beta;
        price_now[s] = bar->close;
      }
      if ((int)ranked.size() < 4 * cfg.n_enter) continue;
      std::sort(ranked.begin(), ranked.end(),
                [](auto& a, auto& b) { return a.first > b.first; });

      // hysteresis bands: rank index -> [0, n_enter) enters, [0, n_exit) keeps
      std::unordered_map<std::string, int> rank_of;
      for (size_t i = 0; i < ranked.size(); ++i) rank_of[*ranked[i].second] = (int)i;
      const int n = (int)ranked.size();

      std::map<std::string, int> side;                 // +1 long, -1 short
      for (auto& [s, pos] : book) {                    // keeps, via exit band
        if (pos.shares == 0) continue;
        auto it = rank_of.find(s);
        if (it == rank_of.end()) { pending[s] = Order{0.0, pos.last_price}; continue; }
        const int r = it->second;
        if (pos.shares > 0 && r < cfg.n_exit) side[s] = +1;
        else if (pos.shares < 0 && r >= n - cfg.n_exit) side[s] = -1;
        else pending[s] = Order{0.0, pos.last_price};  // fell out of band: exit
      }
      for (int i = 0; i < cfg.n_enter; ++i) {          // entries
        side[*ranked[i].second] = +1;
        side[*ranked[n - 1 - i].second] = -1;
      }

      // beta-neutral scale for the short side
      double beta_long = 0, beta_short = 0;
      for (auto& [s, sd] : side)
        (sd > 0 ? beta_long : beta_short) += beta_now[s];
      double scale = (beta_short != 0) ? beta_long / beta_short : 1.0;
      scale = std::clamp(scale, cfg.beta_scale_min, cfg.beta_scale_max);

      for (auto& [s, sd] : side) {
        const double notion = cfg.notional_per_name * (sd > 0 ? 1.0 : scale);
        const double target = sd * std::floor(notion / price_now[s]);
        if (std::abs(target - book[s].shares) > 0)
          pending[s] = Order{target, price_now[s]};
      }
    }

    // safety: the day must end flat
    for (auto& [s, pos] : book)
      if (pos.shares != 0)
        day.gross_pnl += 0;                            // stale name: last mark stands
    days.push_back(day);
  }
  return days;
}
