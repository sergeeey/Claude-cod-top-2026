import queue
import random
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    order_id: str
    sku: str
    qty: int
    unit_price: float


class TransientError(Exception):
    pass


class PaymentGateway:
    def __init__(self, failure_rate=0.1, seed=None):
        self.failure_rate = failure_rate
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self.charges = []

    def charge(self, order_id, amount):
        with self._lock:
            self.charges.append((order_id, amount))
            fail = self._rng.random() < self.failure_rate
        time.sleep(0.0005)
        if fail:
            raise TransientError(f"gateway timeout for {order_id}")


class OrderService:
    def __init__(self, warehouse, gateway, workers=4, max_attempts=3):
        self.warehouse = warehouse
        self.gateway = gateway
        self.max_attempts = max_attempts
        self.processed = 0
        self.results = queue.Queue()
        self._inbox = queue.Queue()
        self._threads = [
            threading.Thread(target=self._run, name=f"worker-{i}", daemon=True)
            for i in range(workers)
        ]

    def start(self):
        for t in self._threads:
            t.start()

    def submit(self, order):
        self._inbox.put(order)

    def stop(self):
        for _ in self._threads:
            self._inbox.put(None)
        for t in self._threads:
            t.join()

    def _run(self):
        while True:
            order = self._inbox.get()
            if order is None:
                break
            self._handle(order)
            self.processed += 1

    def _handle(self, order):
        for attempt in range(1, self.max_attempts + 1):
            try:
                if not self.warehouse.reserve(order.sku, order.qty):
                    self.results.put(("rejected", order.order_id))
                    return
                self.gateway.charge(order.order_id, order.qty * order.unit_price)
                self.results.put(("ok", order.order_id))
                return
            except TransientError:
                if attempt == self.max_attempts:
                    self.results.put(("failed", order.order_id))

    def drain_results(self):
        out = []
        while True:
            try:
                out.append(self.results.get_nowait())
            except queue.Empty:
                return out
