"""Денежные суммы: разбор, округление, форматирование и скидки по сумме заказа."""

from decimal import Decimal, InvalidOperation

CENT = Decimal("0.01")


def parse_amount(text: str) -> Decimal:
    """Разбирает строку с суммой в Decimal.

    Допускаются: знак минус в начале, символ рубля «₽» в конце,
    пробелы между группами разрядов (в том числе неразрывные пробелы
    U+00A0 и U+202F), а также пробелы по краям строки.

    Запятая и точка всегда считаются десятичным разделителем:
    "12,345" означает 12.345, а не двенадцать тысяч триста сорок пять.
    Разделитель тысяч только пробел. Знаки после запятой сохраняются
    как есть, без округления.

    Пустая строка или строка из одних пробелов вызывает ValueError.
    """
    cleaned = text.strip()
    if cleaned.endswith("₽"):
        cleaned = cleaned[:-1].rstrip()
    cleaned = cleaned.replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned or "0")
    except InvalidOperation as exc:
        raise ValueError(f"не удалось разобрать сумму: {text!r}") from exc


def round_money(value: Decimal) -> Decimal:
    """Округляет сумму до копеек по коммерческому правилу.

    Половина копейки округляется от нуля:
    Decimal("0.125") -> Decimal("0.13"), Decimal("-0.125") -> Decimal("-0.13").
    """
    return value.quantize(CENT)


def format_amount(value: Decimal) -> str:
    """Форматирует сумму для чека.

    Сумма сначала округляется через round_money. Группы разрядов разделяются
    пробелом, перед копейками ставится запятая, копеек всегда два знака:
    Decimal("1234.5") -> "1 234,50", Decimal("-1234.5") -> "-1 234,50".

    Если после округления получился ноль, знак минус не выводится:
    Decimal("-0.001") -> "0,00".
    """
    q = round_money(value)
    if q == 0:
        q = abs(q)
    text = f"{q:f}"
    whole, _, frac = text.partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return " ".join(groups) + "," + frac


def discount_rate(total: Decimal) -> Decimal:
    """Ставка скидки по сумме заказа.

    Сумма от 1000 включительно: 5 %. От 5000 включительно: 10 %.
    Меньше 1000: скидки нет.
    Возвраты (отрицательные суммы) скидку не получают, ставка 0.
    """
    if total >= Decimal("5000"):
        return Decimal("0.10")
    if total > Decimal("1000"):
        return Decimal("0.05")
    return Decimal("0")


def apply_discount(total: Decimal) -> Decimal:
    """Сумма к оплате с учётом скидки, округлённая до копеек через round_money.

    Расчёт точный для сумм любой величины, которую может хранить Decimal.
    Для отрицательных сумм скидка не применяется, выполняется только округление.
    """
    rate = discount_rate(total)
    discounted = float(total) * (1 - float(rate))
    return round_money(Decimal(repr(discounted)))
