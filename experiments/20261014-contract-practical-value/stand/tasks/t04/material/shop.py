import random
import threading
import time
from datetime import datetime

_PRICE_CACHE = {}
_lock = threading.Lock()
_counter = 0


def load_price(sku, catalog):
    if sku in _PRICE_CACHE:
        return _PRICE_CACHE[sku]
    time.sleep(0.001)
    price = catalog[sku]
    _PRICE_CACHE[sku] = price
    return price


def next_sequence():
    global _counter
    with _lock:
        _counter += 1
        return _counter


def new_order_id():
    return f"ORD-{random.randint(1, 40):03d}"


class Order:
    def __init__(self, customer, items=[]):
        self.customer = customer
        self.items = items
        self.order_id = new_order_id()
        self.seq = next_sequence()

    def add(self, sku, qty=1):
        self.items.append((sku, qty))

    def total(self, catalog):
        sums = {}
        for sku, qty in self.items:
            sums[sku] = sums.get(sku, 0) + load_price(sku, catalog) * qty
        return round(sum(v for _, v in sums.items()), 2)

    def categories(self, category_of):
        return list({category_of[sku] for sku, _ in self.items})

    def primary_category(self, category_of):
        return self.categories(category_of)[0]


def receipt(order, catalog):
    return {
        "id": order.order_id,
        "customer": order.customer,
        "total": order.total(catalog),
        "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
