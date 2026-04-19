---
name: neo4j-schema
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-18]
  Проектирование Neo4j граф-схем: temporal properties, confidence tracking,
  безопасные миграции с rollback, индексы, Cypher паттерны.
  Особенно полезно для knowledge graphs, temporal event graphs, social graphs.
  Триггеры: "neo4j", "cypher", "граф схема", "graph schema", "node label",
  "relationship type", "temporal graph", "граф миграция", "neo4j индекс",
  "knowledge graph", "graph database".
  НЕ использовать для: SQL, MongoDB, Redis — только Neo4j.
allowed-tools: Read, Bash(cypher-shell:*), Bash(python:*)
---

# Neo4j Schema Design

## Принципы граф-моделирования

### Правило 1: Существительное → Node, Глагол → Relationship
```
Country -[HAS_EVENT]-> Event       ✅ правильно
Country -[EVENT]-> Event           ❌ неправильно (существительное как связь)
```

### Правило 2: Свойства на связях = контекст отношения
```cypher
(c:Country)-[r:EXPORTS {
  product: "oil",
  volume_mbd: 3.2,
  year: 2024
}]->(c2:Country)
```

### Правило 3: Temporal properties — всегда явно
```cypher
CREATE (e:Event {
  event_id: "evt_001",
  type: "sanctions",
  valid_from: datetime("2024-03-15"),
  valid_to: null,           // null = до сих пор активно
  confidence: 0.92,         // [0..1] — уверенность в данных
  source: "ACLED",
  created_at: datetime()
})
```

---

## Шаблоны для GeoMiro-типа проектов

### Temporal Event Graph
```cypher
// Node labels
(:Country {name, iso_code, region, population})
(:Event {event_id, type, severity, valid_from, valid_to, confidence, source})
(:Actor {name, type, country_iso})
(:Sector {name, gdp_weight})

// Relationships
(:Country)-[:HAS_EVENT {date, impact_score}]->(:Event)
(:Actor)-[:INVOLVED_IN {role, confidence}]->(:Event)
(:Event)-[:AFFECTS {channel, lag_days}]->(:Sector)
(:Country)-[:BORDERS {shared_km}]->(:Country)
```

### Запрос активных событий на дату
```cypher
MATCH (c:Country {iso_code: $iso})-[:HAS_EVENT]->(e:Event)
WHERE e.valid_from <= $date
  AND (e.valid_to IS NULL OR e.valid_to >= $date)
  AND e.confidence >= 0.7
RETURN e
ORDER BY e.valid_from DESC
LIMIT 50
```

---

## Индексы — создавай сразу

```cypher
// Обязательные для production
CREATE INDEX country_iso IF NOT EXISTS FOR (c:Country) ON (c.iso_code);
CREATE INDEX event_date IF NOT EXISTS FOR (e:Event) ON (e.valid_from);
CREATE INDEX event_type IF NOT EXISTS FOR (e:Event) ON (e.type);

// Composite index для temporal queries
CREATE INDEX event_temporal IF NOT EXISTS
FOR (e:Event) ON (e.valid_from, e.valid_to);

// Full-text для поиска
CREATE FULLTEXT INDEX event_search IF NOT EXISTS
FOR (e:Event) ON EACH [e.description, e.source];
```

---

## Безопасные миграции (с rollback)

### Паттерн: добавить свойство
```cypher
// Шаг 1: добавить с default значением (не сломает существующие запросы)
MATCH (e:Event) WHERE e.severity IS NULL
SET e.severity = 'medium'
RETURN count(e) AS updated;

// Шаг 2: проверить
MATCH (e:Event) WHERE e.severity IS NULL RETURN count(e);
// Ожидаем: 0

// Rollback если нужно:
MATCH (e:Event) WHERE e.severity = 'medium' AND e.created_at > datetime('2026-04-18')
REMOVE e.severity;
```

### Паттерн: переименовать relationship
```cypher
// Нельзя переименовать напрямую — создаём новый, удаляем старый
MATCH (a)-[r:OLD_NAME]->(b)
CREATE (a)-[r2:NEW_NAME]->(b)
SET r2 = properties(r)
WITH r DELETE r;
```

### Kill criterion для миграции
- Если после миграции count(nodes) уменьшился > 0.1% → **немедленный rollback**
- Если время Cypher запросов выросло >2x → проверить индексы

---

## Confidence Tracking паттерн

```python
# При добавлении данных из нескольких источников
def merge_confidence(sources: list[dict]) -> float:
    """
    Несколько источников подтверждают одно событие →
    confidence растёт, но не до 1.0 (никогда не бывает 100% уверенности).
    """
    if not sources:
        return 0.0
    base = max(s["confidence"] for s in sources)
    bonus = 0.05 * (len(sources) - 1)  # каждый доп. источник +5%
    return min(base + bonus, 0.95)     # cap at 95%
```

---

## Gotchas

- Neo4j не поддерживает composite unique constraints на нескольких labels
- `datetime()` без аргументов = UTC now, используй везде
- `MERGE` опасен без `ON CREATE SET` + `ON MATCH SET` — создаст дубли
- Удаление node с relationships → сначала удали relationships: `DETACH DELETE`
- Property `null` vs отсутствие property — в Cypher это разные вещи
