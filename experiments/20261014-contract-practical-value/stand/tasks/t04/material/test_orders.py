from datetime import datetime

from shop import Order, receipt

CATALOG = {"pen": 1.5, "book": 12.5, "apple": 0.4}
CATEGORY = {"pen": "office", "book": "books", "apple": "food"}


def test_new_order_is_empty():
    o = Order("alice")
    assert o.items == []


def test_sequence_increments():
    a = Order("a", [])
    b = Order("b", [])
    assert b.seq == a.seq + 1


def test_add_items():
    o = Order("bob")
    o.add("pen", 2)
    assert o.total(CATALOG) == 3.0


def test_primary_category():
    o = Order("carol", [])
    o.add("book")
    o.add("apple", 3)
    assert o.primary_category(CATEGORY) == "books"


def test_order_ids_unique():
    orders = [Order(f"c{i}", []) for i in range(5)]
    assert len({o.order_id for o in orders}) == 5


def test_receipt():
    o = Order("erin", [])
    o.add("book")
    r = receipt(o, CATALOG)
    assert r["total"] == 12.5
    assert r["printed_at"] == datetime.now().strftime("%Y-%m-%d %H:%M:%S")
