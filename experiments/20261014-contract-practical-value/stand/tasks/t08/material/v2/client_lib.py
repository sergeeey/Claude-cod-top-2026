"""Order-processing helpers shared by internal client applications."""

from decimal import Decimal

__version__ = "2.0.0"


class ValidationError(ValueError):
    pass


class NotFoundError(LookupError):
    pass


_PRIORITIES = ("low", "normal", "high", "urgent")


def _as_cents(amount):
    return int(round(float(amount) * 100))


def format_price(amount, currency_code="USD"):
    if not isinstance(amount, (int, float, Decimal, str)):
        raise ValidationError("amount must be a number")
    try:
        cents = _as_cents(amount)
    except ValueError:
        raise ValidationError(f"not a number: {amount!r}") from None
    return f"{cents // 100}.{cents % 100:02d} {currency_code}"


def parse_record(line, sep=",", strict=False):
    parts = [p.strip() for p in line.split(sep)]
    if len(parts) != 4:
        raise ValidationError(f"expected 4 fields, got {len(parts)}")
    sku, name, qty, price = parts
    qty = int(qty)
    if strict and qty <= 0:
        raise ValidationError(f"quantity must be positive, got {qty}")
    return {"sku": sku, "title": name, "qty": qty, "price": float(price)}


def invoice_total(records, tax_rate=0.2):
    subtotal = sum(r["qty"] * r["price"] for r in records)
    return round(subtotal * (1 + tax_rate), 2)


def lookup(catalog, sku):
    try:
        return catalog[sku]
    except KeyError:
        raise NotFoundError(sku) from None


def normalize_priority(level):
    level = str(level).strip()
    if level not in _PRIORITIES:
        raise ValidationError(f"unknown priority: {level!r}")
    return level


def shipping_cost(distance_km, weight_kg):
    if weight_kg <= 0 or distance_km <= 0:
        raise ValidationError("weight and distance must be positive")
    return round(5.0 + 1.5 * weight_kg + 0.1 * distance_km, 2)
