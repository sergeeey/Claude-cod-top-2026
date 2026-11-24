from shop import Order, load_price

CATALOG = {"pen": 1.5, "book": 12.5, "apple": 0.4}
PROMO = {"pen": 1.2, "book": 10.0, "apple": 0.4}


def test_load_price_regular():
    assert load_price("apple", CATALOG) == 0.4


def test_promo_order_total():
    o = Order("dave", [])
    o.add("pen", 2)
    o.add("book")
    assert o.total(PROMO) == 15.5
