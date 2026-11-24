"""Create fresh runs for the 11 executions that ended on an API session-limit error.

Old run directories are kept on disk (nothing is deleted). Old ids go to excluded_runs.json;
new entries are appended to plan_SECRET.json with a `replaces` field. Prompt and material are
identical to the failed run, only the run directory in the path changes.
"""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

HERE = Path(__file__).parent
FAILED = "x1327 xaf11 xc7cd xaadd xd9ed x2448 x0eff xc3dc x36b8 x4640 xe0fe".split()

plan = json.load(open(HERE / "plan_SECRET.json", encoding="utf-8"))
by_id = {p["run"]: p for p in plan}
used = set(by_id)
rnd = random.Random(20261014 + 7)


def newid() -> str:
    while True:
        x = "x" + "".join(rnd.choice("0123456789abcdef") for _ in range(4))
        if x not in used:
            used.add(x)
            return x


excluded_path = HERE / "excluded_runs.json"
excluded = (
    set(json.load(open(excluded_path, encoding="utf-8"))) if excluded_path.exists() else set()
)
new_entries = []
for old in FAILED:
    p = by_id[old]
    nid = newid()
    old_prompt = (HERE / "prompts" / f"{old}.txt").read_text(encoding="utf-8")
    new_prompt = old_prompt.replace(f"/runs/{old}", f"/runs/{nid}")
    assert new_prompt != old_prompt, old
    shutil.copytree(HERE / "tasks" / p["task"] / "material", HERE / "runs" / nid)
    (HERE / "prompts" / f"{nid}.txt").write_text(new_prompt, encoding="utf-8")
    (HERE / "runs" / nid / "ЗАДАНИЕ.txt").write_text(new_prompt, encoding="utf-8")
    new_entries.append(
        {
            "run": nid,
            "task": p["task"],
            "arm": p["arm"],
            "rep": p["rep"],
            "chars": len(new_prompt),
            "replaces": old,
        }
    )
    excluded.add(old)

plan.extend(new_entries)
json.dump(plan, open(HERE / "plan_SECRET.json", "w", encoding="utf-8"), indent=1)
json.dump(sorted(excluded), open(excluded_path, "w", encoding="utf-8"), indent=1)
for e in new_entries:
    print(e["replaces"], "->", e["run"], e["task"], e["arm"], e["rep"])
print("plan size", len(plan), "| excluded", len(excluded))
