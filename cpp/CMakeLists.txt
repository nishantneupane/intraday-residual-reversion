# Build:   cmake -S cpp -B cpp/build && cmake --build cpp/build
# Outputs land in cpp/build/.
#
# vendor/c.o is KX's precompiled IPC client (universal x86_64+arm64 object);
# it is listed as a source file so the linker folds it straight in.

cmake_minimum_required(VERSION 3.20)
project(kdb_quant CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_BUILD_TYPE Release)

# Eigen is header-only; Homebrew (Intel prefix on this machine) puts it here.
set(EIGEN_INCLUDE /usr/local/include/eigen3)

add_executable(smoke
  src/main_smoke.cpp
  src/kdb_conn.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/vendor/c.o)
target_include_directories(smoke PRIVATE include ${EIGEN_INCLUDE})

add_executable(betas
  src/main_betas.cpp
  src/rolling_beta.cpp
  src/kdb_conn.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/vendor/c.o)
target_include_directories(betas PRIVATE include ${EIGEN_INCLUDE})

add_executable(backtest
  src/main_backtest.cpp
  src/backtester.cpp
  src/kdb_conn.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/vendor/c.o)
target_include_directories(backtest PRIVATE include ${EIGEN_INCLUDE})
