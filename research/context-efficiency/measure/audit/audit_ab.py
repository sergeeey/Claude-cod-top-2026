"""Independent audit of the approved A/B run. Free, local, read-only on sources.

1. Loads results/ab_runs.jsonl (raw rows, not modified). Checks keys, duplicates, gaps.
2. For each run, finds its Claude Code session folder (cwd-derived name) and sums
   per-turn usage from the session jsonl. Compares with the CLI row.
3. Recomputes cost per turn from OFFICIAL Haiku 5.5 prices (platform.claude.com pricing,
   fetched 2026-11-21): prompt <=100k: in 0.10, out 0.50, cw5m 0.125, cw1h 0.20, cr 0.01 USD/MTok;
   prompt >100k: in 0.50, out 2.50, cw5m 0.625, cw1h 1.00, cr 0.05 USD/MTok.
   prompt = input + cache_creation + cache_read of that request (per docs).
4. Writes results/audit_per_run.csv and prints aggregates. No API calls.
"""

import csv
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
PROJ = r"C:\Users\serge\.claude\projects"
RUNS_ROOT_TAG = "scratchpad-ab-runs"

LOW = {"in": 0.10, "out": 0.50, "cw5m": 0.125, "cw1h": 0.20, "cr": 0.01}
HIGH = {"in": 0.50, "out": 2.50, "cw5m": 0.625, "cw1h": 1.00, "cr": 0.05}


def load_rows():
    rows = []
    with open(os.path.join(RES, "ab_runs.jsonl"), encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            r = json.loads(line)
            r["_line"] = i
            rows.append(r)
    return rows


def session_folder(arm, task, rep):
    t = task.replace("_", "-")
    pattern = f"*{RUNS_ROOT_TAG}-{arm}-{t}-r{rep}"
    hits = glob.glob(os.path.join(PROJ, pattern))
    return hits


def turns_of(path):
    """One entry per API request (message.id), not per jsonl record.

    WHY: Claude Code writes one jsonl record per content block (thinking, text,
    tool_use), and every record repeats the same request's `usage`. Summing records
    double-counts. Dedup by message.id; flag any id whose usage differs between records.
    """
    by_id = {}
    conflicts = 0
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
            if not isinstance(u, dict) or msg.get("model") == "<synthetic>":
                continue
            mid = msg.get("id") or rec.get("uuid")
            cc_obj = u.get("cache_creation") or {}
            cw5 = int(cc_obj.get("ephemeral_5m_input_tokens") or 0)
            cw1 = int(cc_obj.get("ephemeral_1h_input_tokens") or 0)
            cc = int(u.get("cache_creation_input_tokens") or 0)
            if cw5 + cw1 == 0:
                cw5 = cc  # no split reported: attribute to 5m (flagged)
            entry = {
                "model": msg.get("model"),
                "in": int(u.get("input_tokens") or 0),
                "out": int(u.get("output_tokens") or 0),
                "cc": cc,
                "cw5": cw5,
                "cw1": cw1,
                "cr": int(u.get("cache_read_input_tokens") or 0),
                "split_reported": (cw5 + cw1) > 0 and bool(cc_obj),
            }
            if mid in by_id:
                if by_id[mid] != entry:
                    conflicts += 1
                continue
            by_id[mid] = entry
    out = list(by_id.values())
    turns_of.last_conflicts = conflicts
    return out


def price_turn(t):
    prompt = t["in"] + t["cc"] + t["cr"]
    p = HIGH if prompt > 100_000 else LOW
    usd = (
        t["in"] * p["in"]
        + t["out"] * p["out"]
        + t["cw5"] * p["cw5m"]
        + t["cw1"] * p["cw1h"]
        + t["cr"] * p["cr"]
    ) / 1e6
    return usd, prompt > 100_000


def main():
    rows = load_rows()
    full = [r for r in rows if not r.get("dry")]
    keys = [(r["arm"], r["task"], r["rep"]) for r in full]
    print(f"rows total={len(rows)} full={len(full)} dry={len(rows) - len(full)}")
    print(f"unique full keys={len(set(keys))} duplicates={len(keys) - len(set(keys))}")
    expected = {
        (a, t, rep)
        for a in "AB"
        for t in ["t1_paginate", "t2_duration", "t3_money", "t4_intervals", "t5_config", "t6_csv"]
        for rep in (1, 2, 3)
    }
    print(f"missing vs expected 36={sorted(expected - set(keys))}")
    print(f"unexpected={sorted(set(keys) - expected)}")
    n_rc = sum(1 for r in full if r["rc"] != 0)
    n_err = sum(1 for r in full if r["is_error"])
    n_parse = sum(1 for r in full if r["parse_error"])
    n_hidden = sum(1 for r in full if not r["hidden_pass"])
    print(f"rc!=0={n_rc} is_error={n_err} parse_error={n_parse} hidden_fail={n_hidden}")

    out_rows = []
    problems = []
    for r in full:
        folders = session_folder(r["arm"], r["task"], r["rep"])
        if len(folders) != 1:
            problems.append((r["arm"], r["task"], r["rep"], f"folders={len(folders)}"))
            continue
        jsonls = glob.glob(os.path.join(folders[0], "*.jsonl"))
        if len(jsonls) != 1:
            problems.append((r["arm"], r["task"], r["rep"], f"session_files={len(jsonls)}"))
        cli_tot = (
            r["input_tokens"],
            r["output_tokens"],
            r["cache_creation_input_tokens"],
            r["cache_read_input_tokens"],
        )
        # WHY: an interrupted run can leave a second session file in the same folder.
        # Pick the file whose per-request totals reproduce the CLI row; record the choice.
        chosen, matched = None, []
        for jp in jsonls:
            cand = turns_of(jp)
            tot = (
                sum(t["in"] for t in cand),
                sum(t["out"] for t in cand),
                sum(t["cc"] for t in cand),
                sum(t["cr"] for t in cand),
            )
            if tot == cli_tot:
                matched.append(os.path.basename(jp))
                if chosen is None:
                    chosen = cand
        if chosen is None:
            chosen = turns_of(jsonls[0]) if jsonls else []
        turns = chosen
        session_pick = ";".join(matched) if matched else "NO_MATCH"
        sums = defaultdict(int)
        usd_sum = 0.0
        high_turns = 0
        models = set()
        for t in turns:
            sums["in"] += t["in"]
            sums["out"] += t["out"]
            sums["cc"] += t["cc"]
            sums["cr"] += t["cr"]
            usd, high = price_turn(t)
            usd_sum += usd
            high_turns += int(high)
            models.add(t["model"])
        cli = {
            "in": r["input_tokens"],
            "out": r["output_tokens"],
            "cc": r["cache_creation_input_tokens"],
            "cr": r["cache_read_input_tokens"],
        }
        diffs = {k: (cli[k] or 0) - sums[k] for k in cli}
        out_rows.append(
            {
                "arm": r["arm"],
                "task": r["task"],
                "rep": r["rep"],
                "turns_log": len(turns),
                "id_conflicts": getattr(turns_of, "last_conflicts", 0) if turns else 0,
                "session_pick": session_pick,
                "turns_cli": r["num_turns"],
                "cli_in": cli["in"],
                "cli_out": cli["out"],
                "cli_cc": cli["cc"],
                "cli_cr": cli["cr"],
                "log_in": sums["in"],
                "log_out": sums["out"],
                "log_cc": sums["cc"],
                "log_cr": sums["cr"],
                "diff_in": diffs["in"],
                "diff_out": diffs["out"],
                "diff_cc": diffs["cc"],
                "diff_cr": diffs["cr"],
                "cli_cost": round(r["total_cost_usd"], 6),
                "recalc_cost": round(usd_sum, 6),
                "high_tier_turns": high_turns,
                "models": ";".join(sorted(m for m in models if m)),
                "hidden_pass": r["hidden_pass"],
                "wall_s": r["wall_s"],
            }
        )
    print(f"problems={problems}")

    os.makedirs(RES, exist_ok=True)
    out_csv = os.path.join(RES, "audit_per_run.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_csv} rows={len(out_rows)}")

    # token-match summary
    mism = [
        x for x in out_rows if any(x[k] != 0 for k in ("diff_in", "diff_out", "diff_cc", "diff_cr"))
    ]
    print(f"runs where CLI usage != sum of session turns: {len(mism)} of {len(out_rows)}")
    cost_gap = [x["cli_cost"] - x["recalc_cost"] for x in out_rows]
    if cost_gap:
        print(
            f"cli_cost - recalc_cost: min={min(cost_gap):.6f} max={max(cost_gap):.6f} "
            f"mean={sum(cost_gap) / len(cost_gap):.6f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
