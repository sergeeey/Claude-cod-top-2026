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
import hashlib
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

# Fallback formats, consulted ONLY when the chain above finds nothing, so a file that already
# parses never changes. Calibration (2026-11-04, 54 hand-labelled decision files whose catalog
# verdict was UNKNOWN): the 40-character cap above rejected every long free-form verdict
# ("PASS_..._NARROW_..."), because the cap plus a trailing word boundary cannot end a longer token.
# The same-line heading form ("## Decision: **GO** -> ...") and "## Result" followed by a bold
# token were also missed. A bare "**Status:**" label is NOT included on purpose: a status
# (DRAFT, EXPLORATORY) is not a verdict and an id such as OB1 is not either.
_FALLBACK_LONG = r"([A-Z][A-Z0-9_./-]{1,400})(?![A-Za-z0-9_])"
_FALLBACK = (
    re.compile(
        r"^#{2,4}[ \t]*(?i:verdict|decision|вердикт|решение)\b[^\n]*\n+[\s>*`_-]*" + _FALLBACK_LONG,
        re.MULTILINE,
    ),
    re.compile(
        # [ \t] not \s in the prefix: \s would let every line start rescan a whole run of blank
        # lines (quadratic on a text of thousands of empty lines).
        r"^[ \t#*>-]*(?i:verdict|вердикт)\b[^\n]{0,6}?[:—]+[*\s`]*" + _FALLBACK_LONG,
        re.MULTILINE,
    ),
    re.compile(
        r"^#{2,4}[ \t]*(?i:verdict|decision|вердикт|решение)\b[ \t]*:[ \t]*[*`_]*" + _FALLBACK_LONG,
        re.MULTILINE,
    ),
    re.compile(
        r"^#{2,4}[ \t]*(?i:result)s?\b[^\n]*\n+[ \t]*\*\*"
        # An underscore is required: long free-form verdicts have one, a bare status (DRAFT) or
        # an id (OB12, EXP1) does not, and neither is a verdict.
        r"([A-Z][A-Z0-9]*_[A-Z0-9_./-]{2,400})(?![A-Za-z0-9_])",
        re.MULTILINE,
    ),
)

# A decision file may carry a CORRECTION ADDENDUM near the top that downgrades its own earlier
# verdict while keeping the original text below it. The corrected value governs; reading the
# first checked/labelled verdict would catalog the retracted one (a CONFIRMED that the file
# itself had changed to FALSIFIED). Only the header region counts: a downgrade of some OTHER
# study quoted deep in the body is not a correction of this file.
_CORRECTION_HEAD_LINES = 40
_CORRECTION_MARK = re.compile(
    r"CORRECTION ADDENDUM|SUPERSEDED BY|"
    r"(?i:verdict)[^\n]{0,30}(?i:downgrad|revis|withdrawn|retract)"
)
# Same token alphabet as the free-form verdict parsers (digits, dots, slashes), and a complete
# token only: the lookahead rejects a prefix of a longer word instead of publishing it.
_TOK = r"[A-Z][A-Z0-9_./-]{1,40}(?![A-Za-z0-9_./-])"
_CORRECTED_TO = re.compile(
    rf"(?i:downgraded|revised)\s+(?:(?i:from)\s+)?[*`\"]*({_TOK})[*`\"]*\s*"
    rf"(?:→|->|(?i:to))\s*[*`\"]*({_TOK})"
)


def _correction_head(text: str) -> str:
    return "\n".join(text.splitlines()[:_CORRECTION_HEAD_LINES])


def has_correction(text: str) -> bool:
    """True when the file's own header says its verdict was corrected after the fact."""
    return bool(_CORRECTION_MARK.search(_correction_head(text)))


def _corrected_verdict(text: str) -> str | None:
    head = _correction_head(text)
    if not _CORRECTION_MARK.search(head):
        return None
    m = _CORRECTED_TO.search(head)
    return m.group(2).upper().strip("._-") if m else None


def parse_verdict(text: str) -> str:
    """Verdict word of a decision file.

    1. A checked box (`[x] REJECT`) is explicit and wins.
    2. Otherwise the EARLIEST of: labelled known verdict, free-form value under a 'Verdict'
       heading, free-form value after a 'Verdict:' label. A decision file states its own verdict
       first and may quote other experiments' verdicts further down, so a later
       'Verdict: CONFIRMED' reference must not override this file's own 'Verdict: WEAKENED'.
    Free-form verdicts are common (CANONICAL_PROXY_ONLY); they are returned upper-cased, as
    written, never mapped. Nothing recognised -> UNKNOWN.

    0. An explicit correction in the file's header ("downgraded CONFIRMED -> FALSIFIED") wins over
       everything below it. A correction that names no new verdict word is flagged by
       has_correction() and leaves the verdict as parsed: nothing explicit is guessed.
    """
    corrected = _corrected_verdict(text)
    if corrected:
        return corrected
    for rx in (_CHECKED, _CHECKED_ANY):
        m = rx.search(text)
        if m:
            return m.group(1).upper()
    best: tuple[int, str] | None = None
    for rx in (_LABELLED, _HEADING_VALUE, _LABEL_VALUE):
        m = rx.search(text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), m.group(1).upper().strip("._-"))
    if best is None:
        for rx in _FALLBACK:
            m = rx.search(text)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), m.group(1).upper().strip("._-"))
    if best is None:
        closed = _closed_vocab_verdict(text)
        if closed:
            return closed
    return best[1] if best else "UNKNOWN"


# --- Last-resort tier (2026-11): closed-vocabulary outcome words -------------------------
# Calibration: 119 decision files labelled independently by reading (not by this parser);
# the rules were tuned on the first half and measured on the second. Only a closed set of
# outcome words is accepted, so a bare status (DRAFT) or an id (OB1) never becomes a verdict.
# Consulted ONLY when every tier above found nothing: a file that already parses is unchanged.
_OUT_WORDS = (
    r"KILLED|KILL|REJECTED|REJECT|FALSIFIED|REFUTED|NOT[_ -]REPLICATED|FAIL|CONFIRMED|"
    r"PROMOTED|PROMOTE|"
    r"PASS|INCONCLUSIVE|UNDERPOWERED|UNRESOLVED|BLOCKED|NEEDS[-_ ]HUMAN|ARCHIVED|PARKED"
)
_CLOSED_TIERS = (
    # "Pre-registered primary criterion: **CONFIRMED**", "Contract outcome: **BLOCKED**",
    # "Status: KILL (H1a)", "decision: UNDERPOWERED", "Вердикт по заранее записанному правилу: FAIL"
    re.compile(
        r"^[ \t#*>-]*(?i:[^\n]{0,60}?(?:criterion|prediction|rule|outcome|decision|status|"
        r"result|verdict|критерий|правил\w*|вердикт|итог|результат|статус))"
        r"[^\n]{0,40}?[:—][\s*`_]*(" + _OUT_WORDS + r")\b",
        re.MULTILINE,
    ),
    # "H1e KILLED", "H1a KILLED by pre-registered criterion" (id with a digit, then the word)
    re.compile(
        r"^[ \t#*>-]*[A-Za-z]{1,4}[-_]?\d[\w.-]{0,10}[ \t]+\**(" + _OUT_WORDS + r")\b", re.MULTILINE
    ),
    # "The pre-registered prediction is CONFIRMED", "The claim is FALSIFIED as stated"
    re.compile(
        r"(?i:\b(?:prediction|claim|hypothesis|criterion|rule)\s+is\s+)[*`_]*("
        + _OUT_WORDS
        + r")\b"
    ),
)
_CLOSED_HEAD_LINES = 120


def _closed_vocab_verdict(text: str) -> str | None:
    head = "\n".join(text.splitlines()[:_CLOSED_HEAD_LINES])
    best: tuple[int, str] | None = None
    for rx in _CLOSED_TIERS:
        m = rx.search(head)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), m.group(1).upper().replace(" ", "_").replace("-", "_"))
    return best[1] if best else None


# Normalised outcome class of a verdict word (the verdict stays as written). Free-form tokens
# are mapped only when they contain a known stem; anything else is OTHER, never guessed.
_NEG = re.compile(r"REJECT|KILL|FALSIF|REFUT|NOT[_-]?REPLICATED|NULL|FAIL|DEAD|NEGATIVE")
_POS = re.compile(r"PROMOTE|CONFIRM|PASS|SUCCESS|SUPPORT|SURVIV|ROBUST|POSITIVE")
_INC = re.compile(r"INCONCLUSIVE|UNDERPOWERED|UNRESOLVED|MARGINAL|WEAK|ILL[_-]?POSED|INCOMPLETE")


def outcome_class(verdict: str) -> str:
    """NEGATIVE|POSITIVE|INCONCLUSIVE|NEEDS_HUMAN|ARCHIVE_PARK|BLOCKED|MIXED|OTHER|UNKNOWN."""
    v = (verdict or "").upper()
    if v in ("", "UNKNOWN"):
        return "UNKNOWN"
    if v.startswith("NEEDS"):
        return "NEEDS_HUMAN"
    if "BLOCK" in v:
        return "BLOCKED"
    if v.startswith(("ARCHIV", "PARK")):
        return "ARCHIVE_PARK"
    neg, pos, inc = bool(_NEG.search(v)), bool(_POS.search(v)), bool(_INC.search(v))
    if neg and pos:
        return "MIXED"
    if neg:
        return "NEGATIVE"
    if pos:
        return "POSITIVE"
    if inc:
        return "INCONCLUSIVE"
    return "OTHER"


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


_REPO_KEY_CACHE: dict[str, str] = {}


def _repo_key(path: Path) -> str:
    cached = _REPO_KEY_CACHE.get(str(path))
    if cached is None:
        cached = _REPO_KEY_CACHE[str(path)] = _repo_key_uncached(path)
    return cached


def _repo_key_uncached(path: Path) -> str:
    """Stable repository identity: normalised remote URL; else the shared git dir (worktrees agree).

    WHY: the folder name alone is not an identity. Two repositories can hold different studies
    under the same `experiments/<name>` folder; a worktree of one repo must NOT look like another.
    """
    url = _git(path, "config", "--get", "remote.origin.url")
    if url and url.strip():
        u = re.sub(r"^[A-Za-z+]+://[^@/]*@", "", url.strip())  # drop credentials
        u = re.sub(r"^git@([^:]+):", r"\1/", u)
        u = re.sub(r"^[A-Za-z+]+://", "", u)
        return "url:" + re.sub(r"\.git$", "", u).rstrip("/").lower()
    common = _git(path, "rev-parse", "--git-common-dir")
    if common and common.strip():
        return "git:" + os.path.normcase(str((path / common.strip()).resolve()))
    return "fs:" + os.path.normcase(str(path.resolve().parent))


def _content_hash(text: str) -> str:
    """Hash of the normalised decision text; "" for near-empty files (templates must not match)."""
    norm = "\n".join(ln.rstrip() for ln in text.replace("\r\n", "\n").strip().splitlines())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16] if len(norm) >= 200 else ""


def _uid(repo_key: str, rel: str) -> str:
    return hashlib.sha1(f"{repo_key}|{rel.casefold()}".encode()).hexdigest()[:12]


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
    rkey = _repo_key(repo if repo is not None else exp.parent)
    rel_id = rel if rel else os.path.normcase(str(exp.resolve())).replace(os.sep, "/")
    return {
        "research_id": exp.name,
        "kind": "experiment",
        "state": state,
        "verdict": parse_verdict(text),
        "outcome": outcome_class(parse_verdict(text)),
        "has_correction": has_correction(text),
        "title": title,
        "summary": summary,
        "date": exp.name[:8] if exp.name[:8].isdigit() else "",
        "repo": str(repo) if repo else "",
        "canonical_path": str(exp),
        "aliases": [],
        "uid": _uid(rkey, rel_id),
        "repo_key": rkey,
        "rel_path": rel_id,
        "content_hash": _content_hash(text),
    }


def _first_decision(exp: Path) -> str:
    for f in sorted(exp.glob("decision*.md")):
        return f.name
    return "decision.md"


def _branch_only_records(repo: Path, known: dict[str, list[tuple[str, str]]]) -> list[dict]:
    """Experiments that exist only on a branch. `known` maps lower-case name -> [(uid, hash)].

    A branch copy is skipped when it is the SAME experiment (same uid) or an EXACT copy (same
    hash) of one already known; a different study that merely shares the folder name is kept.
    """
    out: list[dict] = []
    rkey = _repo_key(repo)
    refs = _git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    rx = re.compile(r"(?:^|/)experiments/([^/]+)/(decision[^/]*\.md)$", re.IGNORECASE)
    for branch in (refs or "").split():
        files = _git(repo, "ls-tree", "-r", "--name-only", branch, timeout=40)
        for path in (files or "").splitlines():
            m = rx.search(path)
            if not m or FIXTURE.match(m.group(1)):
                continue
            rel_dir = path.rsplit("/", 1)[0]
            uid = _uid(rkey, rel_dir)
            seen = known.setdefault(m.group(1).lower(), [])
            if any(u == uid for u, _h in seen):
                continue  # the same study is already known: no need to read this branch copy
            text = _git(repo, "show", f"{branch}:{path}") or ""
            chash = _content_hash(text)
            if chash and any(h == chash for _u, h in seen):
                continue  # an exact copy of a known study
            collided = bool(seen)
            seen.append((uid, chash))
            first = next(
                (ln.strip("# ").strip() for ln in text.splitlines() if ln.startswith("#")), ""
            )
            out.append(
                {
                    "research_id": m.group(1),
                    "kind": "experiment",
                    "state": "COMMITTED_BRANCH",
                    "verdict": parse_verdict(text),
                    "outcome": outcome_class(parse_verdict(text)),
                    "has_correction": has_correction(text),
                    "title": first[:140] or m.group(1),
                    "summary": "",
                    "date": m.group(1)[:8] if m.group(1)[:8].isdigit() else "",
                    "repo": str(repo),
                    "canonical_path": f"git:{branch}:{path.rsplit('/', 1)[0]}",
                    "aliases": [],
                    "uid": uid,
                    "repo_key": rkey,
                    "rel_path": rel_dir,
                    "content_hash": chash,
                    **({"id_collision_of": m.group(1)} if collided else {}),
                }
            )
            if collided:
                out[-1]["research_id"] = f"{m.group(1)}~{uid[:6]}"
    return out


def _resolve_name_group(recs: list[dict]) -> list[dict]:
    """Records sharing a folder name -> one catalog row per DISTINCT study.

    Same uid (repo + path) is one study seen in several worktrees/branches: best location wins and
    the rest become aliases (unchanged behaviour). Different uid but identical decision text is an
    exact copy: merged, its path kept in aliases and its uid in copy_uids. Everything else is a
    different study that happens to share the name: it keeps its own row, with `~<uid6>` appended
    to research_id (the first row keeps the plain name, so existing ids and links do not move).
    """
    clusters: dict[str, list[dict]] = {}
    for r in recs:
        clusters.setdefault(r["uid"], []).append(r)
    bests: list[dict] = []
    for members in clusters.values():
        members.sort(key=lambda r: (_STATE_RANK[r["state"]], r["canonical_path"]))
        best = members[0]
        best["aliases"] = [m["canonical_path"] for m in members[1:]]
        bests.append(best)
    bests.sort(key=lambda r: (_STATE_RANK[r["state"]], r["canonical_path"]))
    rows: list[dict] = []
    for b in bests:
        twin = next(
            (o for o in rows if b["content_hash"] and o["content_hash"] == b["content_hash"]),
            None,
        )
        if twin is not None:
            twin["aliases"] += [b["canonical_path"], *b["aliases"]]
            twin.setdefault("copy_uids", []).append(b["uid"])
            continue
        rows.append(b)
    base = rows[0]["research_id"] if rows else ""
    for r in rows[1:]:
        r["id_collision_of"] = base
        if r["title"] and r["title"] == rows[0]["title"]:
            r["possible_variant_of"] = base  # same title, different text: a human decides
        r["research_id"] = f"{base}~{r['uid'][:6]}"
    return rows


def _flag_exact_duplicates(catalog: list[dict]) -> None:
    """Rows under DIFFERENT names with identical decision text: keep both, mark the later."""
    groups: dict[str, list[dict]] = {}
    for r in catalog:
        if r.get("content_hash"):
            groups.setdefault(r["content_hash"], []).append(r)
    for rows in groups.values():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda r: (_STATE_RANK[r["state"]], r["date"] or "0", r["research_id"]))
        for r in rows[1:]:
            r["duplicate_of"] = rows[0]["research_id"]


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
        catalog.extend(_resolve_name_group(recs))

    # Repos to inspect for branch-only experiments: those that hold a found folder, plus the
    # repo (and every worktree's repo) of each root, so a repo with nothing on disk still counts.
    repos = {r for r in toplevels.values() if r is not None}
    for root in roots:
        top = _git(root, "rev-parse", "--show-toplevel") if root.is_dir() else None
        if top:
            repos.add(Path(top.strip()))
    known = {n: [(r["uid"], r["content_hash"]) for r in rs] for n, rs in by_name.items()}
    for repo in sorted(repos):
        catalog.extend(_branch_only_records(repo, known))
    _flag_exact_duplicates(catalog)
    catalog.sort(key=lambda r: (r["date"] or "0", r["research_id"]))
    return catalog


def write(catalog: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    jl, md = out_dir / "RESEARCH_CATALOG.jsonl", out_dir / "RESEARCH_CATALOG.md"
    jl_tmp = jl.with_name(jl.name + ".tmp")
    try:
        with jl_tmp.open("w", encoding="utf-8", newline="\n") as f:
            for rec in catalog:
                f.write(json.dumps({**rec, "generated_at": stamp}, ensure_ascii=False) + "\n")
        os.replace(jl_tmp, jl)  # a crash mid-write leaves the previous catalog intact
    except BaseException:
        jl_tmp.unlink(missing_ok=True)
        raise
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
        "| id | state | verdict | outcome | title | summary | where |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in catalog:
        title = r["title"].replace("|", "/")
        summary = r["summary"].replace("|", "/")[:240]
        verdict = r["verdict"] + (" (corrected)" if r.get("has_correction") else "")
        outcome = r.get("outcome") or outcome_class(r["verdict"])
        if outcome in ("UNKNOWN", "OTHER", "MIXED"):
            outcome += " (read the decision file)"
        row = [r["research_id"], r["state"], verdict, outcome, title, summary, r["canonical_path"]]
        lines.append("| " + " | ".join(row) + " |")
    md_tmp = md.with_name(md.name + ".tmp")
    md_tmp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.replace(md_tmp, md)
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
