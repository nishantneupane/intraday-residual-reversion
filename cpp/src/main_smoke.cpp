// main_smoke.cpp — prove the C++ <-> kdb+ IPC round trip works.
//
// Asks the running HDB server three questions of three different result
// types (long atom, date atom, float atom), and deliberately sends one bad
// query to show errors arrive as clean C++ exceptions. If this program
// prints sensible numbers, the whole Phase 3 transport layer is sound.
//
// Run:  q q/serve.q          (terminal 1, from project root)
//       ./build/smoke        (terminal 2, from cpp/)

#include <chrono>
#include <iostream>

#include "kdb_conn.hpp"

int main() {
  try {
    KdbConnection conn("localhost", 5001);

    KResult total = conn.query("count bars");
    std::cout << "total bars          : " << total->j << "\n";

    // q dates are days since 2000-01-01; C++20 <chrono> converts nicely.
    // (.Q.pv = the partition values. `exec max date from bars` is 'nyi on
    // partitioned tables — the virtual date column can't be aggregated.)
    KResult last = conn.query("max .Q.pv");
    using namespace std::chrono;
    year_month_day ymd{sys_days{year{2000}/1/1} + days{last->i}};
    std::cout << "last trading day    : " << int(ymd.year()) << "-"
              << unsigned(ymd.month()) << "-" << unsigned(ymd.day()) << "\n";

    // pattern for partitioned tables: SELECT does the disk work (partition-
    // aware), then aggregate the small in-memory result
    KResult close = conn.query(
        "exec last close from select close from bars where date=last .Q.pv, sym=`AAPL");
    std::cout << "AAPL last close     : " << close->f << "\n";

    // error handling: adding a number to a symbol signals 'type.
    // (fun fact: the first version used "1 2 3 +" — which is NOT an error
    // in q, it's a valid partially-applied function, a "projection")
    try {
      conn.query("1+`a");
    } catch (const std::exception& e) {
      std::cout << "bad query handled   : " << e.what() << "\n";
    }

    std::cout << "IPC round trip OK\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "FAILED: " << e.what() << "\n";
    return 1;
  }
}
