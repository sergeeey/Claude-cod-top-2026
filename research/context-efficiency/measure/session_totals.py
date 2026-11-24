"""Read-only: per-session totals of real API usage from Claude Code session logs.

Counts only assistant records that carry a usage block. Subagent transcripts, if
present in a per-session subfolder, are counted separately and reported as files.
Prints aggregates only; no message content.
"""

import glob
import json
import os
import statistics
import sys

ROOT = r"C:\Users\serge\.claude\projects\D--Claude-cod-top-2026"


def totals(path):
    t = {
        "turns": 0,
        "input": 0,
        "output": 0,
        "cache_create": 0,
        "cache_read": 0,
        "first_startup": None,
        "first_model": None,
        "models": set(),
    }
    # WHY: one record per content block repeats the request's usage; dedupe by message.id.
    by_id = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message")
            if rec.get("type") != "assistant" or not isinstance(msg, dict):
                continue
            u = msg.get("usage")
            if not isinstance(u, dict):
                continue
            model = msg.get("model")
            if model == "<synthetic>":
                continue
            by_id[msg.get("id") or rec.get("uuid")] = (u, model)
    for u, model in by_id.values():
        cc = int(u.get("cache_creation_input_tokens") or 0)
        cr = int(u.get("cache_read_input_tokens") or 0)
        inp = int(u.get("input_tokens") or 0)
        t["turns"] += 1
        t["input"] += inp
        t["output"] += int(u.get("output_tokens") or 0)
        t["cache_create"] += cc
        t["cache_read"] += cr
        t["models"].add(model)
        if t["first_startup"] is None:
            t["first_startup"] = inp + cc + cr
            t["first_model"] = model
    return t


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "*.jsonl")), key=os.path.getmtime)
    rows = []
    for p in files:
        sid = os.path.splitext(os.path.basename(p))[0]
        sub = os.path.join(ROOT, sid, "subagents")
        n_sub = len(glob.glob(os.path.join(sub, "*.jsonl"))) if os.path.isdir(sub) else 0
        t = totals(p)
        if t["turns"] == 0:
            continue
        t["sid"] = sid[:8]
        t["subagent_files"] = n_sub
        rows.append(t)
    print(f"sessions with real usage (non-synthetic): {len(rows)}")
    print("sid      turns  startup_in  input    output   cache_create  cache_read      models")
    for r in rows:
        print(
            f"{r['sid']} {r['turns']:>6} {str(r['first_startup']):>10} "
            f"{r['input']:>8} {r['output']:>8} {r['cache_create']:>13} "
            f"{r['cache_read']:>13}  {','.join(sorted(m for m in r['models'] if m))[:60]}"
            f"  sub={r['subagent_files']}"
        )
    # Only sessions with a plausibly full startup footprint for the same model family
    turns = [r["turns"] for r in rows]
    if turns:
        print(
            f"turns per session: median={statistics.median(turns):.0f} "
            f"min={min(turns)} max={max(turns)}"
        )
    crpt = [r["cache_read"] / r["turns"] for r in rows if r["turns"] > 1]
    if crpt:
        print(f"cache_read per turn: median={statistics.median(crpt):.0f} max={max(crpt):.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
