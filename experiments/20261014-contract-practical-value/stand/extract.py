"""Extract reports and cost metrics of finished executor runs from the subagent transcripts.

Usage:
    EXPERIMENT_SUBAGENTS=<session>/subagents python extract.py            # reports + metrics
    EXPERIMENT_SUBAGENTS=<session>/subagents python extract.py --tokens-only  # metrics only

Token counts are taken once per assistant message id. A transcript writes one record per content
block, and every record of the same message repeats the same usage, so summing per record counts
each message two or more times (checked on one run: 110 summed vs 56 per message).
Prints counts only.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
TOKENS_ONLY = "--tokens-only" in sys.argv
SUB_ENV = os.environ.get("EXPERIMENT_SUBAGENTS")
if not SUB_ENV:
    sys.exit("set EXPERIMENT_SUBAGENTS to the session's subagents folder")
SUB = Path(SUB_ENV)

plan = {p["run"]: p for p in json.load(open(HERE / "plan_SECRET.json", encoding="utf-8"))}
# runs that ended on an API session-limit error (their "report" is the error text); see claim.md
EXCLUDED = set(json.load(open(HERE / "excluded_runs.json", encoding="utf-8")))
(HERE / "reports").mkdir(exist_ok=True)
metrics_path = HERE / "metrics_runs.json"
metrics = json.load(open(metrics_path, encoding="utf-8")) if metrics_path.exists() else {}


def ts(s: str) -> float:
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def once_per_message(records: list[dict]) -> list[dict]:
    """First record of each assistant message id; repeated records carry the same usage."""
    seen: dict[str, dict] = {}
    for r in records:
        mid = r["message"].get("id") or f"anon-{len(seen)}"
        seen.setdefault(mid, r)
    return list(seen.values())


done = 0
for meta in sorted(SUB.glob("agent-*.meta.json")):
    m = json.load(open(meta, encoding="utf-8"))
    desc = m.get("description", "")
    if not desc.startswith("Execute run "):
        continue
    rid = desc.split()[-1]
    if rid not in plan or rid in EXCLUDED:
        continue
    jl = meta.with_suffix("").with_suffix(".jsonl")
    if not jl.exists():
        continue
    rows = [
        json.loads(line) for line in open(jl, encoding="utf-8", errors="replace") if line.strip()
    ]
    asst = [r for r in rows if r.get("type") == "assistant"]
    # a finished run ends with a text-only assistant record; some finished transcripts record
    # stop_reason as None on that record (seen for xd239), so that case counts as finished too
    last_stop = asst[-1]["message"].get("stop_reason") if asst else None
    last_blocks = asst[-1]["message"]["content"] if asst else []
    text_only = any(b.get("type") == "text" for b in last_blocks) and not any(
        b.get("type") == "tool_use" for b in last_blocks
    )
    finished = last_stop in ("end_turn", "stop_sequence", "max_tokens") or (
        last_stop is None and text_only
    )
    if not finished:
        continue  # still running

    messages = once_per_message(asst)
    usage = [r["message"].get("usage") or {} for r in messages]
    tokens = {
        "tokens_in": sum(u.get("input_tokens", 0) for u in usage),
        "tokens_cache_create": sum(u.get("cache_creation_input_tokens", 0) for u in usage),
        "tokens_cache_read": sum(u.get("cache_read_input_tokens", 0) for u in usage),
        "tokens_out": sum(u.get("output_tokens", 0) for u in usage),
        "turns": len(messages),
    }

    if TOKENS_ONLY:
        if rid in metrics:
            metrics[rid].update(tokens)
            done += 1
        continue

    final = "".join(
        b.get("text", "") for b in asst[-1]["message"]["content"] if b.get("type") == "text"
    ).strip()
    rdir = HERE / "runs" / rid
    rep = rdir / "report.md"
    text = rep.read_text(encoding="utf-8", errors="replace") if rep.exists() else final
    (HERE / "reports" / f"{rid}.md").write_text(text, encoding="utf-8")
    # files the executor created or changed, copied for the grader (report and instruction excluded)
    mat = HERE / "tasks" / plan[rid]["task"] / "material"
    extra = []
    fdir = HERE / "reports" / f"{rid}_files"
    for root, dirs, files in os.walk(rdir):
        dirs[:] = [
            d
            for d in dirs
            if d not in ("__pycache__", ".pytest_cache", ".venv", "venv", "node_modules")
        ]
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(rdir)
            if str(rel) in ("report.md", "ЗАДАНИЕ.txt"):
                continue
            src = mat / rel
            if not src.exists() or src.read_bytes() != full.read_bytes():
                extra.append(str(rel).replace("\\", "/"))
                dst = fdir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(full, dst)
    tool_calls = sum(
        1 for r in messages for b in r["message"]["content"] if b.get("type") == "tool_use"
    )
    metrics[rid] = {
        "task": plan[rid]["task"],
        "arm": plan[rid]["arm"],
        "rep": plan[rid]["rep"],
        "wrote_report_file": rep.exists(),
        "report_chars": len(text),
        "extra_files": extra,
        "tool_calls": tool_calls,
        **tokens,
        "seconds": ts(rows[-1]["timestamp"]) - ts(rows[0]["timestamp"]),
    }
    done += 1

json.dump(metrics, open(metrics_path, "w", encoding="utf-8"), indent=1)
by = {}
for v in metrics.values():
    by[v["arm"]] = by.get(v["arm"], 0) + 1
print(
    "mode:",
    "tokens-only" if TOKENS_ONLY else "full",
    "| updated:",
    done,
    "| entries:",
    len(metrics),
    "by arm:",
    by,
)
