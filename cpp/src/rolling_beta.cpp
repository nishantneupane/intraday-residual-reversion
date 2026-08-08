// rolling_beta.cpp — fetch panel from q, run the regressions, upload betas.

#include "rolling_beta.hpp"

#include <Eigen/Dense>
#include <cmath>
#include <cstring>
#include <stdexcept>

#include "kdb_conn.hpp"

// ---------------------------------------------------------------------------
// 1. FETCH — one IPC query builds the whole regression panel server-side.
//    q does what q is good at (joins, per-symbol returns); C++ receives one
//    flat table: sym, date, exret, mkt_rf, smb, hml, wml sorted by sym, date.
// ---------------------------------------------------------------------------
static const char* PANEL_QUERY = R"Q(
d: update ret: -1 + close % prev close by sym from `sym`date xasc select sym, date, close from daily;
t: ej[`date; select from d where not null ret; select date, mkt_rf, smb, hml, wml, rf from factors];
`sym`date xasc select sym: value sym, date, exret: ret - rf, mkt_rf, smb, hml, wml from t
)Q";
// (`value`, not `symbol$: the sym column arrives as an ENUMERATION over the
// hdb sym file — `value` resolves it back to plain symbols for the wire)

// find a column's vector inside a K table by name
static K column(K table, const char* name) {
  K dict = table->k;                       // a table is a flipped dict
  K names = kK(dict)[0], cols = kK(dict)[1];
  for (long long i = 0; i < names->n; ++i)
    if (0 == std::strcmp(kS(names)[i], name)) return kK(cols)[i];
  throw std::runtime_error(std::string("column missing: ") + name);
}

Panel fetch_panel(KdbConnection& conn) {
  KResult res = conn.query(PANEL_QUERY);
  if (res->t != 98) throw std::runtime_error("expected a table from panel query");

  K sym = column(res.get(), "sym"),   date = column(res.get(), "date");
  K exr = column(res.get(), "exret"), mkt = column(res.get(), "mkt_rf");
  K smb = column(res.get(), "smb"),   hml = column(res.get(), "hml");
  K wml = column(res.get(), "wml");
  const long long n = date->n;

  Panel p;
  p.rows.resize(n);
  for (long long i = 0; i < n; ++i) {
    p.rows[i] = DailyRow{kI(date)[i], kF(exr)[i],
                         {kF(mkt)[i], kF(smb)[i], kF(hml)[i], kF(wml)[i]}};
    // new symbol block? record its start (rows are sorted by sym)
    if (i == 0 || std::strcmp(kS(sym)[i], kS(sym)[i - 1]) != 0) {
      p.syms.emplace_back(kS(sym)[i]);
      p.starts.push_back(i);
    }
  }
  p.starts.push_back(n);
  return p;
}

// ---------------------------------------------------------------------------
// 2. FIT — the actual quant work. One 5-parameter WLS per (sym, day).
// ---------------------------------------------------------------------------
static BetaRow fit_one(const DailyRow* rows, int first, int t, const FitConfig& cfg) {
  const int lo = std::max(first, t - cfg.window + 1);   // window start
  const int nobs = t - lo + 1;

  Eigen::Matrix<double, 5, 5> A = Eigen::Matrix<double, 5, 5>::Zero();  // XᵀWX
  Eigen::Matrix<double, 5, 1> b = Eigen::Matrix<double, 5, 1>::Zero();  // XᵀWy
  double sw = 0, swy = 0, swyy = 0;                     // for weighted R²

  for (int j = lo; j <= t; ++j) {
    const double w = std::pow(0.5, double(t - j) / cfg.half_life);
    Eigen::Matrix<double, 5, 1> x;
    x << 1.0, rows[j].factors[0], rows[j].factors[1], rows[j].factors[2], rows[j].factors[3];
    const double y = rows[j].exret;
    A.noalias() += w * x * x.transpose();
    b.noalias() += w * x * y;
    sw += w; swy += w * y; swyy += w * y * y;
  }
  A.diagonal().array() += cfg.ridge;                    // + λI
  const Eigen::Matrix<double, 5, 1> beta = A.ldlt().solve(b);

  // weighted R² = 1 - SSR/SST (recompute residuals; 250 rows is cheap)
  double ssr = 0;
  for (int j = lo; j <= t; ++j) {
    const double w = std::pow(0.5, double(t - j) / cfg.half_life);
    const double fit = beta[0] + beta[1] * rows[j].factors[0] + beta[2] * rows[j].factors[1]
                     + beta[3] * rows[j].factors[2] + beta[4] * rows[j].factors[3];
    const double e = rows[j].exret - fit;
    ssr += w * e * e;
  }
  const double sst = swyy - swy * swy / sw;             // variance around weighted mean
  const double r2 = sst > 0 ? 1.0 - ssr / sst : 0.0;

  return BetaRow{rows[t].date, "", beta[0], beta[1], beta[2], beta[3], beta[4], r2, nobs};
}

std::vector<BetaRow> fit_all(const Panel& panel, const FitConfig& cfg) {
  std::vector<BetaRow> out;
  out.reserve(panel.rows.size());
  for (size_t s = 0; s < panel.syms.size(); ++s) {
    const int first = int(panel.starts[s]), last = int(panel.starts[s + 1]) - 1;
    for (int t = first + cfg.min_obs - 1; t <= last; ++t) {
      BetaRow row = fit_one(panel.rows.data(), first, t, cfg);
      row.sym = panel.syms[s];
      out.push_back(std::move(row));
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// 3. UPLOAD — build a K table in C++ and hand it to the server, then persist.
//    This is real "IPC writeback": the server receives a native table object,
//    no CSV middleman. ktn() allocates typed vectors; ss() interns a symbol;
//    xD(names, cols) makes a dict, xT() flips it into a table. k(...) with
//    extra arguments passes them to the q function AND consumes our reference.
// ---------------------------------------------------------------------------
void upload_betas(KdbConnection& conn, const std::vector<BetaRow>& rows) {
  const long long n = (long long)rows.size();
  K date = ktn(KD, n), sym = ktn(KS, n);
  K alpha = ktn(KF, n), mkt = ktn(KF, n), smb = ktn(KF, n);
  K hml = ktn(KF, n), wml = ktn(KF, n), r2 = ktn(KF, n), nobs = ktn(KJ, n);
  for (long long i = 0; i < n; ++i) {
    const BetaRow& r = rows[i];
    kI(date)[i] = r.date;
    kS(sym)[i] = ss(const_cast<char*>(r.sym.c_str()));
    kF(alpha)[i] = r.alpha; kF(mkt)[i] = r.mkt; kF(smb)[i] = r.smb;
    kF(hml)[i] = r.hml;     kF(wml)[i] = r.wml; kF(r2)[i] = r.r2;
    kJ(nobs)[i] = r.nobs;
  }
  K names = ktn(KS, 9);
  const char* colnames[9] = {"date","sym","alpha","mkt","smb","hml","wml","r2","nobs"};
  for (int i = 0; i < 9; ++i) kS(names)[i] = ss(const_cast<char*>(colnames[i]));
  K table = xT(xD(names, knk(9, date, sym, alpha, mkt, smb, hml, wml, r2, nobs)));

  conn.call("{`betas set `date`sym xasc x; count betas}", table);
  // `:. is the server's CURRENT directory — which is the HDB root, because
  // `\l data/hdb` cd's into the database it loads. A relative "data/hdb"
  // here would nest a second copy inside the first (ask us how we know).
  conn.query("(.Q.dd[`:.; `betas,`]) set .Q.en[`:.; betas]");
}
