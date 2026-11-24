#!/usr/bin/env python3
"""Skill usage report from Claude Code session transcripts (read-only, counts only).

WHY: nothing records which skills are used, how they were reached (user typed /name or the
model called the Skill tool), whether the model could even see the skill's description at
that moment, or what failed (``Unknown skill``). Without it a monthly skill evaluation is
guesswork. The raw material already exists in the transcripts under ``~/.claude/projects``:
tool calls, slash commands, and the exact skill listing the model received at session start
(``skill_listing`` attachments). This script only aggregates it.

What it reports, per skill, for a time window:
  * activations by the user (slash command) and by the model (Skill tool call, deduplicated
    by tool_use id, so a record repeated by session resume counts once);
  * exposure: in how many of the sessions that activated it the skill's DESCRIPTION was in
    the listing (the rest saw the name only), and in how many sessions it was listed at all;
  * ``Unknown skill`` errors by name (stale names after renames);
  * context added after an activation: mean tokens (input + output + cache creation, cache
    reads excluded) over the next few distinct API requests.

PRIVACY: only skill names and counts are written. No prompt text, no tool arguments, no file
contents. The transcripts are opened read-only.

LIMITS (stated, not hidden): a model call may follow a prompt or rule that names the skill, so
"model-initiated" is not "discovered from the description". Slash commands are counted as
skills only if the name appears in some listing seen in the window. Post-activation tokens
are an approximation: the next requests also carry unrelated work.

Usage:
    python scripts/skill_usage_report.py                       # last 30 days, Markdown
    python scripts/skill_usage_report.py --since 2026-10-25 --json
    python scripts/skill_usage_report.py --root DIR --out report_dir
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

POST_REQUESTS = 5
SLASH_RE = re.compile(r"<command-name>/?([^<\s]+)</command-name>")
UNKNOWN_RE = re.compile(r"Unknown skill: ([A-Za-z0-9:_.-]+)")
LISTING_LINE = re.compile(r"^- ([^\s:][^:]*?)(?:: .*)?$")


def parse_listing(content: str) -> tuple[set[str], set[str]]:
    """Return (all names, names with a description) from a skill_listing attachment."""
    names: set[str] = set()
    described: set[str] = set()
    for line in content.split("\n"):
        if not line.startswith("- "):
            continue
        body = line[2:]
        m = re.match(r"([\w:.\-/]+): ", body)
        if m:
            names.add(m.group(1))
            described.add(m.group(1))
        else:
            names.add(body.strip())
    return names, described


def usage_tokens(usage: dict) -> int:
    """Tokens that add context or output; cache reads are excluded on purpose."""
    return (
        int(usage.get("input_tokens") or 0)
        + int(usage.get("output_tokens") or 0)
        + int(usage.get("cache_creation_input_tokens") or 0)
    )


class Report:
    def __init__(self) -> None:
        self.model_calls: Counter[str] = Counter()
        self.slash_calls: Counter[str] = Counter()
        self.slash_all: Counter[str] = Counter()  # any slash command, filtered later
        self.sessions_active: dict[str, set[str]] = defaultdict(set)
        self.sessions_listed: dict[str, set[str]] = defaultdict(set)
        self.sessions_described: dict[str, set[str]] = defaultdict(set)
        self.active_with_description: dict[str, set[str]] = defaultdict(set)
        self.unknown: dict[str, set[str]] = defaultdict(set)
        self.post_tokens: dict[str, list[int]] = defaultdict(list)
        self.known_names: set[str] = set()
        self.sessions_seen: set[str] = set()
        self.files = 0
        self.records = 0


def in_window(ts: str | None, since: str) -> bool:
    return bool(ts) and str(ts)[:10] >= since


def scan_file(path: Path, rep: Report, since: str) -> None:
    session = path.parent.parent.name if path.parent.name == "subagents" else path.stem
    rep.files += 1
    seen_tool_ids: set[str] = set()
    seen_slash_uuids: set[str] = set()
    described_now: set[str] = set()
    listed_now: set[str] = set()
    pending: list[dict] = []  # activations waiting for post-activation requests
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            wants_usage = bool(pending) and '"usage"' in line
            if not (
                "skill_listing" in line
                or '"name":"Skill"' in line
                or "<command-name>" in line
                or "Unknown skill" in line
                or wants_usage
            ):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            rep.records += 1
            ts = rec.get("timestamp")
            att = rec.get("attachment")
            if isinstance(att, dict) and att.get("type") == "skill_listing":
                if att.get("isInitial"):
                    listed_now, described_now = parse_listing(str(att.get("content") or ""))
                    if in_window(ts, since):
                        rep.sessions_seen.add(session)
                        rep.known_names |= listed_now
                        for n in listed_now:
                            rep.sessions_listed[n].add(session)
                        for n in described_now:
                            rep.sessions_described[n].add(session)
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            if rec.get("type") == "assistant":
                usage = msg.get("usage")
                if pending and isinstance(usage, dict) and msg.get("model") != "<synthetic>":
                    mid = msg.get("id") or rec.get("uuid")
                    for act in list(pending):
                        # the request that made the call (and its repeated records) is not "after"
                        if mid in act["skip"] or mid in act["ids"]:
                            continue
                        act["ids"].add(mid)
                        act["tokens"] += usage_tokens(usage)
                        if len(act["ids"]) >= POST_REQUESTS:
                            rep.post_tokens[act["name"]].append(act["tokens"])
                            pending.remove(act)
                content = msg.get("content")
                if isinstance(content, list) and in_window(ts, since):
                    for block in content:
                        if (
                            isinstance(block, dict)
                            and block.get("type") == "tool_use"
                            and block.get("name") == "Skill"
                        ):
                            tid = str(block.get("id"))
                            name = str((block.get("input") or {}).get("skill") or "")
                            if not name or tid in seen_tool_ids:
                                continue
                            seen_tool_ids.add(tid)
                            rep.model_calls[name] += 1
                            rep.sessions_active[name].add(session)
                            if name in described_now:
                                rep.active_with_description[name].add(session)
                            own = msg.get("id") or rec.get("uuid")
                            pending.append({"name": name, "skip": {own}, "ids": set(), "tokens": 0})
            elif rec.get("type") == "user" and in_window(ts, since):
                raw = json.dumps(msg.get("content"), ensure_ascii=False)
                for m in UNKNOWN_RE.finditer(raw):
                    rep.unknown[m.group(1)].add(session)
                text = msg.get("content")
                if isinstance(text, str):
                    m2 = SLASH_RE.search(text)
                    uid = str(rec.get("uuid"))
                    if m2 and uid not in seen_slash_uuids:
                        seen_slash_uuids.add(uid)
                        name = m2.group(1)
                        rep.slash_all[name] += 1
                        rep.sessions_active[name].add(session)
                        if name in described_now:
                            rep.active_with_description[name].add(session)
                        pending.append({"name": name, "skip": set(), "ids": set(), "tokens": 0})
    for act in pending:  # fewer than POST_REQUESTS requests followed: keep what exists
        if act["ids"]:
            rep.post_tokens[act["name"]].append(act["tokens"])


def build(root: Path, since: str) -> dict:
    rep = Report()
    cutoff = datetime.fromisoformat(since).replace(tzinfo=UTC).timestamp() - 86400
    for path in sorted(root.rglob("*.jsonl")):
        try:
            if path.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        scan_file(path, rep, since)
    # slash commands count as skills only when the name was listed in the window
    for name, n in rep.slash_all.items():
        if name in rep.known_names or name.split(":")[-1] in {
            k.split(":")[-1] for k in rep.known_names
        }:
            rep.slash_calls[name] = n
    names = set(rep.model_calls) | set(rep.slash_calls)
    rows: list[dict[str, Any]] = []
    for name in names:
        active = rep.sessions_active.get(name, set())
        visible = rep.active_with_description.get(name, set())
        post = rep.post_tokens.get(name, [])
        rows.append(
            {
                "skill": name,
                "user_slash": rep.slash_calls.get(name, 0),
                "model_calls": rep.model_calls.get(name, 0),
                "sessions_active": len(active),
                "sessions_active_with_description_visible": len(visible),
                "sessions_listed": len(rep.sessions_listed.get(name, set())),
                "sessions_description_visible": len(rep.sessions_described.get(name, set())),
                "post_activation_tokens_mean": round(sum(post) / len(post)) if post else None,
            }
        )
    rows.sort(key=lambda r: -(r["user_slash"] + r["model_calls"]))
    never = sorted(n for n in rep.known_names if n not in names)
    return {
        "schema": 1,
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_since": since,
        "files_scanned": rep.files,
        "records_parsed": rep.records,
        "sessions_with_listing": len(rep.sessions_seen),
        "listed_skills": len(rep.known_names),
        "skills_activated": len(rows),
        "total_user_slash": sum(r["user_slash"] for r in rows),
        "total_model_calls": sum(r["model_calls"] for r in rows),
        "listed_never_activated": len(never),
        "unknown_skill_errors": {k: len(v) for k, v in sorted(rep.unknown.items())},
        "skills": rows,
        "never_activated_names": never,
    }


def render(rep: dict) -> str:
    L = [
        f"# Skill usage report (since {rep['window_since']})",
        "",
        f"Transcripts scanned: {rep['files_scanned']}; sessions with a listing: "
        f"{rep['sessions_with_listing']}; skills in listings: {rep['listed_skills']}; "
        f"activated: {rep['skills_activated']}; never activated: {rep['listed_never_activated']}.",
        f"Activations: {rep['total_user_slash']} by the user (slash), "
        f"{rep['total_model_calls']} by the model (Skill tool).",
        "",
        "| Skill | Slash | Model | Sessions active | Of those, description visible | "
        "Sessions listed | Post-activation tokens (mean) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rep["skills"][:60]:
        post = r["post_activation_tokens_mean"]
        post_text = "-" if post is None else str(post)
        L.append(
            f"| {r['skill']} | {r['user_slash']} | {r['model_calls']} | {r['sessions_active']} | "
            f"{r['sessions_active_with_description_visible']} | {r['sessions_listed']} | "
            f"{post_text} |"
        )
    if len(rep["skills"]) > 60:
        L.append(f"| ... {len(rep['skills']) - 60} more in the JSON | | | | | | |")
    L += ["", "## Unknown skill errors (sessions per name)", ""]
    if rep["unknown_skill_errors"]:
        L += [f"- {k}: {v}" for k, v in rep["unknown_skill_errors"].items()]
    else:
        L.append("none in the window")
    L += [
        "",
        "Counts only; no prompt text. A model call can follow a prompt or rule that names the "
        "skill, so it does not prove discovery from the description.",
    ]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--root", default=str(Path.home() / ".claude" / "projects"))
    ap.add_argument("--since", help="YYYY-MM-DD (default: 30 days ago)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    ap.add_argument("--out", help="directory for skill-usage-<date>.md and .json")
    args = ap.parse_args(argv)
    since = args.since or (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
    rep = build(Path(args.root).expanduser(), since)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y-%m-%d")
        (out / f"skill-usage-{stamp}.json").write_text(
            json.dumps(rep, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out / f"skill-usage-{stamp}.md").write_text(render(rep), encoding="utf-8")
        print(f"written to {out}")
        return 0
    sys.stdout.write(
        json.dumps(rep, indent=2, ensure_ascii=False) + "\n" if args.json else render(rep)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
