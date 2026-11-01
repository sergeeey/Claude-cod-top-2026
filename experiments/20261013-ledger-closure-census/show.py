"""Print the per-PR detail of declared ledgers from data/results.json."""

import json
from pathlib import Path

r = json.loads((Path(__file__).parent / "data" / "results.json").read_text(encoding="utf-8"))
for d in r["declared_detail"]:
    print(
        d["number"],
        d["merged"],
        "BC" if d["bc"] else "--",
        "D4" if d["d4"] else "d1",
        "|",
        d["title"][:60],
        "| CA:",
        repr(d["check_after"])[:120],
        "|",
        d["due"],
        "| cand",
        [c["where"] for c in d["candidates"]],
    )
