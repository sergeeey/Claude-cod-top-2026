#!/usr/bin/env python3
"""Build a derived, read-only catalog of research experiments (JSONL + Markdown twin).

WHY: a finished experiment can exist only in a git worktree, on a branch that is not
merged, or as untracked files. Neither the experiments index nor any search covers those
places, so a fresh agent proposed redoing a finished study from scratch. This script walks
the given roots and every git worktree/branch of the repos it finds, and writes one record
per experiment object.

The catalog is a VIEW, never a source of truth: each record points at the artifact that
owns the result (`canonical_path`). Regenerate it; do not edit it.

State of an object (best location wins when the same folder name exists in several places):
  MERGED_DEFAULT        decision file is on the default branch (origin/main or main)
  COMMITTED_BRANCH      committed on some other branch / worktree, not on the default branch
  UNCOMMITTED_ORPHAN    exists on disk only, in no commit of any branch

Usage:
  python scripts/build_research_catalog.py --root D:/Claude-cod-top-2026 --root E:/Hypotheses
  python scripts/build_research_catalog.py --root ... --out DIR   # DIR/RESEARCH_CATALOG.{jsonl,md}

Read-only on every scanned root; writes only the two output files. Local refs only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_OUT = Path.home() / ".claude" / "memory" / "knowledge" / "registry"
# Folders that are copies/snapshots of an experiment, not the experiment itself.
COPY_MARKERS = (
    "workspace-temp",
    f"{os.sep}tmp{os.sep}",
    "-review" + os.sep,
    f"{os.sep}mut{os.sep}",
    f"{os.sep}copies{os.sep}",
    "gov_copies",
    "phase4",
    "snapshot",
    "backup",
    "y17_audit",
    "_template",
)
PRUNE = {".git", "node_modules", ".venv", "venv", "__pycache__", "site-packages", ".obsidian"}
DECISION = re.compile(r"^decision.*\.md$", re.IGNORECASE)
FIXTURE = re.compile(r"^(\d{8}-test|_template|template|example|sample)$", re.IGNORECASE)
VERDICTS = (
    "PROMOTE|REJECT|REPEAT|ARCHIVE|IMPROVE|KILL|REVIVE|PARK|NEEDS-HUMAN|CONFIRMED|REFUTED|NULL|LEAD"
)
_CHECKED = re.compile(rf"\[[xX]\]\s*\**\s*({VERDICTS})", re.IGNORECASE)
# A checked box with a project-specific verdict (`- [x] **CRITERION_INVALID**`): UPPER_CASE only,
# so a checked prose item ("[x] Peter Lake lead ...") is never a verdict.
_CHECKED_ANY = re.compile(r"\[[xX]\]\s*\**\s*([A-Z][A-Z0-9_-]{2,40})\b")
# '[' and ']' are excluded from the gap so an unchecked option list ("## Decision\n- [ ] PROMOTE")
# is never read as the verdict.
_LABELLED = re.compile(rf"(?:verdict|decision)[^\w\[\]]{{0,12}}\**\s*({VERDICTS})", re.IGNORECASE)
_STATE_RANK = {"MERGED_DEFAULT": 0, "COMMITTED_BRANCH": 1, "UNCOMMITTED_ORPHAN": 2}


def _git(cwd: Path, *args: str, timeout: int = 20) -> str | None:
    try:
        res = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout if res.returncode == 0 else None


# A free-form verdict is an UPPER_CASE token (CANONICAL_PROXY_ONLY, PASS_CALIBRATED), so prose
# such as "## Decision\n\nWe decided ..." and a "# decision.md" title never count. Level-1
# headings are document titles and are skipped.
_HEADING_VALUE = re.compile(
    r"^#{2,4}[ \t]*(?i:verdict|decision|вердикт|решение)\b[^\n]*\n+"
    r"[\s>*`_-]*([A-Z][A-Z0-9_./-]{1,40})\b",
    re.MULTILINE,
)
_LABEL_VALUE = re.compile(
    r"^[#*\s>-]*(?i:verdict|вердикт)\b[^\n]{0,6}?[:—]+[*\s`]*([A-Z][A-Z0-9_./-]{1,40})\b",
    re.MULTILINE,
)


def parse_verdict(text: str) -> str:
    """Verdict word of a decision file.

    1. A checked box (`[x] REJECT`) is explicit and wins.
    2. Otherwise the EARLIEST of: labelled known verdict, free-form value under a 'Verdict'
       heading, free-form value after a 'Verdict:' label. A decision file states its own verdict
       first and may quote other experiments' verdicts further down, so a later
       'Verdict: CONFIRMED' reference must not override this file's own 'Verdict: WEAKENED'.
    Free-form verdicts are common (CANONICAL_PROXY_ONLY); they are returned upper-cased, as
    written, never mapped. Nothing recognised -> UNKNOWN.
    """
    for rx in (_CHECKED, _CHECKED_ANY):
        m = rx.search(text)
        if m:
            return m.group(1).upper()
    best: tuple[int, str] | None = None
    for rx in (_LABELLED, _HEADING_VALUE, _LABEL_VALUE):
        m = rx.search(text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), m.group(1).upper().strip("._-"))
    return best[1] if best else "UNKNOWN"


_CLAIM_ROW = re.compile(
    r"^\|\s*\**\s*(entity|falsifiable predicate|claim|hypothesis|question)\s*\**\s*\|"
    r"\s*([^|]{15,})\|",
    re.IGNORECASE | re.MULTILINE,
)
_ADMIN_LINE = re.compile(r"^(written|date|status|follows|created|updated|author)\b", re.IGNORECASE)


def _claim_summary(exp: Path) -> str:
    """Prefer the substantive claim rows (Entity / Falsifiable predicate) over admin prose.

    WHY: the first body line of a claim.md is often 'Written 2026-10-14 BEFORE ...', which says
    nothing about the question, so a search by meaning could not match the experiment.
    """
    f = exp / "claim.md"
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    parts = [m.group(2).strip().strip("*` ") for m in _CLAIM_ROW.finditer(text)]
    return " ".join(parts)[:280]


def parse_title_summary(exp: Path) -> tuple[str, str]:
    title, summary = exp.name, ""
    seen_heading = False  # only the document's first heading can be its title
    for fname in ("claim.md", *sorted(p.name for p in exp.glob("decision*.md"))):
        f = exp / fname
        if not f.is_file():
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                if title == exp.name and not seen_heading:
                    seen_heading = True
                    t = re.sub(r"^[#\s]+", "", s)
                    t = re.sub(r"^(claim|decision)(\.md)?\s*[—–-]+\s*", "", t, flags=re.I)
                    t = t.replace(exp.name, "").strip(" —–-:")
                    if t:
                        title = t[:140]
                continue
            if _ADMIN_LINE.match(s.lstrip("-*> ")):
                continue
            summary = s.lstrip("-*> ")[:280]
            break
        if summary:
            break
    return title, _claim_summary(exp) or summary


def _is_copy(rel_path: str) -> bool:
    """True if a path RELATIVE to its scan root looks like a copy/snapshot of an experiment.

    WHY relative: a legitimate repo that lives under /tmp (CI temp dirs, pytest's tmp_path) must
    not be discarded because an ancestor of the scan root contains a copy marker.
    """
    return any(m in os.sep + rel_path + os.sep for m in COPY_MARKERS)


def _expand_with_worktrees(roots: list[Path]) -> list[Path]:
    """Add every linked git worktree of the repos the roots live in (they may be elsewhere)."""
    seen: dict[str, Path] = {}
    for root in roots:
        if root.is_dir():
            seen.setdefault(os.path.normcase(str(root.resolve())), root)
    given = list(seen.values())
    for root in given:
        out = _git(root, "worktree", "list", "--porcelain")
        for line in (out or "").splitlines():
            if not line.startswith("worktree "):
                continue
            wt = Path(line[len("worktree ") :])
            if not wt.is_dir():
                continue
            # Never widen a scan to a checkout that CONTAINS the given root (e.g. a root that
            # is a plain folder inside a larger repo): only the repo's other worktrees count.
            if any(
                wt.resolve() == r.resolve() or wt.resolve() in r.resolve().parents for r in given
            ):
                continue
            seen.setdefault(os.path.normcase(str(wt.resolve())), wt)
    return list(seen.values())


def _find_experiment_dirs(roots: list[Path]) -> list[Path]:
    found: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in PRUNE]
            if Path(d).parent.name != "experiments":
                continue
            if any(DECISION.match(f) for f in files):
                dirs[:] = []  # an experiment folder; do not descend into its stand/ data
                if not _is_copy(os.path.relpath(d, root)):
                    found.setdefault(os.path.normcase(str(Path(d).resolve())), Path(d))
    return list(found.values())


def _default_ref(repo: Path) -> str | None:
    for ref in ("origin/main", "origin/master", "main", "master"):
        if _git(repo, "rev-parse", "--verify", "-q", ref) is not None:
            return ref
    return None


def _on_default(repo: Path, ref: str | None, rel: str) -> bool:
    return bool(ref) and _git(repo, "cat-file", "-e", f"{ref}:{rel}") is not None


def _record(exp: Path, repo: Path | None, ref: str | None) -> dict:
    text = ""
    for f in sorted(exp.glob("decision*.md")):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        break
    title, summary = parse_title_summary(exp)
    state, rel = "UNCOMMITTED_ORPHAN", ""
    if repo is not None:
        rel = os.path.relpath(exp, repo).replace(os.sep, "/")
        tracked = _git(exp, "ls-files", "--", ".")
        if tracked and tracked.strip():
            state = (
                "MERGED_DEFAULT"
                if _on_default(repo, ref, f"{rel}/{_first_decision(exp)}")
                else "COMMITTED_BRANCH"
            )
        elif _git(repo, "log", "--all", "-1", "--format=%h", "--", rel):
            state = "COMMITTED_BRANCH"
    return {
        "research_id": exp.name,
        "kind": "experiment",
        "state": state,
        "verdict": parse_verdict(text),
        "title": title,
        "summary": summary,
        "date": exp.name[:8] if exp.name[:8].isdigit() else "",
        "repo": str(repo) if repo else "",
        "canonical_path": str(exp),
        "aliases": [],
    }


def _first_decision(exp: Path) -> str:
    for f in sorted(exp.glob("decision*.md")):
        return f.name
    return "decision.md"


def _branch_only_records(repo: Path, known: set[str]) -> list[dict]:
    out: list[dict] = []
    refs = _git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    rx = re.compile(r"(?:^|/)experiments/([^/]+)/(decision[^/]*\.md)$", re.IGNORECASE)
    for branch in (refs or "").split():
        files = _git(repo, "ls-tree", "-r", "--name-only", branch, timeout=40)
        for path in (files or "").splitlines():
            m = rx.search(path)
            if not m or m.group(1).lower() in known or FIXTURE.match(m.group(1)):
                continue
            known.add(m.group(1).lower())
            text = _git(repo, "show", f"{branch}:{path}") or ""
            first = next(
                (ln.strip("# ").strip() for ln in text.splitlines() if ln.startswith("#")), ""
            )
            out.append(
                {
                    "research_id": m.group(1),
                    "kind": "experiment",
                    "state": "COMMITTED_BRANCH",
                    "verdict": parse_verdict(text),
                    "title": first[:140] or m.group(1),
                    "summary": "",
                    "date": m.group(1)[:8] if m.group(1)[:8].isdigit() else "",
                    "repo": str(repo),
                    "canonical_path": f"git:{branch}:{path.rsplit('/', 1)[0]}",
                    "aliases": [],
                }
            )
    return out


def build(roots: list[Path]) -> list[dict]:
    roots = _expand_with_worktrees(roots)
    dirs = _find_experiment_dirs(roots)
    toplevels: dict[Path, Path | None] = {}
    refs: dict[Path, str | None] = {}
    by_name: dict[str, list[dict]] = {}
    for exp in dirs:
        if FIXTURE.match(exp.name):
            continue
        parent = exp.parent
        if parent not in toplevels:
            top = _git(parent, "rev-parse", "--show-toplevel")
            toplevels[parent] = Path(top.strip()) if top else None
        repo = toplevels[parent]
        if repo is not None and repo not in refs:
            refs[repo] = _default_ref(repo)
        rec = _record(exp, repo, refs.get(repo) if repo else None)
        by_name.setdefault(exp.name.lower(), []).append(rec)

    catalog: list[dict] = []
    for _name, recs in by_name.items():
        recs.sort(key=lambda r: (_STATE_RANK[r["state"]], r["canonical_path"]))
        best = recs[0]
        best["aliases"] = [r["canonical_path"] for r in recs[1:]]
        catalog.append(best)

    # Repos to inspect for branch-only experiments: those that hold a found folder, plus the
    # repo (and every worktree's repo) of each root, so a repo with nothing on disk still counts.
    repos = {r for r in toplevels.values() if r is not None}
    for root in roots:
        top = _git(root, "rev-parse", "--show-toplevel") if root.is_dir() else None
        if top:
            repos.add(Path(top.strip()))
    known = set(by_name)
    for repo in sorted(repos):
        catalog.extend(_branch_only_records(repo, known))
    catalog.sort(key=lambda r: (r["date"] or "0", r["research_id"]))
    return catalog


def write(catalog: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    jl, md = out_dir / "RESEARCH_CATALOG.jsonl", out_dir / "RESEARCH_CATALOG.md"
    with jl.open("w", encoding="utf-8", newline="\n") as f:
        for rec in catalog:
            f.write(json.dumps({**rec, "generated_at": stamp}, ensure_ascii=False) + "\n")
    states: dict[str, int] = {}
    for r in catalog:
        states[r["state"]] = states.get(r["state"], 0) + 1
    lines = [
        "# Research catalog (generated, do not edit)",
        "",
        f"Generated {stamp}. A derived view of experiment folders across repos, worktrees and",
        "branches; each row points to the artifact that owns the result. Regenerate with",
        "`python scripts/build_research_catalog.py`.",
        "",
        "States: " + ", ".join(f"{k}={v}" for k, v in sorted(states.items())),
        "",
        "| id | state | verdict | title | summary | where |",
        "|---|---|---|---|---|---|",
    ]
    for r in catalog:
        title = r["title"].replace("|", "/")
        summary = r["summary"].replace("|", "/")[:240]
        row = [r["research_id"], r["state"], r["verdict"], title, summary, r["canonical_path"]]
        lines.append("| " + " | ".join(row) + " |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return jl, md


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", action="append", required=True, help="directory to scan (repeatable)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    args = ap.parse_args(argv)
    catalog = build([Path(r) for r in args.root])
    jl, md = write(catalog, Path(args.out))
    counts: dict[str, int] = {}
    for r in catalog:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    print(f"[catalog] {len(catalog)} objects {counts} -> {jl}, {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
