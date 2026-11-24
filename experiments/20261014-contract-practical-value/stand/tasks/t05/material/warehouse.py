import threading
import time


class Warehouse:
    def __init__(self, name, stock=None):
        self.name = name
        self._stock = dict(stock or {})
        self._reserved = {}
        self._last_access = {}
        self._lock = threading.RLock()

    def _touch(self, sku):
        self._last_access[sku] = time.monotonic()

    def _apply_delta(self, sku, delta):
        self._stock[sku] = self._stock.get(sku, 0) + delta
        self._touch(sku)

    def available(self, sku):
        with self._lock:
            return self._stock.get(sku, 0)

    def restock(self, sku, qty):
        if qty <= 0:
            raise ValueError("qty must be positive")
        with self._lock:
            self._apply_delta(sku, qty)

    def restock_many(self, items):
        with self._lock:
            for sku, qty in items.items():
                self.restock(sku, qty)

    def reserve(self, sku, qty):
        if self.available(sku) < qty:
            return False
        self._touch(sku)
        with self._lock:
            self._apply_delta(sku, -qty)
        self._reserved[sku] = self._reserved.get(sku, 0) + qty
        return True

    def release(self, sku, qty):
        with self._lock:
            self._reserved[sku] = self._reserved.get(sku, 0) - qty
            self._apply_delta(sku, qty)

    def snapshot(self):
        with self._lock:
            return dict(self._stock), dict(self._reserved)

    def report(self):
        lines = []
        for sku, qty in self._stock.items():
            lines.append(f"{self.name}:{sku} free={qty} reserved={self._reserved.get(sku, 0)}")
        return "\n".join(lines)


def transfer(src, dst, sku, qty):
    with src._lock:
        if src._stock.get(sku, 0) < qty:
            return False
        src._apply_delta(sku, -qty)
        with dst._lock:
            dst._apply_delta(sku, qty)
    return True
