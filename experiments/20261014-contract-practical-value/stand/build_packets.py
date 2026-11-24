"""Build blind grading packets: one per task, six reports shuffled under neutral labels.

The label-to-run key is written to keys_SECRET/ and is never shown to graders.
A slot is (task, arm, rep); it is filled by the single valid run for that slot
(an original, or its rerun when the original ended on an API error).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).parent
SLOTS = (("C", 1), ("C", 2), ("F", 1), ("F", 2), ("H", 1), ("W", 1))

plan = json.load(open(HERE / "plan_SECRET.json", encoding="utf-8"))
metrics = json.load(open(HERE / "metrics_runs.json", encoding="utf-8"))
excluded = set(json.load(open(HERE / "excluded_runs.json", encoding="utf-8")))

slot_run: dict[tuple[str, str, int], str] = {}
for p in plan:
    if p["run"] in excluded or p["run"] not in metrics:
        continue
    key = (p["task"], p["arm"], p["rep"])
    assert key not in slot_run, f"two valid runs for slot {key}"
    slot_run[key] = p["run"]

(HERE / "grading").mkdir(exist_ok=True)
(HERE / "keys_SECRET").mkdir(exist_ok=True)

tasks = sorted({p["task"] for p in plan})
for t in tasks:
    slots = [(t, arm, rep) for arm, rep in SLOTS]
    missing = [s for s in slots if s not in slot_run]
    assert not missing, f"missing slots {missing}"

    rnd = random.Random(f"blind-grade-{t}")
    order = slots[:]
    rnd.shuffle(order)
    labels = [f"R{i + 1}" for i in range(len(order))]

    statement = (HERE / "statements" / f"{t}.txt").read_text(encoding="utf-8").strip()
    parts = [
        f"# Пакет оценки {t}\n\n"
        "Задание, которое выполняли исполнители (без дополнительного контекста):\n\n"
        f"{statement}\n"
    ]
    key: dict[str, str] = {}
    for label, slot in zip(labels, order):
        run_id = slot_run[slot]
        key[label] = run_id
        text = (
            (HERE / "reports" / f"{run_id}.md")
            .read_text(encoding="utf-8", errors="replace")
            .strip()
        )
        parts.append(f"\n---\n\n## Отчёт {label}\n\n{text}\n")

    (HERE / "grading" / f"{t}_packet.md").write_text("".join(parts), encoding="utf-8")
    (HERE / "keys_SECRET" / f"{t}.json").write_text(
        json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(t, "packet chars:", len("".join(parts)), "reports:", len(order))

print("tasks:", len(tasks))
