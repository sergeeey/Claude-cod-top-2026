Я не смог записать `report.md`. Запись файла была отклонена с сообщением, что субагенты возвращают результат текстом. Обходить это через Bash я не стал. Ниже полный текст отчёта, его можно сохранить как `<HOME>/AppData/Local/Temp/claude/D--Claude-cod-top-2026/29a715b1-3478-43c8-b908-635a18c4834e/scratchpad/practical/runs/x15da/report.md`.

---

# Проверка заявления "client_lib 2.0.0 полностью обратно совместима с 1.x"

## Вывод

Заявление в CHANGELOG неверно (строки 5-7: "fully backward compatible... keeps working without any changes"). Из 7 шагов `client_app.py` на v2 только 2 дают тот же результат, что на v1. Остальные 5 отличаются. Они вызваны пунктами раздела "Changed", которые в CHANGELOG описаны расплывчато и без слова "breaking". Шаг `priority` в CHANGELOG не упомянут вообще.

## Чем подтверждено

Я запустил `python client_app.py v1` и `python client_app.py v2` в папке проекта и сравнил выводы через `diff`. Граничные случаи проверил отдельным скриптом, который вызывает обе версии библиотеки напрямую.

| Шаг клиента | v1 (1.4.0) | v2 (2.0.0) | Тип |
|---|---|---|---|
| items | `Widget x4, Gadget x1` | `FAILED KeyError: 'name'` | падение |
| subtotal | `20.0` | `24.0` | тихая смена результата |
| label | `19.90 EUR` | `FAILED TypeError: ... unexpected keyword argument 'currency'` | падение |
| unit price A-100 | `2.5` | `2.5` | без изменений |
| unit price Z-999 | `0.0` | `FAILED NotFoundError: Z-999` | падение (потеря обработки ошибки) |
| priority | `high` | `FAILED ValidationError: unknown priority: 'High'` | падение |
| shipping | `38.0` | `455.2` | тихая смена результата |

### Что сломается или изменится у клиента

1. **`invoice_total`: дефолт `tax_rate` изменился с 0.0 на 0.2** (v1:36, v2:44).
   - Клиент вызывает `lib.invoice_total(records)` без налога (`client_app.py:44`). Итог 20.0 стал 24.0 (+20%), ошибки нет.
   - С явным `tax_rate=0.0` в v2 получается 20.0, то есть причина именно в дефолте.
   - В CHANGELOG это записано как "defaults aligned with accounting requirements".
   - Это самый опасный пункт: ночной инвойсинг выставит завышенные суммы без единого сигнала.
2. **`shipping_cost`: поменялся порядок параметров** с `(weight_kg, distance_km)` на `(distance_km, weight_kg)` (v1:55, v2:63).
   - Клиент вызывает позиционно `shipping_cost(2.0, 300)` (`client_app.py:49`). Было 38.0, стало 455.2: число 300 теперь читается как вес.
   - Оба значения положительные, проверка не срабатывает, ошибки нет.
   - Вызов по именам (`weight_kg=2.0, distance_km=300`) даёт 38.0 в обеих версиях.
   - В CHANGELOG это "Parameter naming unified". О перестановке позиций не сказано.
3. **`parse_record`: ключ `"name"` переименован в `"title"`** (v1:33, v2:41).
   - Клиент читает `r['name']` (`client_app.py:43`) и получает `KeyError: 'name'`.
   - В CHANGELOG: "Record fields aligned with catalog terminology".
4. **`format_price`: параметр `currency` переименован в `currency_code`** (v1:21, v2:23).
   - Клиент передаёт `currency="EUR"` (`client_app.py:45`) и получает `TypeError`.
   - Позиционный вызов `format_price(19.9, "EUR")` работает в обеих версиях.
   - В CHANGELOG: "Parameter naming unified".
5. **`NotFoundError` перестал быть наследником `KeyError`.** В v1 это `class NotFoundError(KeyError)`, в v2 `class NotFoundError(LookupError)`.
   - Проверка `issubclass(NotFoundError, KeyError)` даёт True в v1 и False в v2.
   - Клиент ловит `except KeyError` в `unit_price` (`client_app.py:28`). Для неизвестного SKU вместо `0.0` теперь падение.
   - В CHANGELOG: "Exception hierarchy clarified".
   - Заметить это в обзоре кода труднее всего: вызов `lookup` в клиенте не менялся.
6. **`normalize_priority` стал чувствителен к регистру**: убрано `.lower()` (v1:49, v2:57).
   - `"High"` и `"HIGH"` теперь дают `ValidationError`, а в v1 возвращали `high`.
   - Клиент вызывает `normalize_priority("High")` (`client_app.py:48`) и падает.
   - В CHANGELOG об этом нет ни слова.

### Что только выглядит опасным и не ломает клиента

- **Переименование `_to_cents` в `_as_cents`.** Это приватная функция, клиент её не использует (в `client_app.py` ноль вхождений). Формально `lib._to_cents` исчезла и даёт `AttributeError`, но публичным API она не была.
- **`format_price` теперь принимает `Decimal` и строки.** Это расширение допустимых входов. `int` и `float` работают как раньше, и клиентский результат тот же (`19.90 EUR`).
  - Нечисловая строка `'abc'` по-прежнему даёт `ValidationError`, но текст сообщения другой.
  - Риск остаётся только у кода, который полагался на `ValidationError` для строк вроде `"12"`.
- **`parse_record(..., strict=False)`.** Новый необязательный параметр с безопасным дефолтом. Вызов `parse_record("A,W,0,1")` принимает qty=0 в обеих версиях.
- **`import Decimal` и смена `__version__`.** Безвредно, клиент только печатает версию.
- **Шаг `unit price A-100`.** Идентичен в обеих версиях.

## Ограничения проверки

- Я проверил один клиент (`client_app.py`) и две копии библиотеки (`v1/`, `v2/`). Других клиентов не видел. Для остальных нужно искать во всей кодовой базе вызовы `invoice_total`, `shipping_cost`, `["name"]`, `currency=`, `except KeyError`, `normalize_priority`.
- Тестов у библиотеки в папке нет. Поведение подтверждено только запуском клиента и точечных вызовов.
- Оценка серьёзности (тихие изменения сумм опаснее всего) моя. Сколько реальных клиентов вызывают `invoice_total` без `tax_rate` и `shipping_cost` позиционно, я не знаю.

## Что предлагаю

1. **Вернуть совместимость там, где это дёшево.** Тогда заявление в CHANGELOG станет правдой:
   - `invoice_total`: вернуть `tax_rate=0.0` или сделать аргумент обязательным.
   - `shipping_cost`: вернуть порядок `(weight_kg, distance_km)`.
   - `parse_record`: на переходный период отдавать оба ключа, `name` и `title`.
   - `format_price`: принимать и `currency`, и `currency_code` (для старого имени добавить `DeprecationWarning`).
   - `class NotFoundError(KeyError, LookupError)`, чтобы старые `except KeyError` продолжили работать.
   - `normalize_priority`: вернуть `.lower()`.
2. **Если поведение менять нужно, выпускать честно как breaking release.** Убрать "fully backward compatible" и перечислить все шесть пунктов в разделе "Breaking changes" со старым и новым поведением. Тихие изменения (налог по умолчанию и порядок аргументов `shipping_cost`) выделить отдельно. Приложить гайд по миграции. Номер 2.0.0 для этого подходит.
3. **Добавить в CI проверку совместимости.** Прогонять набор вызовов клиента на v1 и v2 и сравнивать результат (то, что я сделал через `diff`). Тогда расхождение будет находиться до релиза.
4. **Подготовить клиенты.** В `client_app.py` стоит перейти на вызовы, которые работают на обеих версиях:
   - `tax_rate` передавать явно;
   - `shipping_cost` вызывать по именам аргументов;
   - ловить `except LookupError`;
   - `format_price` вызывать позиционно.

   Поле `name`/`title` и регистр приоритета этим не лечатся, там нужна правка либо библиотеки, либо клиента.

---

Файлы, которые я читал и запускал: `CHANGELOG.md`, `client_app.py`, `v1/client_lib.py`, `v2/client_lib.py` в папке `<HOME>/AppData/Local/Temp/claude/D--Claude-cod-top-2026/29a715b1-3478-43c8-b908-635a18c4834e/scratchpad/practical/runs/x15da/`. Временные выводы и скрипт проверки лежат в `/tmp`, в проект я ничего не записывал.