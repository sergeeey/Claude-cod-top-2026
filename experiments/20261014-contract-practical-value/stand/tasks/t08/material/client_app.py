"""Nightly invoice job. Usage: python client_app.py [v1|v2]"""

import os
import sys

CATALOG = {
    "A-100": {"name": "Widget", "price": 2.5},
    "B-200": {"name": "Gadget", "price": 10.0},
}

LINES = [
    "A-100, Widget, 4, 2.50",
    "B-200, Gadget, 1, 10.00",
]


def load_lib():
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), version))
    import client_lib

    return client_lib


def unit_price(lib, sku):
    try:
        return lib.lookup(CATALOG, sku)["price"]
    except KeyError:
        return 0.0


def step(title, fn):
    try:
        print(f"{title}: {fn()}")
    except Exception as exc:
        print(f"{title}: FAILED {type(exc).__name__}: {exc}")


def main():
    lib = load_lib()
    print(f"client_lib {lib.__version__}")
    records = [lib.parse_record(line) for line in LINES]
    step("items", lambda: ", ".join(f"{r['name']} x{r['qty']}" for r in records))
    step("subtotal", lambda: lib.invoice_total(records))
    step("label", lambda: lib.format_price(19.9, currency="EUR"))
    step("unit price A-100", lambda: unit_price(lib, "A-100"))
    step("unit price Z-999", lambda: unit_price(lib, "Z-999"))
    step("priority", lambda: lib.normalize_priority("High"))
    step("shipping", lambda: lib.shipping_cost(2.0, 300))


if __name__ == "__main__":
    main()
