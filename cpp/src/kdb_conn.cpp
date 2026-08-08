// kdb_conn.cpp — implementation of the KX C API wrapper.
// The three raw API calls used here are the only ones in the whole project:
//   khpu(host, port, "user:pass")  connect; returns handle >0, or 0 (auth
//                                  rejected) / negative (network failure)
//   k(handle, query, (K)0)         send `query`, block for the answer; the
//                                  trailing (K)0 terminates the varargs
//   kclose(handle)                 close the socket

#include "kdb_conn.hpp"

#include <stdexcept>

KdbConnection::KdbConnection(const std::string& host, int port) {
  handle_ = khpu(const_cast<char*>(host.c_str()), port, const_cast<char*>(""));
  if (handle_ <= 0) {
    throw std::runtime_error("cannot connect to q at " + host + ":" +
                             std::to_string(port) +
                             " — is `q q/serve.q` running?");
  }
}

KdbConnection::~KdbConnection() { kclose(handle_); }

// shared post-flight checks for both entry points
static KResult check(K result, const std::string& what) {
  if (result == nullptr) {                       // socket died mid-call
    throw std::runtime_error("q connection lost during: " + what);
  }
  if (result->t == -128) {                       // q signalled an error
    std::string msg = result->s ? result->s : "unknown";
    r0(result);
    throw std::runtime_error("q error '" + msg + " from: " + what);
  }
  return KResult(result);
}

KResult KdbConnection::query(const std::string& expr) {
  return check(k(handle_, const_cast<char*>(expr.c_str()), (K)0), expr);
}

KResult KdbConnection::call(const std::string& fn, K arg) {
  return check(k(handle_, const_cast<char*>(fn.c_str()), arg, (K)0), fn);
}
