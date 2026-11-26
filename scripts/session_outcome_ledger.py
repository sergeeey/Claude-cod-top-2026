#!/usr/bin/env python3
"""Offline session -> PR outcome ledger (read-only over transcripts and GitHub).

WHY: the repository can say which skills, agents and tools a session used, and GitHub can say
whether the PRs it opened were merged, but nothing links the two. Without that link no claim
about resource choice and result can be checked. This script joins them offline. It adds no hook
and no telemetry.

What is stored per transcript file: counts and names only (session id, start/end time, git branch,
project folder name, number of user prompts and API requests, token sums, Skill and Agent names,
MCP server names, routing-floor and dispatcher verdict labels, PR numbers the session created).
Never stored: prompt text, tool arguments, file contents.

What is stored per PR (from `gh`): state, merge and creation dates, commit count, review count,
changed lines. Titles are not stored.

Commands:
  update  scan recent transcripts, refresh PR outcomes, write the ledger (incremental)
  report  print the descriptive table for sessions that created PRs

Caveats the report states on every run: a session that creates a PR is not a comparable task;
correlation with size is not causation; a small class (n below --min-n) is not evidence.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

DEFAULT_PROJECTS = Path.home() / ".claude" / "projects"
DEFAULT_LEDGER = Path.home() / ".claude" / "state" / "session_outcome_ledger.json"
DEFAULT_REPO = "sergeeey/Claude-cod-top-2026"

PR_URL_RE = re.compile(r"/pull/(\d+)")
ROUTE_RE = re.compile(r"\[routing-floor\] (\w+)")
DISPATCH_RE = re.compile(r"\[dispatcher\] Project '[^']*' → (\w+)")


def parse_transcript(path: str, repo: str) -> dict:
    """Derive one row from a transcript file. Reads line by line; keeps only derived features."""
    repo_pr_re = re.compile(re.escape(repo) + r"/pull/(\d+)")
    feats = {
        "file": os.path.basename(path),
        "project_dir": os.path.basename(os.path.dirname(path)),
        "session_id": None,
        "cwd": None,
        "branch": None,
        "first_ts": None,
        "last_ts": None,
        "user_prompts": 0,
        "requests": {},
        "skill_calls": Counter(),
        "agent_types": Counter(),
        "mcp_servers": Counter(),
        "routing_verdicts": Counter(),
        "dispatcher_verdicts": Counter(),
        "create_ids": set(),
        "pr_created": set(),
    }
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            feats["session_id"] = feats["session_id"] or o.get("sessionId")
            feats["cwd"] = feats["cwd"] or o.get("cwd")
            if o.get("gitBranch"):
                feats["branch"] = o["gitBranch"]
            ts = o.get("timestamp")
            if ts:
                feats["first_ts"] = feats["first_ts"] or ts
                feats["last_ts"] = ts
            kind = o.get("type")
            msg = o.get("message") or {}
            content = msg.get("content")
            if kind == "user":
                if isinstance(content, str):
                    feats["user_prompts"] += 1
                elif isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "tool_result":
                            if blk.get("tool_use_id") in feats["create_ids"]:
                                txt = json.dumps(blk.get("content"), ensure_ascii=False)
                                feats["pr_created"].update(int(m) for m in repo_pr_re.findall(txt))
            elif kind == "assistant":
                rid = o.get("requestId") or o.get("uuid")
                usage = msg.get("usage") or {}
                if rid and usage:
                    feats["requests"][rid] = tuple(
                        int(usage.get(k, 0) or 0)
                        for k in (
                            "input_tokens",
                            "output_tokens",
                            "cache_creation_input_tokens",
                            "cache_read_input_tokens",
                        )
                    )
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "tool_use":
                            _count_tool_use(blk, feats)
            elif kind == "attachment":
                txt = json.dumps(o.get("attachment", {}), ensure_ascii=False)
                feats["routing_verdicts"].update(ROUTE_RE.findall(txt))
                feats["dispatcher_verdicts"].update(DISPATCH_RE.findall(txt))
    return feats


def _count_tool_use(blk: dict, feats: dict) -> None:
    name = blk.get("name", "")
    inp = blk.get("input") or {}
    if name == "Skill":
        feats["skill_calls"][str(inp.get("skill", "?"))] += 1
    elif name == "Agent":
        feats["agent_types"][str(inp.get("subagent_type", "general-purpose"))] += 1
    elif name.startswith("mcp__"):
        parts = name.split("__")
        feats["mcp_servers"][parts[1] if len(parts) > 1 else name] += 1
    cmd = inp.get("command") if isinstance(inp, dict) else None
    if isinstance(cmd, str) and "gh pr create" in cmd:
        feats["create_ids"].add(blk.get("id"))


def row_from_feats(feats: dict) -> dict:
    totals = [0, 0, 0, 0]
    for usage in feats["requests"].values():
        for i in range(4):
            totals[i] += usage[i]
    return {
        "file": feats["file"],
        "project_dir": feats["project_dir"],
        "session_id": feats["session_id"],
        "cwd": feats["cwd"],
        "branch": feats["branch"],
        "first_ts": feats["first_ts"],
        "last_ts": feats["last_ts"],
        "user_prompts": feats["user_prompts"],
        "requests": len(feats["requests"]),
        "tokens_input": totals[0],
        "tokens_output": totals[1],
        "tokens_cache_create": totals[2],
        "tokens_cache_read": totals[3],
        "skill_calls": dict(feats["skill_calls"]),
        "agent_types": dict(feats["agent_types"]),
        "mcp_servers": dict(feats["mcp_servers"]),
        "routing_verdicts": dict(feats["routing_verdicts"]),
        "dispatcher_verdicts": dict(feats["dispatcher_verdicts"]),
        "pr_created": sorted(feats["pr_created"]),
    }


def _gh_env() -> dict:
    """Environment for `gh`: GH_TOKEN is dropped so the CLI's own login is used.

    WHY: on the machine where this was built, a stale GH_TOKEN in the Python environment
    returned HTTP 401 while the same `gh` call from the shell, without that variable,
    succeeded. Nothing stored is changed; only this process's view is.
    """
    env = dict(os.environ)
    env.pop("GH_TOKEN", None)
    return env


def fetch_pr_states(repo: str) -> dict:
    """PR number -> {state, createdAt, mergedAt}. One `gh` call; no titles kept."""
    proc = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,state,createdAt,mergedAt",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=_gh_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError("gh pr list failed: " + proc.stderr[:200])
    return {
        int(p["number"]): {
            "state": p["state"],
            "createdAt": p["createdAt"],
            "mergedAt": p.get("mergedAt"),
        }
        for p in json.loads(proc.stdout)
    }


def fetch_pr_detail(repo: str, number: int) -> dict:
    """Commit count, review count and changed lines for one PR.

    A slow or failed lookup returns {} so the PR is retried on the next run instead of
    aborting the whole update.
    """
    try:
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "commits,reviews,additions,deletions",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env=_gh_env(),
        )
    except subprocess.TimeoutExpired:
        return {}
    if proc.returncode != 0:
        return {}
    d = json.loads(proc.stdout)
    return {
        "commits": len(d.get("commits") or []),
        "reviews": len(d.get("reviews") or []),
        "changed_lines": int(d.get("additions") or 0) + int(d.get("deletions") or 0),
    }


def load_ledger(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"sessions": {}, "prs": {}, "generated": None}


def save_ledger(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def update(
    projects: Path,
    ledger_path: Path,
    repo: str,
    days: int,
    pr_states: dict | None = None,
    pr_detail=fetch_pr_detail,
) -> dict:
    """Incremental update. Re-parses only files newer than the stored row. Returns counts."""
    ledger = load_ledger(ledger_path)
    cutoff = time.time() - days * 86400
    scanned = parsed = 0
    for path in glob.glob(str(projects / "**" / "*.jsonl"), recursive=True):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime < cutoff:
            continue
        scanned += 1
        key = os.path.relpath(path, projects)
        stored = ledger["sessions"].get(key)
        if stored and stored.get("mtime") == round(mtime, 3):
            continue
        try:
            row = row_from_feats(parse_transcript(path, repo))
        except OSError:
            continue
        row["mtime"] = round(mtime, 3)
        ledger["sessions"][key] = row
        parsed += 1

    needed = sorted({n for row in ledger["sessions"].values() for n in row["pr_created"]})
    if needed:
        states = pr_states if pr_states is not None else fetch_pr_states(repo)
        done = 0
        for n in needed:
            entry = ledger["prs"].get(str(n), {})
            entry.update(states.get(n, {"state": "UNKNOWN"}))
            # detail is cached; refetch only while the PR is open (commits may still change)
            if "commits" not in entry or entry.get("state") == "OPEN":
                detail = pr_detail(repo, n)
                done += 1
                if done % 25 == 0:
                    save_ledger(ledger_path, ledger)
                if detail:
                    entry.update(detail)
            ledger["prs"][str(n)] = entry
    ledger["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_ledger(ledger_path, ledger)
    return {
        "scanned": scanned,
        "parsed": parsed,
        "sessions": len(ledger["sessions"]),
        "prs": len(ledger["prs"]),
    }


def _class_of(row: dict) -> str:
    routes = row.get("routing_verdicts") or {}
    if not routes:
        return "no-routing-verdict"
    return max(routes.items(), key=lambda kv: kv[1])[0]


def report(ledger_path: Path, min_n: int) -> str:
    ledger = load_ledger(ledger_path)
    rows = [r for r in ledger["sessions"].values() if r.get("pr_created")]
    prs = ledger.get("prs", {})
    lines = []
    lines.append("# Session -> PR outcome ledger")
    lines.append("")
    lines.append(
        f"Generated: {ledger.get('generated')}. Sessions in ledger: {len(ledger['sessions'])}. "
        f"Sessions that created PRs: {len(rows)}."
    )
    lines.append("Descriptive only. Size drives counts; correlation is not causation.")
    lines.append("")
    lines.append(
        "| Session | First | Prompts | Tokens (M) | Skill calls | Agent calls | MCP calls "
        "| Class | PRs | merged | closed | open | commits | changed lines |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    by_class: dict[str, dict] = {}
    for r in sorted(rows, key=lambda x: x.get("first_ts") or ""):
        states = Counter(prs.get(str(n), {}).get("state", "UNKNOWN") for n in r["pr_created"])
        commits = sum(prs.get(str(n), {}).get("commits", 0) for n in r["pr_created"])
        changed = sum(prs.get(str(n), {}).get("changed_lines", 0) for n in r["pr_created"])
        tokens = (r["tokens_input"] + r["tokens_output"] + r["tokens_cache_create"]) / 1e6
        cls = _class_of(r)
        lines.append(
            f"| {(r.get('session_id') or r['file'])[:8]} | {(r.get('first_ts') or '')[:10]} | "
            f"{r['user_prompts']} | {tokens:.2f} | {sum(r['skill_calls'].values())} | "
            f"{sum(r['agent_types'].values())} | {sum(r['mcp_servers'].values())} | {cls} | "
            f"{len(r['pr_created'])} | {states.get('MERGED', 0)} | {states.get('CLOSED', 0)} | "
            f"{states.get('OPEN', 0)} | {commits} | {changed} |"
        )
        agg = by_class.setdefault(
            cls, {"n": 0, "merged": 0, "closed": 0, "open": 0, "commits": 0, "changed": 0}
        )
        agg["n"] += 1
        agg["merged"] += states.get("MERGED", 0)
        agg["closed"] += states.get("CLOSED", 0)
        agg["open"] += states.get("OPEN", 0)
        agg["commits"] += commits
        agg["changed"] += changed
    lines.append("")
    lines.append("## By routing class (sessions with a PR)")
    lines.append("")
    lines.append(
        f"| Class | Sessions | Below n={min_n}? | PRs merged | PRs closed | PRs open "
        "| Commits per 100 changed lines |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for cls, a in sorted(by_class.items()):
        ratio = (100 * a["commits"] / a["changed"]) if a["changed"] else float("nan")
        flag = "yes: no conclusion" if a["n"] < min_n else "no"
        lines.append(
            f"| {cls} | {a['n']} | {flag} | {a['merged']} | {a['closed']} "
            f"| {a['open']} | {ratio:.2f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_up = sub.add_parser("update")
    p_up.add_argument("--projects", type=Path, default=DEFAULT_PROJECTS)
    p_up.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    p_up.add_argument("--repo", default=DEFAULT_REPO)
    p_up.add_argument("--days", type=int, default=30)
    p_rep = sub.add_parser("report")
    p_rep.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    p_rep.add_argument("--min-n", type=int, default=30)
    args = parser.parse_args(argv)
    if args.cmd == "update":
        counts = update(args.projects, args.ledger, args.repo, args.days)
        print(json.dumps(counts))
        return 0
    sys.stdout.write(report(args.ledger, args.min_n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
