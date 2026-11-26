#!/usr/bin/env python3
"""Offline session -> PR outcome ledger (read-only over transcripts and GitHub).

WHY: the repository can say which skills, agents and tools a session used, and GitHub can say
whether the PRs it opened were merged, but nothing links the two. Without that link no claim
about resource choice and result can be checked. This script joins them offline. It adds no hook,
no telemetry, no database and no service.

What is stored per transcript file: counts and names only (session id, first and last time,
a hash of the project folder, number of user prompts and API requests, token sums, Skill and Agent
names, MCP server names, routing-floor and dispatcher verdict labels, PR numbers the file itself
created). Never stored: prompt text, tool arguments, file contents, working directory, git branch.

What is stored per PR (from `gh`): integration state (OPEN, MERGED, CLOSED), dates, commit count,
review count, changed lines. Titles are not stored.

Integration state is NOT a measured result. "MERGED" means the owner accepted the change; it does
not show that the task's goal was met. The report says so on every run.

A ledger belongs to one repository. Its default path includes the repository name, and a ledger
written for another repository is refused rather than overwritten.

Commands:
  update  scan recent transcripts, refresh PR states, write the ledger (incremental)
  report  print the descriptive table: sessions that created PRs, grouped by session id

Caveats the report states on every run: a session that creates a PR is not a comparable task;
correlation with size is not causation; a small class (n below --min-n) is not evidence.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = 5
DEFAULT_PROJECTS = Path.home() / ".claude" / "projects"
STATE_DIR = Path.home() / ".claude" / "state"
DEFAULT_REPO = "sergeeey/Claude-cod-top-2026"
AUTH_MODES = ("auto", "cli", "env")

ROUTE_RE = re.compile(r"\[routing-floor\] (\w+)")
DISPATCH_RE = re.compile(r"\[dispatcher\] Project '[^']*' → (\w+)")

# counters for the current run, reported by `update`
_STATS: Counter[str] = Counter()

# GitHub token variables. The CLI login is used when these are dropped.
TOKEN_VARS = ("GH_TOKEN", "GITHUB_TOKEN")

# skill and agent names are stored only when they look like a plain name
NAME_RE = re.compile(r"^[\w:.\-]{1,64}$")

# GitHub owner/name, and the integration states the ledger accepts
REPO_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}")
STATES = ("OPEN", "MERGED", "CLOSED")


def check_repo(repo: str) -> str:
    """Accept only 'owner/name' with GitHub's characters.

    WHY: the repository name becomes part of a file name. Anything else (separators, '..',
    drive colons) could point the ledger outside the state folder.
    """
    if not REPO_RE.fullmatch(repo) or ".." in repo:
        raise ValueError(f"not a valid owner/name: {repo!r}")
    return repo


def default_ledger_path(repo: str) -> Path:
    """One ledger file per repository: the repository name is part of the file name."""
    name = f"session_outcome_ledger_{check_repo(repo).replace('/', '__')}.json"
    path = (STATE_DIR / name).resolve()
    if STATE_DIR.resolve() not in path.parents:
        raise ValueError(f"ledger path escapes the state folder: {path}")
    return path


def _safe_name(value: object) -> str:
    """A plain name (64 characters or fewer, no spaces or symbols), else "other"."""
    if isinstance(value, str) and NAME_RE.match(value):
        return value
    return "other"


def parse_transcript(path: str, repo: str) -> dict[str, Any]:
    """Derive the features of one transcript file. Keeps counts and names only."""
    repo_pr_re = re.compile(r"(?<![\w.-])" + re.escape(repo) + r"/pull/(\d{1,9})\b")
    feats: dict[str, Any] = {
        "file": os.path.basename(path),
        "project_dir": os.path.basename(os.path.dirname(path)),
        "session_id": None,
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
            except (ValueError, RecursionError):
                continue
            if not isinstance(o, dict):
                continue
            feats["session_id"] = feats["session_id"] or o.get("sessionId")
            ts = o.get("timestamp")
            if ts:
                feats["first_ts"] = feats["first_ts"] or ts
                feats["last_ts"] = ts
            kind = o.get("type")
            msg = o.get("message")
            msg = msg if isinstance(msg, dict) else {}
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
                usage = msg.get("usage")
                usage = usage if isinstance(usage, dict) else {}
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


def _count_tool_use(blk: dict[str, Any], feats: dict[str, Any]) -> None:
    name = blk.get("name", "")
    if not isinstance(name, str):
        name = ""
    inp = blk.get("input")
    inp = inp if isinstance(inp, dict) else {}
    if name == "Skill":
        feats["skill_calls"][_safe_name(inp.get("skill", "?"))] += 1
    elif name == "Agent":
        feats["agent_types"][_safe_name(inp.get("subagent_type", "general-purpose"))] += 1
    elif name.startswith("mcp__"):
        parts = name.split("__")
        feats["mcp_servers"][_safe_name(parts[1] if len(parts) > 1 else name)] += 1
    cmd = inp.get("command")
    if isinstance(cmd, str) and "gh pr create" in cmd:
        feats["create_ids"].add(blk.get("id"))


def row_from_feats(feats: dict[str, Any]) -> dict[str, Any]:
    totals = [0, 0, 0, 0]
    for usage in feats["requests"].values():
        for i in range(4):
            totals[i] += usage[i]
    return {
        "file": feats["file"],
        "session_id": feats["session_id"],
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


# ---- GitHub access -------------------------------------------------------------------------


def _is_auth_error(stderr: str) -> bool:
    return "401" in stderr or "Bad credentials" in stderr


def _run_gh(args: list[str], timeout: int, auth: str) -> subprocess.CompletedProcess[str]:
    """Run `gh` with a chosen credential source.

    auth=env   use the environment as it is (a GH_TOKEN there is used).
    auth=cli   drop GH_TOKEN and GITHUB_TOKEN for this process; `gh` then uses its own login.
    auth=auto  use the environment; if GitHub rejects the credentials and a token variable was
               set, retry once with the CLI's own login. The retry is counted in the run statistics.
    Stored tokens are never changed by this script.
    """
    if auth not in AUTH_MODES:
        raise ValueError(f"auth must be one of {AUTH_MODES}")

    def call(drop_token: bool) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        if drop_token:
            for var in TOKEN_VARS:
                env.pop(var, None)
        return subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=timeout, env=env
        )

    if auth == "cli":
        return call(drop_token=True)
    proc = call(drop_token=False)
    if auth == "auto" and proc.returncode != 0 and any(os.environ.get(v) for v in TOKEN_VARS):
        if _is_auth_error(proc.stderr):
            _STATS["auth_fallback"] += 1
            return call(drop_token=True)
    return proc


def fetch_pr_states(repo: str, auth: str = "auto") -> dict[int, dict[str, Any]]:
    """PR number -> integration state and dates. One `gh` call; no titles kept.

    The list is bounded (1000). A PR missing from it keeps the state it already has; it is never
    set to UNKNOWN because of the bound. See update().
    """
    proc = _run_gh(
        [
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
        timeout=120,
        auth=auth,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh pr list failed (exit {proc.returncode})")
    return {
        int(p["number"]): {
            "state": p["state"],
            "createdAt": p["createdAt"],
            "mergedAt": p.get("mergedAt"),
        }
        for p in json.loads(proc.stdout)
    }


def fetch_pr_detail(repo: str, number: int, auth: str = "auto") -> dict[str, Any]:
    """Commit count, review count, changed lines and state for one PR.

    A slow or failed lookup returns {} so the PR is retried on the next run instead of
    aborting the whole update. The state is returned too, so a PR outside the bounded list
    still gets its state.
    """
    try:
        proc = _run_gh(
            [
                "pr",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "commits,reviews,additions,deletions,state",
            ],
            timeout=60,
            auth=auth,
        )
    except subprocess.TimeoutExpired:
        _STATS["detail_timeout"] += 1
        return {}
    if proc.returncode != 0:
        _STATS["detail_error"] += 1
        return {}
    d = json.loads(proc.stdout)
    return {
        "commits": len(d.get("commits") or []),
        "reviews": len(d.get("reviews") or []),
        "changed_lines": int(d.get("additions") or 0) + int(d.get("deletions") or 0),
        "state": d.get("state"),
    }


# ---- ledger --------------------------------------------------------------------------------


def load_ledger(path: Path, repo: str) -> dict[str, Any]:
    """Load the ledger for one repository.

    An older schema is rebuilt. A ledger that belongs to another repository is refused: this
    prevents one repository's rows being mixed into another's report.
    """
    fresh: dict[str, Any] = {
        "schema": SCHEMA,
        "repo": repo,
        "sessions": {},
        "prs": {},
        "generated": None,
    }
    if not path.exists():
        return fresh
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    # the repository is checked first: a file of another repository is never rebuilt over
    if data.get("repo") != repo:
        raise ValueError(
            f"ledger {path} belongs to repo {data.get('repo')!r}, not {repo!r}; "
            "use another --ledger path"
        )
    if data.get("schema") != SCHEMA:
        return fresh
    return data


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def update(
    projects: Path,
    ledger_path: Path,
    repo: str,
    days: int,
    auth: str = "auto",
    pr_states: dict[int, dict[str, Any]] | None = None,
    pr_detail: Any = None,
) -> dict[str, Any]:
    """Incremental update. Re-parses only files whose mtime changed. Returns run statistics."""
    _STATS.clear()
    repo = check_repo(repo)
    if pr_detail is None:

        def pr_detail(r: str, n: int) -> dict[str, Any]:
            return fetch_pr_detail(r, n, auth)

    ledger = load_ledger(ledger_path, repo)
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
        key = hashlib.sha256(os.path.relpath(path, projects).encode("utf-8")).hexdigest()[:16]
        stored = ledger["sessions"].get(key)
        if stored and stored.get("mtime") == round(mtime, 3):
            continue
        try:
            row = row_from_feats(parse_transcript(path, repo))
        except (OSError, ValueError, RecursionError, AttributeError, TypeError):
            _STATS["file_error"] += 1
            continue
        row["mtime"] = round(mtime, 3)
        ledger["sessions"][key] = row
        parsed += 1

    needed = sorted({n for row in ledger["sessions"].values() for n in row["pr_created"]})
    if needed:
        states = pr_states if pr_states is not None else fetch_pr_states(repo, auth)
        done = 0
        for n in needed:
            entry = dict(ledger["prs"].get(str(n), {}))
            if n in states:
                entry.update(states[n])
            # Detail is re-read until the PR is MERGED: MERGED is the only final state. An open,
            # closed or unknown PR is read again on every run, so a reopened or merged PR is
            # followed even when it has fallen out of the bounded list.
            stale = "commits" not in entry or entry.get("detail_state") != "MERGED"
            if stale:
                detail = pr_detail(repo, n)
                done += 1
                if detail:
                    fetched_state = detail.pop("state", None)
                    if n not in states and fetched_state in STATES:
                        entry["state"] = fetched_state
                    detail["detail_state"] = entry.get("state")
                    entry.update(detail)
                if done % 25 == 0:
                    ledger["prs"][str(n)] = entry
                    save_ledger(ledger_path, ledger)
            ledger["prs"][str(n)] = entry
    ledger["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_ledger(ledger_path, ledger)
    return {
        "scanned": scanned,
        "parsed": parsed,
        "sessions": len({r["session_id"] for r in ledger["sessions"].values()}),
        "files": len(ledger["sessions"]),
        "prs": len(ledger["prs"]),
        "auth_fallback": _STATS.get("auth_fallback", 0),
        "detail_timeout": _STATS.get("detail_timeout", 0),
        "detail_error": _STATS.get("detail_error", 0),
        "file_error": _STATS.get("file_error", 0),
    }


# ---- report --------------------------------------------------------------------------------


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / (sx * sy)


def _spearman(x: list[float], y: list[float]) -> float:
    return _pearson(_rank(x), _rank(y))


def _fmt(v: float) -> str:
    return "nan" if math.isnan(v) else f"{v:.2f}"


def _session_groups(ledger: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger["sessions"].values():
        groups[row["session_id"]].append(row)
    return groups


def _routing_class(rows: list[dict[str, Any]]) -> str:
    routes: Counter[str] = Counter()
    for r in rows:
        routes.update(r.get("routing_verdicts") or {})
    if not routes:
        return "no-routing-verdict"
    return routes.most_common(1)[0][0]


def report(ledger_path: Path, repo: str, min_n: int) -> str:
    ledger = load_ledger(ledger_path, repo)
    prs = ledger.get("prs", {})
    groups = _session_groups(ledger)
    made: dict[str, tuple[list[dict[str, Any]], list[int]]] = {}
    for sid, rows in groups.items():
        pr_set = sorted({n for r in rows for n in r["pr_created"]})
        if pr_set:
            made[sid] = (rows, pr_set)

    lines = ["# Session -> PR outcome ledger", ""]
    lines.append(
        f"Repo: {repo}. Generated: {ledger.get('generated')}. Session ids: {len(groups)} "
        f"(transcript files: {len(ledger['sessions'])}). "
        f"Session ids that created PRs: {len(made)}."
    )
    lines.append(
        "Descriptive only. 'merged' is integration status, not a measured result of the task. "
        "Size drives counts; correlation is not causation."
    )
    lines.append("")
    lines.append(
        "| Session | First | Files | Prompts | Tokens (M) | Skill calls | Agent calls | MCP calls "
        "| Class | PRs | merged | closed | open | commits | changed lines |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    by_class: dict[str, dict[str, int]] = {}
    pr_points: list[tuple[str, float, float]] = []  # (session id, commits, changed lines)
    order = sorted(made.items(), key=lambda kv: min((r["first_ts"] or "") for r in kv[1][0]))
    for sid, (rows, pr_set) in order:
        states = Counter(prs.get(str(n), {}).get("state", "UNKNOWN") for n in pr_set)
        commits = sum(prs.get(str(n), {}).get("commits", 0) for n in pr_set)
        changed = sum(prs.get(str(n), {}).get("changed_lines", 0) for n in pr_set)
        tokens = (
            sum(r["tokens_input"] + r["tokens_output"] + r["tokens_cache_create"] for r in rows)
            / 1e6
        )
        prompts = sum(r["user_prompts"] for r in rows)
        skills = sum(sum(r["skill_calls"].values()) for r in rows)
        agents = sum(sum(r["agent_types"].values()) for r in rows)
        mcp = sum(sum(r["mcp_servers"].values()) for r in rows)
        first = min((r["first_ts"] or "") for r in rows)[:10]
        cls = _routing_class(rows)
        lines.append(
            f"| {sid[:8]} | {first} | {len(rows)} | {prompts} | {tokens:.2f} | {skills} "
            f"| {agents} | {mcp} | {cls} | {len(pr_set)} | {states.get('MERGED', 0)} "
            f"| {states.get('CLOSED', 0)} | {states.get('OPEN', 0)} | {commits} | {changed} |"
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
        for n in pr_set:
            p = prs.get(str(n), {})
            if "commits" in p and p.get("changed_lines", 0) > 0:
                pr_points.append((sid, float(p["commits"]), float(p["changed_lines"])))

    lines.append("")
    lines.append("## By routing class (session ids with a PR)")
    lines.append("")
    lines.append(
        f"| Class | Session ids | Below n={min_n}? | PRs merged | PRs closed | PRs open "
        "| Commits per 100 changed lines |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for cls, a in sorted(by_class.items()):
        ratio = (100 * a["commits"] / a["changed"]) if a["changed"] else float("nan")
        flag = "yes: no conclusion" if a["n"] < min_n else "no"
        lines.append(
            f"| {cls} | {a['n']} | {flag} | {a['merged']} | {a['closed']} "
            f"| {a['open']} | {_fmt(ratio)} |"
        )

    lines.append("")
    lines.append("## Size and commits: robustness to outliers (PR level)")
    lines.append("")
    if pr_points:
        xs = [p[2] for p in pr_points]
        ys = [p[1] for p in pr_points]
        biggest = Counter(p[0] for p in pr_points).most_common(1)[0][0]
        rest = [p for p in pr_points if p[0] != biggest]
        lines.append(f"PRs with commit and size data: {len(pr_points)}.")
        lines.append(f"- all: Pearson {_fmt(_pearson(xs, ys))}, Spearman {_fmt(_spearman(xs, ys))}")
        if len(rest) >= 3:
            rx = [p[2] for p in rest]
            ry = [p[1] for p in rest]
            lines.append(
                f"- without the session id with the most PRs ({biggest[:8]}, n={len(rest)}): "
                f"Pearson {_fmt(_pearson(rx, ry))}, Spearman {_fmt(_spearman(rx, ry))}"
            )
        lines.append(
            "Spearman is rank-based and less sensitive to single large PRs; "
            "both are descriptive at this n."
        )
    else:
        lines.append("No PR with both commit and size data yet.")
    lines.append("")
    lines.append(
        "Causal effect of any skill, agent or tool on the outcome is not estimated here. "
        "The sample is too small and size is confounded with everything else."
    )
    return "\n".join(lines) + "\n"


# ---- CLI -----------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_up = sub.add_parser("update")
    p_up.add_argument("--projects", type=Path, default=DEFAULT_PROJECTS)
    p_up.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help="default: a file per repository under ~/.claude/state/",
    )
    p_up.add_argument("--repo", default=DEFAULT_REPO)
    p_up.add_argument("--days", type=int, default=30)
    p_up.add_argument(
        "--gh-auth",
        choices=AUTH_MODES,
        default="auto",
        help="auto: environment token, fall back to the CLI login on 401; "
        "env: environment only; cli: CLI login only",
    )
    p_rep = sub.add_parser("report")
    p_rep.add_argument("--ledger", type=Path, default=None)
    p_rep.add_argument("--repo", default=DEFAULT_REPO)
    p_rep.add_argument("--min-n", type=int, default=30)
    args = parser.parse_args(argv)
    ledger_path = args.ledger or default_ledger_path(args.repo)
    if args.cmd == "update":
        counts = update(args.projects, ledger_path, args.repo, args.days, auth=args.gh_auth)
        print(json.dumps(counts))
        return 0
    sys.stdout.write(report(ledger_path, args.repo, args.min_n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
