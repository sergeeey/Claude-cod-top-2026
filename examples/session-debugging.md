# Пример сессии: Systematic Debugging

Реальный пример: тест падает после обновления зависимости.

## Запрос пользователя

```
test_payment_process падает после обновления stripe SDK. Разберись.
```

## Stuck Detection + Evidence Policy в действии

### Попытка 1: Claude исследует

```
[VERIFIED] test_payment_process падает с:
  AttributeError: 'PaymentIntent' object has no attribute 'charges'
  (pytest output, строка 47 test_payment.py)

[CODE] В payment_service.py:23 используется intent.charges.data[0]
[DOCS] Stripe SDK v8.0 changelog: "charges" переименован в "latest_charge"
[INFERRED] Breaking change в Stripe SDK v7→v8: intent.charges → intent.latest_charge
```

Claude НЕ гадает. Он:
1. Прочитал ошибку (VERIFIED)
2. Нашёл строку в коде (CODE)
3. Проверил changelog (DOCS)
4. Сделал вывод (INFERRED — с указанием цепочки)

### Попытка 2: Минимальный фикс

```python
# payment_service.py:23
# Было:
charge = intent.charges.data[0]
# Стало:
charge = intent.latest_charge
```

### Результат

```
$ pytest tests/unit/test_payment.py -x -q
3 passed in 0.15s
```

```
[VERIFIED] 3/3 тестов проходят после замены intent.charges на intent.latest_charge
[DOCS] Stripe SDK v8.0 migration guide подтверждает: latest_charge — рекомендуемый способ
[UNKNOWN] не проверял другие места в коде, где может использоваться .charges
```

### Claude предлагает проверку

```
Рекомендую grep по всему проекту:
$ grep -rn "\.charges" src/ --include="*.py"

Это [UNKNOWN] — могут быть другие места с тем же breaking change.
```

## Что показывает этот пример

1. **Evidence Policy** — каждый факт промаркирован, видно что проверено
2. **Stuck Detection** — не потребовался (решено за 1 итерацию)
3. **Минимальный фикс** — 1 строка, не рефакторинг всего модуля
4. **[UNKNOWN]** — честное «не проверял» вместо «всё починил»
