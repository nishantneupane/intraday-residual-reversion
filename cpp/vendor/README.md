KX C API vendor files, fetched 2026-08-07 from github.com/KxSystems/kdb (Apache 2.0):
- k.h  : the (famously terse) C API header
- c.o  : IPC client object. Published under m64/ but actually a universal
         binary (x86_64 + arm64), so we link it natively on Apple Silicon.
