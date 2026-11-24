import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tasks", "t05", "material"))
sys.setswitchinterval(1e-6)

from orders import Order, OrderService, PaymentGateway  # noqa: E402
from warehouse import Warehouse, transfer  # noqa: E402


def run_threads(n, fn):
    ts = [threading.Thread(target=fn, daemon=True) for _ in range(n)]
    for t in ts:
        t.start()
    return ts


def p1_check_then_act(rounds=1500):
    worst = 0
    oversold = 0
    for _ in range(rounds):
        w = Warehouse("w", {"A": 2})
        ok = []
        gate = threading.Barrier(8)

        def buyer():
            gate.wait()
            if w.reserve("A", 1):
                ok.append(1)

        for t in run_threads(8, buyer):
            t.join()
        stock, _ = w.snapshot()
        worst = min(worst, stock["A"])
        oversold += max(0, len(ok) - 2)
    print(f"P1 check-then-act: min stock={worst}, oversold units total={oversold}")


def p6_split_update(rounds=10):
    violations = 0
    lost = 0
    for _ in range(rounds):
        w = Warehouse("w", {"A": 100000})
        stop = threading.Event()

        def buyer():
            for _ in range(2000):
                w.reserve("A", 1)

        def observer():
            nonlocal violations
            while not stop.is_set():
                s, r = w.snapshot()
                if s.get("A", 0) + r.get("A", 0) != 100000:
                    violations += 1

        obs = run_threads(1, observer)
        for t in run_threads(8, buyer):
            t.join()
        stop.set()
        obs[0].join()
        s, r = w.snapshot()
        lost += s["A"] + r.get("A", 0) - 100000
    print(
        f"P6 split update: snapshot invariant violations={violations}, final stock+reserved drift={lost}"
    )


def p5_report_during_mutation():
    w = Warehouse("w", {f"s{i}": 1 for i in range(200)})
    errors = 0
    stop = threading.Event()

    def adder():
        i = 0
        while not stop.is_set():
            w.restock(f"n{i}", 1)
            i += 1

    ts = run_threads(2, adder)
    for _ in range(300):
        try:
            w.report()
        except RuntimeError:
            errors += 1
    stop.set()
    for t in ts:
        t.join()
    print(f"P5 report while mutating: RuntimeError count={errors}/300")


def p3_deadlock():
    a = Warehouse("a", {"X": 10**6})
    b = Warehouse("b", {"X": 10**6})

    def ab():
        for _ in range(20000):
            transfer(a, b, "X", 1)

    def ba():
        for _ in range(20000):
            transfer(b, a, "X", 1)

    t1 = threading.Thread(target=ab, daemon=True)
    t2 = threading.Thread(target=ba, daemon=True)
    t1.start()
    t2.start()
    t1.join(10)
    t2.join(10)
    print(f"P3 lock order: deadlocked={t1.is_alive() or t2.is_alive()}")


def p4_retry_and_p2_counter():
    w = Warehouse("w", {"A": 100000})
    gw = PaymentGateway(failure_rate=0.3, seed=1)
    svc = OrderService(w, gw, workers=8, max_attempts=3)
    svc.start()
    n = 3000
    for i in range(n):
        svc.submit(Order(f"o{i}", "A", 1, 1.0))
    svc.stop()
    _, r = w.snapshot()
    per = {}
    for oid, _ in gw.charges:
        per[oid] = per.get(oid, 0) + 1
    multi = sum(1 for v in per.values() if v > 1)
    print(
        f"P4 retry: orders={n}, units reserved={r['A']}, charges={len(gw.charges)}, orders charged >1 time={multi}"
    )
    print(f"P2 counter: processed={svc.processed} expected={n}")


def decoys():
    w = Warehouse("w", {"A": 0})
    w.restock_many({"A": 5, "B": 3})
    a = Warehouse("a", {"X": 10000})
    b = Warehouse("b", {"X": 10000})

    def one_way():
        for _ in range(500):
            transfer(a, b, "X", 1)

    def restocker():
        for _ in range(500):
            a.restock_many({"X": 1})

    ts = run_threads(4, one_way) + run_threads(4, restocker)
    for t in ts:
        t.join()
    total = a.snapshot()[0]["X"] + b.snapshot()[0]["X"]
    print(
        f"D2 RLock reentry ok: {w.snapshot()[0]}; D3 one-way transfer+restock conserved: {total == 20000 + 2000}"
    )


if __name__ == "__main__":
    decoys()
    p1_check_then_act()
    p6_split_update()
    p5_report_during_mutation()
    p4_retry_and_p2_counter()
    p3_deadlock()
