#!/usr/bin/env python3
"""Find a skill by what the task needs, over the full content of every skill that is available.

WHY: Claude Code shows the model each skill's NAME always, but a DESCRIPTION only for the few
skills that fit a budget (about 45 of 250 on this install; the rest are name-only), and the
listing never contains a skill's body. A skill the user never typed and the model cannot guess
from its name is therefore invisible. This script is the missing second path: a plain lexical
search (BM25) over name, description, when_to_use, trigger phrases, headings and body of the
skills that are really available, run on demand. It is not a new router and not an index
service: no daemon, no cache, no vectors, no network, no writes.

Properties (each has a test):
  * Fresh by construction: the index is rebuilt from the files on every call (a few hundred
    small files), so adding, editing, renaming or removing a skill is visible at once.
  * Only skills the model can actually invoke are indexed: backups (``*.bak*``, ``*backup*``),
    ``skills-disabled``, ``_``/``.`` prefixed folders, ``disable-model-invocation: true``,
    and names set to ``off`` or ``user-invocable-only`` in ``skillOverrides`` are excluded.
    Unreadable or invalid files are skipped and counted, never fatal.
  * Scopes follow Claude Code: personal ``<home>/skills`` and project ``<project>/.claude/skills``
    (the project directory and its parents up to the git root). A personal skill wins over a
    project skill of the same name, as the documentation says.
  * "No suitable skill" is a normal answer: the result is empty unless the best match clears a
    score and a matched-terms floor, and it says to do the task directly.
  * Private names stay local: output goes to stdout only, nothing is written anywhere.

HOW TO USE (integration point, nothing is installed by this file): the native listing stays the
fast path. When no listed skill fits a non-trivial task, run
    python <path>/skill_search.py "<the task in your own words>"
and apply a candidate only if it really fits; an empty result means do the task directly.

Usage:
    python scripts/skill_search.py "разобрать падение продакшена и написать разбор" [--top 5]
    python scripts/skill_search.py "..." --json --explain
    python scripts/skill_search.py "..." --home ~/.claude --project .

Limits: lexical, so a query that shares no words with a skill (and no stem) will not find it;
a query typed into a shell command passes through the same command filters as any Bash text.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:  # PyYAML is a dev/CI dependency of this repo, not a runtime one: stdlib fallback below
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised by a test that blanks the module
    yaml = None  # type: ignore[assignment]

# Floors chosen on a development split (control false-recommendation rate <= 0.10 on two control
# sets, maximum recall on author trigger phrases) and then frozen; the held-out test split was
# never used to tune them. See the PR description for both splits and the numbers.
MIN_SCORE = 0.0
MIN_MATCHED = 1
MIN_COV = 0.6
MAX_TERMS = 6
TOP_DEFAULT = 5
BODY_CHARS = 8000

WEIGHTS = {"name": 3, "description": 2, "when": 2, "triggers": 2, "headings": 2, "body": 1}
EXCLUDED_DIR = re.compile(r"(\.bak|\.backup|[-_.]backup|\.disabled|\.orig|\.old)", re.I)
EXCLUDED_PARENT = re.compile(r"^(skills-disabled|skills-backup.*|_.*|\..*)$", re.I)
HIDDEN_OVERRIDES = {"off", "user-invocable-only"}
BANNER = re.compile(r"^(\s*\[[^\]]*\])+\s*")
TOKEN = re.compile(r"[a-zа-яё0-9]+")
STOP = frozenset(
    "the and for with that this from into your you are not but can will how what when use using "
    "used also any all per via one two new more most only such than then them they their there "
    "это как что для при или так его она они все был быть если уже ещё нужно можно надо чтобы "
    "через между после перед когда только также который которая которые своего свой себя".split()
)


@dataclass
class Skill:
    name: str
    path: str
    scope: str  # "user" | "project"
    purpose: str
    tokens: list[str] = field(default_factory=list)
    length: int = 0
    head: frozenset[str] = (
        frozenset()
    )  # terms of name, description, when_to_use, triggers, headings


def stem(word: str) -> str:
    """Crude suffix cut shared by Russian and English: keep the first five letters."""
    return word[:5] if len(word) > 5 else word


def tokenize(text: str) -> list[str]:
    return [stem(w) for w in TOKEN.findall(text.lower()) if len(w) >= 3 and w not in STOP]


# --------------------------------------------------------------------------- frontmatter


def _simple_frontmatter(block: str) -> dict:
    """Minimal fallback for the keys this script needs when PyYAML is not installed."""
    out: dict = {}
    key = None
    for raw in block.split("\n"):
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if m and not raw.startswith((" ", "\t")):
            key, val = m.group(1), m.group(2).strip()
            if val in (">", "|", ">-", "|-"):
                out[key] = ""
            elif val.startswith("[") and val.endswith("]"):
                out[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            else:
                out[key] = val.strip("\"'")
        elif key and raw.strip():
            item = raw.strip()
            if item.startswith("- "):
                cur = out.get(key)
                out[key] = (cur if isinstance(cur, list) else []) + [item[2:].strip("\"' ")]
            elif isinstance(out.get(key), str):
                out[key] = (out[key] + " " + item).strip()
    return out


def read_skill(path: Path) -> tuple[dict, str] | None:
    """Return (frontmatter, body) or None when the file is unusable."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace").lstrip("﻿")
    except OSError:
        return None
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    block, body = text[4:end], text[end + 4 :]
    try:
        fm = yaml.safe_load(block) if yaml is not None else _simple_frontmatter(block)
    except Exception:  # noqa: BLE001 - any YAML error means "skip this file"
        return None
    return (fm, body) if isinstance(fm, dict) else None


# --------------------------------------------------------------------------- discovery


def _overrides(files: list[Path]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        ov = data.get("skillOverrides") if isinstance(data, dict) else None
        if isinstance(ov, dict):
            merged.update({str(k): str(v) for k, v in ov.items()})
    return merged


def _project_roots(project: Path) -> list[Path]:
    """The project directory and its parents up to (and including) the git root."""
    roots = []
    cur = project.resolve()
    for d in [cur, *cur.parents]:
        roots.append(d / ".claude" / "skills")
        if (d / ".git").exists():
            break
    return roots


def iter_skill_files(base: Path) -> list[Path]:
    """SKILL.md files directly under base/<name>/, plus one nested level (repo layout)."""
    if not base.is_dir() or EXCLUDED_PARENT.match(base.name):
        return []
    found = []
    for child in sorted(base.iterdir()):
        if (
            not child.is_dir()
            or EXCLUDED_DIR.search(child.name)
            or child.name.startswith(("_", "."))
        ):
            continue
        if (child / "SKILL.md").is_file():
            found.append(child / "SKILL.md")
            continue
        for sub in sorted(child.iterdir()) if child.is_dir() else []:
            if (
                sub.is_dir()
                and not EXCLUDED_DIR.search(sub.name)
                and not sub.name.startswith(("_", "."))
                and (sub / "SKILL.md").is_file()
            ):
                found.append(sub / "SKILL.md")
    return found


def collect(
    home: Path,
    project: Path | None,
    include_triggers: bool = True,
    extra_roots: list[Path] | None = None,
) -> tuple[list[Skill], dict]:
    """Build the list of searchable skills and a stats dict (counts of what was left out)."""
    stats = {
        "scanned": 0,
        "indexed": 0,
        "skipped_unreadable": 0,
        "hidden_by_override": 0,
        "model_invocation_disabled": 0,
        "shadowed": 0,
    }
    override_files = [home / "settings.json"]
    if project is not None:
        override_files += [
            project / ".claude" / "settings.json",
            project / ".claude" / "settings.local.json",
        ]
    overrides = _overrides(override_files)
    scopes: list[tuple[str, Path]] = [("user", home / "skills")]
    if project is not None:
        scopes += [("project", r) for r in _project_roots(project)]
    scopes += [("user", Path(r)) for r in (extra_roots or [])]
    skills: dict[str, Skill] = {}
    for scope, base in scopes:
        for path in iter_skill_files(base):
            stats["scanned"] += 1
            parsed = read_skill(path)
            if parsed is None:
                stats["skipped_unreadable"] += 1
                continue
            fm, body = parsed
            name = str(fm.get("name") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9:_.-]+", name or ""):
                name = path.parent.name
            if overrides.get(name) in HIDDEN_OVERRIDES:
                stats["hidden_by_override"] += 1
                continue
            if (
                str(fm.get("disable-model-invocation", "")).lower() == "true"
                or fm.get("disable-model-invocation") is True
            ):
                stats["model_invocation_disabled"] += 1
                continue
            if name in skills:  # first scope wins: user scope is listed first
                stats["shadowed"] += 1
                continue
            desc = " ".join(str(fm.get("description") or "").split())
            when = " ".join(str(fm.get("when_to_use") or "").split())
            trig = fm.get("triggers")
            trig_text = (
                " ".join(str(t) for t in trig)
                if isinstance(trig, list) and include_triggers
                else ""
            )
            heads = " ".join(re.findall(r"^#{1,4}\s+(.+)$", body, re.M))
            purpose = BANNER.sub("", desc)
            m = re.search(r"(?<=[.!?])\s", purpose[:220])
            purpose = (purpose[: m.start()] if m else purpose[:160]).strip()
            fields = {
                "name": re.sub(r"[-_:./]", " ", name),
                "description": desc,
                "when": when,
                "triggers": trig_text,
                "headings": heads,
                "body": body[:BODY_CHARS],
            }
            toks: list[str] = []
            for f, text in fields.items():
                toks += tokenize(text) * WEIGHTS[f]
            head = frozenset(t for f, text in fields.items() if f != "body" for t in tokenize(text))
            skills[name] = Skill(name, str(path), scope, purpose, toks, len(toks), head)
    stats["indexed"] = len(skills)
    return list(skills.values()), stats


# --------------------------------------------------------------------------- ranking


class Index:
    """Term statistics for a list of skills; build once, then score many queries."""

    def __init__(self, skills: list[Skill], k1: float = 1.2, b: float = 0.75) -> None:
        self.skills, self.k1, self.b = skills, k1, b
        self.tfs: list[dict[str, int]] = []
        self.df: dict[str, int] = {}
        for s in skills:
            tf: dict[str, int] = {}
            for t in s.tokens:
                tf[t] = tf.get(t, 0) + 1
            self.tfs.append(tf)
            for t in tf:
                self.df[t] = self.df.get(t, 0) + 1
        self.avg = (sum(s.length for s in skills) / len(skills)) if skills else 1.0

    def idf(self, term: str) -> float:
        d = self.df.get(term, 0)
        return math.log(1 + (len(self.skills) - d + 0.5) / (d + 0.5))

    def condense(self, query: str, max_terms: int = MAX_TERMS) -> list[str]:
        """The most informative query terms that exist in the catalog at all.

        WHY: a long prompt accumulates BM25 score on common words, so scores of plain
        conversation and of real skill requests overlap. Keeping the few rarest known terms
        makes a long message behave like a short statement of intent and keeps coverage
        (below) comparable across query lengths.
        """
        toks = [t for t in dict.fromkeys(tokenize(query)) if t in self.df]
        toks.sort(key=lambda t: -self.idf(t))
        return toks[:max_terms]

    def rank(self, query: str, max_terms: int = MAX_TERMS) -> list[dict]:
        qt = self.condense(query, max_terms)
        if not self.skills or not qt:
            return []
        total = sum(self.idf(t) for t in qt) or 1.0
        out: list[dict] = []
        for s, tf in zip(self.skills, self.tfs, strict=True):
            score, matched = 0.0, []
            for t in qt:
                f = tf.get(t, 0)
                if not f:
                    continue
                score += (
                    self.idf(t)
                    * f
                    * (self.k1 + 1)
                    / (f + self.k1 * (1 - self.b + self.b * s.length / self.avg))
                )
                matched.append(t)
            if score > 0:
                out.append(
                    {
                        "name": s.name,
                        "score": round(score, 2),
                        "cov": round(sum(self.idf(t) for t in matched if t in s.head) / total, 3),
                        "matched": matched,
                        "matched_head": [t for t in matched if t in s.head],
                        "purpose": s.purpose,
                        "scope": s.scope,
                        "path": s.path,
                    }
                )
        out.sort(key=lambda r: (-float(r["score"]), r["name"]))
        return out


def rank(skills: list[Skill], query: str) -> list[dict]:
    return Index(skills).rank(query)


def decide(
    ranked: list[dict],
    top: int = TOP_DEFAULT,
    min_score: float = MIN_SCORE,
    min_matched: int = MIN_MATCHED,
    min_cov: float = MIN_COV,
) -> tuple[bool, list[dict]]:
    """Abstention rule: recommend only when the best match clears all three floors.

    ``cov`` is the share of the query's information (summed idf of the kept terms) that the
    best skill actually contains. A request that states an intent in the skill's own words
    scores near 1; ordinary conversation that happens to share a few common words does not.
    """
    if not ranked:
        return False, []
    best = ranked[0]
    if not (
        best["score"] >= min_score
        and len(best["matched_head"]) >= min_matched
        and best["cov"] >= min_cov
    ):
        return False, []
    return True, [r for r in ranked[:top] if r["score"] >= best["score"] * 0.6]


def search(
    query: str,
    home: Path,
    project: Path | None = None,
    top: int = TOP_DEFAULT,
    min_score: float = MIN_SCORE,
    min_matched: int = MIN_MATCHED,
    min_cov: float = MIN_COV,
    include_triggers: bool = True,
    extra_roots: list[Path] | None = None,
) -> dict:
    t0 = time.perf_counter()
    skills, stats = collect(home, project, include_triggers, extra_roots)
    ranked = Index(skills).rank(query)
    best = ranked[0] if ranked else None
    confident, cands = decide(ranked, top, min_score, min_matched, min_cov)
    return {
        "confident": confident,
        "candidates": cands,
        "best_unconfirmed": None
        if confident or not best
        else {"name": best["name"], "score": best["score"]},
        "stats": {**stats, "seconds": round(time.perf_counter() - t0, 3)},
    }


def render(res: dict, explain: bool) -> str:
    st = res["stats"]
    head = f"[skill-search] index: {st['indexed']} skills in {st['seconds']}s"
    if not res["confident"]:
        return (
            head + "\n[skill-search] no confident match: do the task directly. "
            "(The native listing stays the first path; nothing here is mandatory.)\n"
        )
    lines = [head + f"; {len(res['candidates'])} candidate(s), apply one only if it really fits:"]
    for i, c in enumerate(res["candidates"], 1):
        extra = f"  [matched: {', '.join(c['matched'])}]" if explain else ""
        lines.append(f"{i}. {c['name']} ({c['scope']}, score {c['score']}) - {c['purpose']}{extra}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("query", nargs="?", help="the task in your own words (or read from stdin)")
    ap.add_argument("--home", default=str(Path.home() / ".claude"))
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--root", action="append", default=[], help="extra skills directory")
    ap.add_argument("--top", type=int, default=TOP_DEFAULT)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--explain", action="store_true", help="show which terms matched")
    args = ap.parse_args(argv)
    query = args.query if args.query is not None else sys.stdin.read()
    res = search(
        query.strip(),
        Path(args.home).expanduser(),
        Path(args.project).expanduser(),
        top=args.top,
        extra_roots=[Path(r) for r in args.root],
    )
    sys.stdout.write(
        json.dumps(res, ensure_ascii=False, indent=2) + "\n"
        if args.json
        else render(res, args.explain)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
