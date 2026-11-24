import cProfile
import pstats
import sys
import time

sys.path.insert(0, sys.argv[1])
import datagen  # noqa: E402
import service  # noqa: E402

datagen.write_aliases()
pr = cProfile.Profile()
pr.enable()
req = datagen.make_requests(n=1200)
res, _ = service.process_batch(req)
p = service.encode_batch(res)
s = service.summarize(res)
pr.disable()
pstats.Stats(pr).sort_stats("cumulative").print_stats(25)

# plain timings without profiler, per stage
t0 = time.perf_counter()
req = datagen.make_requests(n=1200)
t1 = time.perf_counter()
res, _ = service.process_batch(req)
t2 = time.perf_counter()
p = service.encode_batch(res)
t3 = time.perf_counter()
service.summarize(res)
t4 = time.perf_counter()
print(f"gen {t1 - t0:.3f} process {t2 - t1:.3f} encode {t3 - t2:.3f} summarize {t4 - t3:.4f}")

# component costs inside handle_request
a = service.load_aliases()
t = time.perf_counter()
for _ in range(1200):
    service.load_aliases()
print(f"load_aliases x1200 {time.perf_counter() - t:.3f}")
import re  # noqa: E402

t = time.perf_counter()
for _ in range(1200):
    re.compile("|".join(re.escape(k) for k in a))
print(f"regex build x1200 {time.perf_counter() - t:.3f}")
rx = re.compile("|".join(re.escape(k) for k in a))
toks = [tok for r in req for tok in r["text"].lower().split()]
t = time.perf_counter()
for tok in toks:
    rx.fullmatch(tok)
print(f"fullmatch all tokens {time.perf_counter() - t:.3f}")
t = time.perf_counter()
for tok in toks:
    tok in a
print(f"dict lookup all tokens {time.perf_counter() - t:.4f}")
sw = service.STOP_WORDS
fs = frozenset(sw)
t = time.perf_counter()
for tok in toks:
    tok in sw
print(f"list membership {time.perf_counter() - t:.3f}")
t = time.perf_counter()
for tok in toks:
    tok in fs
print(f"set membership {time.perf_counter() - t:.4f}")
t = time.perf_counter()
b"".join(__import__("json").dumps(r, sort_keys=True).encode() + b"\n" for r in res)
print(f"join encode {time.perf_counter() - t:.3f}")
t = time.perf_counter()
service.validate_settings(service.SETTINGS)
print(f"validate_settings {time.perf_counter() - t:.6f}")
print("payload bytes", len(p))
