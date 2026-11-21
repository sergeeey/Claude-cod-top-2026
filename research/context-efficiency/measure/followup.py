"""Read-only follow-up probe. Prints aggregates and hashes only, no message text.

1. Per-session totals INCLUDING subagent transcripts.
2. Scheduled-run grouping: sessions whose first assistant turn starts at
   fixed wall-clock minutes (00:47/00:57/01:15/02:03 local-ish UTC); group by
   a short hash of the first user prompt; report startup tokens before/after 2026-11-17.
3. Reconcile last cost-state per-model token sums against per-turn sums.
"""

import glob
import hashlib
import json
import os
import statistics
import sys
from collections import defaultdict

ROOT = r"C:\Users\serge\.claude\projects\D--Claude-cod-top-2026"
SCHED_MIN = {"00:47", "00:57", "01:15", "02:03"}


def scan(path):
    t = {
        "turns": 0,
        "input": 0,
        "output": 0,
        "cc": 0,
        "cr": 0,
        "startup": None,
        "first_ts": None,
        "prompt_hash": None,
        "cost_last": None,
        "cost_models": None,
    }
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            typ = rec.get("type")
            if typ == "user" and t["prompt_hash"] is None:
                msg = rec.get("message") or {}
                content = msg.get("content")
                text = (
                    content
                    if isinstance(content, str)
                    else json.dumps(content)[:4000]
                    if content
                    else ""
                )
                if text:
                    t["prompt_hash"] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[
                        :10
                    ]
            if typ == "cost-state":
                t["cost_last"] = rec.get("totalCostUSD")
                t["cost_models"] = rec.get("modelUsage")
            msg = rec.get("message")
            if typ != "assistant" or not isinstance(msg, dict):
                continue
            u = msg.get("usage")
            if not isinstance(u, dict) or msg.get("model") == "<synthetic>":
                continue
            inp = int(u.get("input_tokens") or 0)
            cc = int(u.get("cache_creation_input_tokens") or 0)
            cr = int(u.get("cache_read_input_tokens") or 0)
            t["turns"] += 1
            t["input"] += inp
            t["output"] += int(u.get("output_tokens") or 0)
            t["cc"] += cc
            t["cr"] += cr
            if t["startup"] is None:
                t["startup"] = inp + cc + cr
                t["first_ts"] = rec.get("timestamp")
    return t


def main():
    top = sorted(glob.glob(os.path.join(ROOT, "*.jsonl")), key=os.path.getmtime)
    print("== 1. totals including subagents ==")
    grand = defaultdict(int)
    for p in top:
        sid = os.path.splitext(os.path.basename(p))[0]
        main_t = scan(p)
        subs = glob.glob(os.path.join(ROOT, sid, "subagents", "*.jsonl"))
        sub_tot = defaultdict(int)
        sub_turns = 0
        for s in subs:
            st = scan(s)
            sub_turns += st["turns"]
            for k in ("input", "output", "cc", "cr"):
                sub_tot[k] += st[k]
        if main_t["turns"] == 0 and sub_turns == 0:
            continue
        for k in ("input", "output", "cc", "cr"):
            grand[k] += main_t[k] + sub_tot[k]
        grand["turns"] += main_t["turns"] + sub_turns
        print(
            f"{sid[:8]} main_turns={main_t['turns']:>6} sub_files={len(subs):>4} "
            f"sub_turns={sub_turns:>6} cache_read_all={main_t['cr'] + sub_tot['cr']:>14}"
        )
    print(
        f"ALL top-level+subagent: turns={grand['turns']} input={grand['input']} "
        f"output={grand['output']} cache_create={grand['cc']} cache_read={grand['cr']}"
    )

    print("== 2. scheduled runs grouped by first-prompt hash ==")
    groups = defaultdict(list)
    for p in top:
        t = scan(p)
        if t["turns"] == 0 or not t["first_ts"]:
            continue
        hhmm = t["first_ts"][11:16]
        if hhmm not in SCHED_MIN:
            continue
        groups[t["prompt_hash"]].append(t)
    for h, rows in groups.items():
        before = [r["startup"] for r in rows if r["first_ts"] < "2026-11-17"]
        after = [r["startup"] for r in rows if r["first_ts"] >= "2026-11-17"]
        print(
            f"prompt={h} n={len(rows)} before_med={statistics.median(before) if before else '-'} "
            f"after_med={statistics.median(after) if after else '-'} "
            f"turns_med={statistics.median([r['turns'] for r in rows])}"
        )
    print(f"scheduled sessions total: {sum(len(v) for v in groups.values())}")

    print("== 3. cost-state vs per-turn sums (sessions with cost-state) ==")
    for p in top[-12:]:
        t = scan(p)
        if not t["cost_models"]:
            continue
        cm_in = sum(int(v.get("inputTokens") or 0) for v in t["cost_models"].values())
        cm_cr = sum(int(v.get("cacheReadInputTokens") or 0) for v in t["cost_models"].values())
        cm_usd = t["cost_last"]
        print(
            f"{os.path.basename(p)[:8]} turn_input={t['input']} cost_input={cm_in} "
            f"turn_cr={t['cr']} cost_cr={cm_cr} cost_usd_last={cm_usd}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
