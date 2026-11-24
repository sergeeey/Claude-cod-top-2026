#!/usr/bin/env python3
"""Skill usage report from Claude Code session transcripts (read-only, counts only).

WHY: nothing records which skills are used, how they were reached (user typed /name or the
model called the Skill tool), whether the model could even see the skill's description at
that moment, or what failed (``Unknown skill``). Without it a monthly skill evaluation is
guesswork. The raw material already exists in the transcripts under ``~/.claude/projects``:
tool calls, slash commands, and the exact skill listing the model received at session start
(``skill_listing`` attachments). This script only aggregates it.

Definitions (every count has one denominator, stated here):
  * activation = a user slash command that names a listed skill, or a model ``Skill`` tool call
    that did not fail with ``Unknown skill``. Model calls are deduplicated by tool_use id.
  * exposure of an activation = what the model's skill listing looked like in that session at
    that moment: ``description_visible``, ``name_only`` or ``unknown`` (no listing record in
    the session before it). The three add up to the skill's activations.
  * status: ``current`` = the name is in the most recent session listing of the window;
    ``historical`` = activated in the window but absent from that listing (renamed, removed,
    or a plugin skill that is no longer installed). Never-activated counts use CURRENT names
    only, so historical names cannot inflate them.
  * listed share = sessions whose listing contained the name / sessions with any listing in
    the window; described share is the same with "had a description".
  * ``failed_unknown`` = model calls whose tool result is ``Unknown skill``. Only results that
    answer a ``Skill`` tool call are counted, never text that merely quotes the error.
  * next5_tokens = mean of (input + output + cache creation) tokens over the next five
    distinct API requests after an activation, cache reads excluded, with the sample count.
    It is NOT the cost of the skill: those requests also carry unrelated work.

PRIVACY: only skill names and counts are written. No prompt text, no tool arguments, no file
contents. The transcripts are opened read-only.

LIMITS (stated, not hidden): a model call may follow a prompt or rule that names the skill, so
"model activation" is not "discovered from the description". Slash commands count as skills
only if the name appears in some listing seen in the window.

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

SCHEMA = 2
POST_REQUESTS = 5
SLASH_RE = re.compile(r"<command-name>/?([^<\s]+)</command-name>")


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


def resolve_name(name: str, candidates: set[str]) -> str:
    """Map a typed or called name to the name the listing uses.

    ``/alpha`` and a Skill call for ``alpha`` must land on the listed ``plugin:alpha`` so that
    activation, exposure and token statistics share one identity. An exact match wins; a bare
    name is resolved only when exactly one candidate has the same last segment.
    """
    if not candidates or name in candidates:
        return name
    last = name.split(":")[-1]
    hits = [c for c in candidates if c.split(":")[-1] == last]
    return hits[0] if len(hits) == 1 else name


def exposure(name: str, listed: set[str], described: set[str]) -> str:
    if not listed:
        return "unknown"
    return "description_visible" if name in described else "name_only"


class Report:
    def __init__(self) -> None:
        self.model: Counter[str] = Counter()
        self.slash_all: Counter[str] = Counter()  # any slash command, filtered later
        self.slash_expo: dict[str, Counter[str]] = defaultdict(Counter)
        self.model_expo: dict[str, Counter[str]] = defaultdict(Counter)
        self.failed: Counter[str] = Counter()
        self.sessions_active: dict[str, set[str]] = defaultdict(set)
        self.sessions_listed: dict[str, set[str]] = defaultdict(set)
        self.sessions_described: dict[str, set[str]] = defaultdict(set)
        self.post_tokens: dict[str, list[int]] = defaultdict(list)
        self.known_names: set[str] = set()
        self.sessions_with_listing: set[str] = set()
        self.latest_ts = ""
        self.latest_names: set[str] = set()
        self.files = 0
        self.records = 0


def in_window(ts: str | None, since: str) -> bool:
    return bool(ts) and str(ts)[:10] >= since


def scan_file(path: Path, rep: Report, since: str) -> None:
    session = path.parent.parent.name if path.parent.name == "subagents" else path.stem
    rep.files += 1
    skill_calls: dict[str, tuple[str, str]] = {}  # tool_use id -> (name, exposure)
    seen_slash_uuids: set[str] = set()
    described_now: set[str] = set()
    listed_now: set[str] = set()
    pending: list[dict] = []  # activations waiting for post-activation requests
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            wants_usage = bool(pending) and '"usage"' in line
            if not (
                "skill_listing" in line
                or '"Skill"' in line  # any JSON spacing; the block is checked after parsing
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
                        rep.sessions_with_listing.add(session)
                        rep.known_names |= listed_now
                        if str(ts) > rep.latest_ts:
                            rep.latest_ts = str(ts)
                            rep.latest_names = set(listed_now)
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
                            if not name or tid in skill_calls:
                                continue
                            name = resolve_name(name, listed_now)
                            expo = exposure(name, listed_now, described_now)
                            skill_calls[tid] = (name, expo)
                            rep.model[name] += 1
                            rep.model_expo[name][expo] += 1
                            rep.sessions_active[name].add(session)
                            own = msg.get("id") or rec.get("uuid")
                            pending.append({"name": name, "skip": {own}, "ids": set(), "tokens": 0})
            elif rec.get("type") == "user" and in_window(ts, since):
                body = msg.get("content")
                if isinstance(body, list):
                    # a failed Skill call: the result answers one of OUR Skill tool_use ids
                    for block in body:
                        if not (isinstance(block, dict) and block.get("type") == "tool_result"):
                            continue
                        info = skill_calls.get(str(block.get("tool_use_id")))
                        if info and "Unknown skill" in json.dumps(block.get("content")):
                            name, expo = info
                            rep.failed[name] += 1
                            rep.model[name] -= 1
                            rep.model_expo[name][expo] -= 1
                            skill_calls.pop(str(block.get("tool_use_id")))
                elif isinstance(body, str):
                    m2 = SLASH_RE.search(body)
                    uid = str(rec.get("uuid"))
                    if m2 and uid not in seen_slash_uuids:
                        seen_slash_uuids.add(uid)
                        name = resolve_name(m2.group(1), listed_now)
                        rep.slash_all[name] += 1
                        rep.slash_expo[name][exposure(name, listed_now, described_now)] += 1
                        rep.sessions_active[name].add(session)
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
    slash: Counter[str] = Counter()
    for raw, c in rep.slash_all.items():
        canon = resolve_name(raw, rep.known_names)
        if canon not in rep.known_names:
            continue
        slash[canon] += c
        if canon != raw:  # activations from sessions without a listing keep the raw name
            rep.slash_expo[canon].update(rep.slash_expo.pop(raw, Counter()))
            rep.sessions_active[canon] |= rep.sessions_active.pop(raw, set())
            rep.post_tokens[canon] += rep.post_tokens.pop(raw, [])
    names = {n for n, c in rep.model.items() if c > 0} | set(slash) | set(rep.failed)
    total_sessions = len(rep.sessions_with_listing)
    rows: list[dict[str, Any]] = []
    for name in names:
        expo: Counter[str] = Counter()
        expo.update(rep.model_expo.get(name, Counter()))
        expo.update(rep.slash_expo.get(name, Counter()) if name in slash else Counter())
        post = rep.post_tokens.get(name, [])
        rows.append(
            {
                "skill": name,
                "status": "current" if name in rep.latest_names else "historical",
                "user_slash": slash.get(name, 0),
                "model_activations": max(rep.model.get(name, 0), 0),
                "failed_unknown": rep.failed.get(name, 0),
                "activations_description_visible": max(expo.get("description_visible", 0), 0),
                "activations_name_only": max(expo.get("name_only", 0), 0),
                "activations_exposure_unknown": max(expo.get("unknown", 0), 0),
                "model_description_visible": max(
                    rep.model_expo.get(name, Counter()).get("description_visible", 0), 0
                ),
                "model_name_only": max(rep.model_expo.get(name, Counter()).get("name_only", 0), 0),
                "model_exposure_unknown": max(
                    rep.model_expo.get(name, Counter()).get("unknown", 0), 0
                ),
                "sessions_active": len(rep.sessions_active.get(name, set())),
                "sessions_listed": len(rep.sessions_listed.get(name, set())),
                "sessions_description_visible": len(rep.sessions_described.get(name, set())),
                "next5_tokens_mean": round(sum(post) / len(post)) if post else None,
                "next5_samples": len(post),
            }
        )
    rows.sort(key=lambda r: -(r["user_slash"] + r["model_activations"]))
    activated = {r["skill"] for r in rows if r["user_slash"] + r["model_activations"] > 0}
    current_never = sorted(n for n in rep.latest_names if n not in activated)
    return {
        "schema": SCHEMA,
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_since": since,
        "files_scanned": rep.files,
        "records_parsed": rep.records,
        "sessions_with_listing": total_sessions,
        "latest_listing_utc": rep.latest_ts or None,
        "current_listed_skills": len(rep.latest_names),
        "current_listed_activated": len(rep.latest_names & activated),
        "current_listed_never_activated": len(current_never),
        "historical_names_activated": len(activated - rep.latest_names),
        "activations_user_slash": sum(r["user_slash"] for r in rows),
        "activations_model": sum(r["model_activations"] for r in rows),
        "model_calls_failed_unknown": sum(r["failed_unknown"] for r in rows),
        "model_activations_by_exposure": {
            "description_visible": sum(r["model_description_visible"] for r in rows),
            "name_only": sum(r["model_name_only"] for r in rows),
            "unknown": sum(r["model_exposure_unknown"] for r in rows),
        },
        "skills": rows,
        "current_never_activated_names": current_never,
    }


def render(rep: dict) -> str:
    L = [
        f"# Skill usage report (since {rep['window_since']})",
        "",
        f"Sessions with a skill listing: {rep['sessions_with_listing']}. Latest listing "
        f"({rep['latest_listing_utc']}): {rep['current_listed_skills']} skills, "
        f"{rep['current_listed_activated']} activated in the window, "
        f"{rep['current_listed_never_activated']} never activated. "
        f"Historical names activated (not in the latest listing): "
        f"{rep['historical_names_activated']}.",
        f"Activations: {rep['activations_user_slash']} by the user (slash), "
        f"{rep['activations_model']} by the model (Skill tool); "
        f"{rep['model_calls_failed_unknown']} model calls failed with Unknown skill.",
        "",
        "Exposure columns count activations by what the model's listing showed at that moment: "
        "description visible / name only / unknown (no listing record).",
        "",
        "| Skill | Status | Slash | Model | Desc | Name only | Exposure unknown | Failed | "
        "Sessions listed | Next-5 tokens mean (n) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rep["skills"][:60]:
        post = "-" if r["next5_tokens_mean"] is None else f"{r['next5_tokens_mean']}"
        L.append(
            f"| {r['skill']} | {r['status']} | {r['user_slash']} | {r['model_activations']} | "
            f"{r['activations_description_visible']} | {r['activations_name_only']} | "
            f"{r['activations_exposure_unknown']} | {r['failed_unknown']} | "
            f"{r['sessions_listed']}/{rep['sessions_with_listing']} | "
            f"{post} ({r['next5_samples']}) |"
        )
    if len(rep["skills"]) > 60:
        L.append(f"| ... {len(rep['skills']) - 60} more in the JSON | | | | | | | | | |")
    L += [
        "",
        "Counts only; no prompt text. A model activation can follow a prompt or rule that names "
        "the skill, so it does not prove discovery from the description. Next-5 tokens are not "
        "the cost of the skill: those requests also carry unrelated work.",
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
    if args.json:
        sys.stdout.write(json.dumps(rep, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
