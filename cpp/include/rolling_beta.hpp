// rolling_beta.hpp — rolling Carhart factor regressions.
//
// THE MATH (PLAN.md §4.1). For each stock i and each day t, fit the last
// W=250 trading days of daily excess returns:
//
//     exret[τ] = α + β_mkt·MKT[τ] + β_smb·SMB[τ] + β_hml·HML[τ] + β_wml·WML[τ] + ε[τ]
//
// as WEIGHTED least squares, where the weight of an observation aged `a`
// days is 0.5^(a/60) — a 60-day half-life, so last week matters ~8x more
// than five months ago. Closed form, with ridge damping for stability:
//
//     β = (XᵀWX + λI)⁻¹ XᵀWy          λ = 1e-4
//
// The ridge term guards against near-singular windows (e.g. factors barely
// moving in a quiet stretch); at λ=1e-4 its bias is negligible.
//
// Rows come in sorted by (sym, date), so each symbol is one contiguous
// block and "the last 250 days" is just a slice [t-249 .. t].

#pragma once

#include <string>
#include <vector>

class KdbConnection;

struct DailyRow {                 // one (sym, date) observation, parsed from q
  int date;                       // days since 2000-01-01 (q's date epoch)
  double exret;                   // stock return minus risk-free rate
  double factors[4];              // MKT-RF, SMB, HML, WML (decimals)
};

struct BetaRow {                  // one fitted regression -> one row of `betas`
  int date;
  std::string sym;
  double alpha, mkt, smb, hml, wml;
  double r2;                      // weighted R², a fit-quality diagnostic
  int nobs;                       // observations in the window (<=250)
};

struct FitConfig {
  int window = 250;               // trading days per regression
  int min_obs = 120;              // don't fit until this much history exists
  double half_life = 60.0;        // decay of observation weights, in days
  double ridge = 1e-4;            // λ
};

// Pull the joined (daily returns x factors) panel from the q server.
// Returns per-symbol blocks: syms[i] owns rows [starts[i], starts[i+1]).
struct Panel {
  std::vector<std::string> syms;
  std::vector<size_t> starts;     // size = syms.size()+1
  std::vector<DailyRow> rows;
};
Panel fetch_panel(KdbConnection& conn);

// Fit every (sym, date) with enough history. Pure CPU, no I/O.
std::vector<BetaRow> fit_all(const Panel& panel, const FitConfig& cfg);

// Upload results as the `betas` table on the server and persist it into the
// HDB as a splayed table (survives server restarts).
void upload_betas(KdbConnection& conn, const std::vector<BetaRow>& rows);
