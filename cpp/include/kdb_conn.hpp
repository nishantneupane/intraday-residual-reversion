// kdb_conn.hpp — a safe, minimal C++ wrapper around the KX C API.
//
// Why this file exists: the raw API (vendor/k.h) is powerful but hostile —
// one-letter typedefs, manual reference counting, errors returned as special
// objects rather than thrown. This wrapper gives the rest of our C++ code
// exactly two safe ideas:
//
//   KdbConnection conn("localhost", 5001);   // opens socket, closes on scope exit
//   KResult r = conn.query("2+2");           // sends q code, throws on error,
//                                            // releases q's memory on scope exit
//
// The K object model in 60 seconds (all you need to read our code):
//   K            a pointer to any q value (atom, list, table, dict, error)
//   x->t         its type: NEGATIVE = atom, POSITIVE = vector of that type.
//                e.g. -7 = long atom, 7 = long vector, -9/9 = float,
//                -14/14 = date (days since 2000.01.01), 98 = table, -128 = error
//   x->j, x->f   the payload of a long / float atom
//   kJ(x), kF(x) typed pointers to a vector's elements
//   r0(x)        release one reference (q's memory is refcounted; forgetting
//                r0 leaks, double-r0 crashes — hence the RAII below)

#pragma once

#include <string>
#include <utility>

#define KXVER 3
#include "../vendor/k.h"

// Owns a K object and guarantees exactly one r0() — q's unique_ptr.
class KResult {
 public:
  explicit KResult(K obj) : obj_(obj) {}
  ~KResult() { if (obj_) r0(obj_); }

  KResult(KResult&& other) noexcept : obj_(std::exchange(other.obj_, nullptr)) {}
  KResult& operator=(KResult&& other) noexcept {
    if (this != &other) { if (obj_) r0(obj_); obj_ = std::exchange(other.obj_, nullptr); }
    return *this;
  }
  KResult(const KResult&) = delete;             // copying would double-free
  KResult& operator=(const KResult&) = delete;

  K get() const { return obj_; }
  K operator->() const { return obj_; }         // r->t reads the type, etc.

 private:
  K obj_;
};

// Owns the socket to a q process. One connection = one handle = one owner.
class KdbConnection {
 public:
  KdbConnection(const std::string& host, int port);
  ~KdbConnection();
  KdbConnection(const KdbConnection&) = delete;
  KdbConnection& operator=(const KdbConnection&) = delete;

  // Send a q expression, wait for the result. Throws std::runtime_error on
  // network failure or if q signals an error ('type, 'length, ...).
  KResult query(const std::string& expr);

  // Apply a q function to one K argument built on our side (e.g. upload a
  // whole table). NOTE: consumes the caller's reference to `arg` — after
  // this call the argument must not be touched or r0()'d.
  KResult call(const std::string& fn, K arg);

 private:
  int handle_;
};
