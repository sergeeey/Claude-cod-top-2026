Я не смог записать report.md. Инструмент записи отклонил вызов с текстом «Subagents should return findings as text, not write report files». Обходить запрет через Bash я не стал, поэтому отчёт ниже. Сохраните его в `report.md` сами или скажите, чтобы я попробовал записать другим способом.

💡 TIP: в client_app.py:28 `except KeyError` ловит `NotFoundError` только потому, что в 1.x он наследует `KeyError`. В v2 база сменилась на `LookupError`, и этот fallback молча перестал работать.

# client_lib 2.0.0: проверка заявления «полностью обратно совместима»

## Вывод

Заявление в CHANGELOG неверно. Для client_app.py при переходе с v1 (1.4.0) на v2 (2.0.0):

- 4 шага из 7 падают с ошибкой.
- 2 шага молча выдают другие числа.
- 1 шаг не меняется.

В публичном API 6 несовместимостей. В CHANGELOG они описаны общими словами («naming unified», «defaults aligned»). Две из них не названы совсем: смена порядка аргументов в `shipping_cost` и регистр в `normalize_priority`.

Проверен один клиент, client_app.py. Что делают другие клиенты, неизвестно. Файлы v1/ и v2/ не менялись.

## Запуск `python client_app.py v1` и `v2`

| шаг | v1 (1.4.0) | v2 (2.0.0) |
|---|---|---|
| items | `Widget x4, Gadget x1` | FAILED KeyError: 'name' |
| subtotal | 20.0 | **24.0** (без ошибки) |
| label | `19.90 EUR` | FAILED TypeError: unexpected keyword argument 'currency' |
| unit price A-100 | 2.5 | 2.5 |
| unit price Z-999 | 0.0 | FAILED NotFoundError: Z-999 |
| priority | `high` | FAILED ValidationError: unknown priority: 'High' |
| shipping | 38.0 | **455.2** (без ошибки) |

Код возврата v2-запуска равен 0. Функция `step()` (client_app.py:32-36) перехватывает все исключения, поэтому ночная задача выглядит успешной при 4 упавших шагах.

## Таблица «задокументировано / фактически»

| # | CHANGELOG | Фактически (v1 → v2) | Последствие |
|---|---|---|---|
| 1 | «Parameter naming unified» | `shipping_cost(weight_kg, distance_km)` → `(distance_km, weight_kg)`. Поменялся порядок, не имя. `shipping_cost(2.0, 300)`: 38.0 → 455.2 (в 11,98 раза) | Критично, молча |
| 2 | «invoice_total defaults aligned» | `tax_rate` 0.0 → 0.2 (v1:36, v2:44). 20.0 → 24.0 (+20%) | Критично, молча |
| 3 | «Parameter naming unified» | `format_price(currency=)` → `currency_code`. Вызов `currency="EUR"` (client_app.py:45) даёт TypeError | Падение |
| 4 | «Record fields aligned» | `parse_record`: ключ `name` → `title` (v2:41). Клиент читает `r['name']` (client_app.py:43) | Падение |
| 5 | «Exception hierarchy clarified» | `NotFoundError(KeyError)` → `(LookupError)`. `except KeyError` не ловит, вместо 0.0 летит исключение | Падение, меняется поток управления |
| 6 | не упомянуто | `normalize_priority`: убран `.lower()`. `"High"` и `"HIGH"` теперь ошибка | Падение |
| — | «format_price принимает Decimal и строки» | Верно. Побочно: `'19.9'` раньше давало ValidationError | Совместимо |
| — | «parse_record strict» | Верно, по умолчанию `False` | Совместимо |
| — | «cents helper refactored» | `_to_cents` → `_as_cents`, приватное. Клиент его не использует | Только выглядит опасным |

## Только выглядит опасным (проверено)

- Переименование приватного `_to_cents`.
- В модуле появилось публичное имя `Decimal`. Удалённых публичных имён нет.
- `ValidationError` по-прежнему наследует `ValueError`. `format_price(nan)` теперь `ValidationError` вместо голого `ValueError`; это подкласс, совместимо.
- Не изменились:
  - `format_price(19.9, "EUR")` с позиционным аргументом;
  - `shipping_cost` с именованными аргументами;
  - `invoice_total(records, tax_rate=0.2)`;
  - `lookup` при успехе;
  - `normalize_priority(" high ")`.
- Текст `str(NotFoundError('Z-999'))` стал без кавычек. У client_app нет кода, который разбирает текст ошибки.

Вне темы совместимости, одинаково в обеих версиях: `format_price(-5.5)` возвращает `-6.50 USD`. Это существующая ошибка.

## Чем подтверждено

- Сравнение сигнатур через `inspect.signature` и MRO исключений, скрипт запускался с `python -I`.
- `grep "lib\.\(_\|Decimal\)" client_app.py` нашёл только `lib.__version__`.
- Контрактные тесты со стороны потребителя: `test_client_contract.py`, 23 теста, привязаны к строкам client_app.py. Запуск: `CLIENT_LIB_DIR=<v1|v2|proposal> python -m pytest test_client_contract.py -q`.

| версия | результат |
|---|---|
| v1 (контроль) | 21 passed, 2 skipped (тесты на новинки 2.0) |
| v2 | **7 failed**, 16 passed |
| proposal | 23 passed |

Шесть из семи падений на v2 соответствуют строкам 1-6 таблицы. Седьмое — сквозной тест вывода client_app. Зелёный v1 показывает, что падения на v2 вызваны библиотекой, а не тестами. 16 прошедших тестов на v2 фиксируют раздел «только выглядит опасным».

Тесты привязаны к поведению v1 и к тому, что использует client_app. Зависимости других клиентов они не покрывают.

## Что предлагаю

**Вариант A: сделать заявление правдой.** Подготовлен `proposal/client_lib.py`, 27 изменённых строк относительно v2, в v2/ ничего не менялось. На нём тесты 23/23, а client_app печатает вывод v1.
- Вернуть порядок `shipping_cost(weight_kg, distance_km)`.
- Вернуть `tax_rate=0.0`.
- Вернуть `.lower()` в `normalize_priority`.
- Вернуть `NotFoundError` на `KeyError`. Он и так подкласс `LookupError`, поэтому ловятся оба.
- В `format_price` оставить `currency` и принять `currency_code` как синоним.
- `parse_record` возвращает и `name`, и `title`. Оговорка: у клиентов, которые сравнивают словарь целиком или сериализуют его, появится лишний ключ. Тогда оставьте только `name`.

Останутся только добавления, значит по SemVer это 1.5.0, а не 2.0.0. Правило взято из памяти, semver.org не открывался.

**Вариант B: оставить 2.0.0 с поломками, но честно.**
- Убрать «fully backward compatible» и добавить раздел Breaking changes с шестью пунктами и примерами «было/стало».
- Сделать две молчаливые поломки громкими: `tax_rate` обязательным, аргументы `shipping_cost` только именованными. Тогда старый вызов даст TypeError, а не неверную сумму.
- Обновить client_app.py:
  - `currency_code`;
  - `r['title']`;
  - `except LookupError`;
  - `.lower()` на входе;
  - именованные аргументы в `shipping_cost`;
  - явный `tax_rate`.

В обоих вариантах стоит подключить `test_client_contract.py` к CI библиотеки. Также стоит сделать так, чтобы client_app завершался с ненулевым кодом при любом упавшем шаге.

## Файлы

В папке запуска:
- `test_client_contract.py` — контрактные тесты.
- `proposal/client_lib.py` — вариант A, не применён.
- Пустую папку `.benchmarks/`, которую создал pytest, не удалил: `rm -rf` блокируется хуком.

Папка запуска: `<HOME>/AppData/Local/Temp/claude/D--Claude-cod-top-2026/29a715b1-3478-43c8-b908-635a18c4834e/scratchpad/practical/runs/x3edb`

╔═ ⚡ УРОК ══════════════════════════╗
  Закон Хайрама: у API с достаточным числом пользователей кто-нибудь зависит от любого наблюдаемого поведения, а не только от документированного. Поэтому контракт надо снимать с кода, а не с CHANGELOG, как сделано в тестах выше.
╚════════════════════════════════════╝