// main_betas.cpp — Phase 3 entry point: fetch panel, fit, upload, report.
// Run:  q q/serve.q      (if not already running)
//       ./cpp/build/betas

#include <chrono>
#include <iostream>

#include "kdb_conn.hpp"
#include "rolling_beta.hpp"

int main() {
  using clock = std::chrono::steady_clock;
  try {
    KdbConnection conn("localhost", 5001);

    auto t0 = clock::now();
    Panel panel = fetch_panel(conn);
    auto t1 = clock::now();
    std::cout << "panel   : " << panel.rows.size() << " sym-days, "
              << panel.syms.size() << " symbols ("
              << std::chrono::duration_cast<std::chrono::milliseconds>(t1 - t0).count()
              << " ms)\n";

    FitConfig cfg;
    std::vector<BetaRow> betas = fit_all(panel, cfg);
    auto t2 = clock::now();
    std::cout << "fitted  : " << betas.size() << " regressions ("
              << std::chrono::duration_cast<std::chrono::milliseconds>(t2 - t1).count()
              << " ms)\n";

    upload_betas(conn, betas);
    auto t3 = clock::now();
    std::cout << "uploaded: betas table set + persisted to data/hdb/betas ("
              << std::chrono::duration_cast<std::chrono::milliseconds>(t3 - t2).count()
              << " ms)\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "FAILED: " << e.what() << "\n";
    return 1;
  }
}
