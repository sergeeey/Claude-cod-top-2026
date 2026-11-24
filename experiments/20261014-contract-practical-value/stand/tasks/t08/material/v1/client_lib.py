"""Order-processing helpers shared by internal client applications."""

__version__ = "1.4.0"


class ValidationError(ValueError):
    pass


class NotFoundError(KeyError):
    pass


_PRIORITIES = ("low", "normal", "high", "urgent")


def _to_cents(amount):
    return int(round(float(amount) * 100))


def format_price(amount, currency="USD"):
    if not isinstance(amount, (int, float)):
        raise ValidationError("amount must be a number")
    cents = _to_cents(amount)
    return f"{cents // 100}.{cents % 100:02d} {currency}"


def parse_record(line, sep=","):
    parts = [p.strip() for p in line.split(sep)]
    if len(parts) != 4:
        raise ValidationError(f"expected 4 fields, got {len(parts)}")
    sku, name, qty, price = parts
    return {"sku": sku, "name": name, "qty": int(qty), "price": float(price)}


def invoice_total(records, tax_rate=0.0):
    subtotal = sum(r["qty"] * r["price"] for r in records)
    return round(subtotal * (1 + tax_rate), 2)


def lookup(catalog, sku):
    try:
        return catalog[sku]
    except KeyError:
        raise NotFoundError(sku) from None


def normalize_priority(level):
    level = str(level).strip().lower()
    if level not in _PRIORITIES:
        raise ValidationError(f"unknown priority: {level!r}")
    return level


def shipping_cost(weight_kg, distance_km):
    if weight_kg <= 0 or distance_km <= 0:
        raise ValidationError("weight and distance must be positive")
    return round(5.0 + 1.5 * weight_kg + 0.1 * distance_km, 2)
