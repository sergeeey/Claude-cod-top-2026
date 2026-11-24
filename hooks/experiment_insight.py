#!/usr/bin/env python3
"""PostToolUse hook: capture experiment outcomes from decision.md writes.

WHY: the reasoning behind an experiment's outcome ("why it didn't work", "why it is
inconclusive") is valuable for OTHER problems and is lost after the session unless it is
captured. This hook intercepts writes to experiments/*/decision.md and:
  1. appends a row to the PROJECT's own null_results/INDEX.md (REJECT-class) or
     parked/INDEX.md (ARCHIVE-class), once per experiment;
  2. writes ONE raw note to ~/.claude/memory/_auto/raw/ for Obsidian import, with
     provenance (project, source decision.md, experiment id, dates) and an explicit
     evidence status.

Triggers on: PostToolUse(Write|Edit) where file_path matches experiments/*/decision*.md

Defects fixed here (each measured in the 2026-11-08 project-interaction audit):
  * the path filter used "/" only, so every Windows path (D:\\p\\experiments\\x\\decision.md)
    was skipped and the hook never fired for any real decision file;
  * the index was looked up next to the HOOK (REPO_ROOT/null_results), which for the
    deployed copy is ~/.claude/null_results -- absent -- so the hook returned silently;
    it is now looked up in the project that owns the decision file;
  * only "[x] REJECT|ARCHIVE" was recognised; verdicts now come from lib.verdicts and a
    closed capture map, and anything outside the map is NOT captured (never guessed);
  * the index row was appended on every edit (duplicates); it is now once per experiment id;
  * the note carried no project identity and three unfilled "[fill in]" sections.

Design note: the machine records what the AUTHOR declared. It never verifies the claim, so
every note says `evidence: UNKNOWN` / `status: auto-captured-not-verified`. A recorded
note is not proof that the classification is right.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lib.runtime import hook_main, parse_stdin
from lib.security import redact_secrets
from lib.state import atomic_write_text, file_lock
from lib.verdicts import KNOWN, UNKNOWN_TOKEN, extract_verdict_earliest

# Recursion guard -- avoid loops inside Agent SDK sub-invocations.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

DRY_RUN = os.environ.get("CLAUDE_DRY_RUN") == "1"

# Test/override hook: when set, this file is used as the null_results index instead of
# discovering one in the project that owns the decision file.
NULL_RESULTS_INDEX: Path | None = None
RAW_DIR = Path.home() / ".claude" / "memory" / "_auto" / "raw"

# Closed capture map: verdict word as written -> outcome class. A word that is not here is
# never captured and never guessed (the owner decides whether the vocabulary grows).
OUTCOME_MAP: dict[str, str] = {
    "REJECT": "NEGATIVE",
    "REJECTED": "NEGATIVE",
    "KILL": "NEGATIVE",
    "KILLED": "NEGATIVE",
    "FALSIFIED": "NEGATIVE",
    "REFUTED": "NEGATIVE",
    "NULL": "NEGATIVE",  # a declared null result: tagged #null-result, never #rejected
    "ARCHIVE": "ARCHIVE",
    "ARCHIVED": "ARCHIVE",
    "PARK": "ARCHIVE",
    "PARKED": "ARCHIVE",
    "REPEAT": "INCONCLUSIVE",
    "INCONCLUSIVE": "INCONCLUSIVE",
    "UNDERPOWERED": "INCONCLUSIVE",
    "UNRESOLVED": "INCONCLUSIVE",
    "NEEDS-HUMAN": "NEEDS_HUMAN",
    "PROMOTE": "POSITIVE",
    "PROMOTED": "POSITIVE",
    "CONFIRMED": "POSITIVE",
}
_TAGS = {
    "NEGATIVE": "#null-result #experiment-insight #rejected",
    "ARCHIVE": "#null-result #experiment-insight #archived",
    "INCONCLUSIVE": "#experiment-insight #inconclusive",
    "NEEDS_HUMAN": "#experiment-insight #needs-human",
    "POSITIVE": "#experiment-insight #promoted",
}

_PATH_RE = re.compile(r"(?:^|/)experiments/([^/]+)/decision[^/]*\.md$", re.IGNORECASE)
_ID_RE = re.compile(r"\*\*Experiment ID:\*\*\s*`?([^`\n]+)`?")
_DATE_RE = re.compile(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})")
# O44 (2026-11-09): the date a decision STATES. Two spellings of the same explicit statement;
# nothing else (file mtime, today, the folder-name prefix) is a decision date.
_DATE_PLAIN_RE = re.compile(r"(?mi)^ {0,3}(?:date|дата)[ \t]*:[ \t]*(\d{4}-\d{2}-\d{2})")
# Words that are not ids even though they look like one (and the unedited template text).
_JUNK_IDS = frozenset({"unknown", "tbd", "todo", "none", "null", "n/a", "na", "n", "-", "?"})
# An explicit id must look like an id (not the template placeholder `<YYYYMMDD-short-slug>`).
_ID_SHAPE_RE = re.compile(r"^[\w][\w.\-]*$")
# Verified folder structure: experiments/<YYYYMMDD-slug>/decision.md (the repo template's id form).
_DIR_ID_RE = re.compile(r"^(\d{8})-[\w][\w.\-]*$")
_TITLE_ID_RE = re.compile(r"\b(\d{8}-[A-Za-z0-9][\w.\-]*)")
_REASONING_RE = re.compile(
    r"##\s+(?:Reasoning|Rationale)\s*\n(.*?)(?=\n##|\n---|\Z)", re.DOTALL | re.IGNORECASE
)
_CHECKED_RE = re.compile(r"\[[xX]\][ \t]*\*{0,2}[ \t]*([A-Za-z][A-Za-z\-]{2,})")
# A correction addendum near the top means the verdict below may have been retracted.
_CORRECTION_RE = re.compile(r"CORRECTION ADDENDUM|SUPERSEDED BY|downgraded|retract", re.IGNORECASE)
_REASONING_LIMIT = 2000
_CONFLICT_HEAD_LINES = 120


def _norm_path(file_path: str) -> str:
    """Forward-slash form of a path (Windows tool paths use backslashes)."""
    return file_path.replace("\\", "/")


def _classify(text: str) -> tuple[str | None, str | None, str]:
    """Return (verdict_word, outcome_class, basis).

    outcome_class is None when the verdict is absent, outside the closed map, ambiguous
    (several different checked boxes) or flagged as corrected. `basis` says why.
    """
    head = "\n".join(text.splitlines()[:40])
    result = extract_verdict_earliest(text)
    if result.outcome in (KNOWN, UNKNOWN_TOKEN):
        word = result.token or ""
    else:
        return None, None, "no-verdict"
    outcome = OUTCOME_MAP.get(word)
    if outcome is None:
        return word, None, "unknown-token"
    checked = {w.upper() for w in _CHECKED_RE.findall(text) if w.upper() in OUTCOME_MAP}
    if len({OUTCOME_MAP[w] for w in checked}) > 1:
        return word, None, "ambiguous-checkboxes"
    if _CORRECTION_RE.search(head):
        return word, None, "corrected-verdict"
    if result.form != "checkbox" and _conflicting_outcomes(text, outcome):
        # A heading/bold/plain verdict can be a sub-verdict (a skeptic section's
        # "**Verdict: CONFIRMED**" inside a REJECTED file). Two outcome classes in the head of
        # the file = not decidable by a regex = not captured. Measured: this flipped 2 real
        # REJECTED files to PROMOTE/CONFIRMED before the check existed.
        return word, None, "conflicting-signals"
    return word, outcome, result.form or "unknown"


def _conflicting_outcomes(text: str, outcome: str) -> bool:
    """True when another outcome class appears as an ALL-CAPS word in the head of the file.

    Unchecked option lines (`- [ ] REJECT`) are ignored: the template lists every option.
    """
    classes = set()
    for line in text.splitlines()[:_CONFLICT_HEAD_LINES]:
        if "[ ]" in line:
            continue
        for tok in re.findall(r"\b[A-Z][A-Z\-]{2,}\b", line):
            cls = OUTCOME_MAP.get(tok.strip("-"))
            if cls:
                classes.add(cls)
    return bool(classes - {outcome})


def _valid_date(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _stated_date_ok(value: str) -> bool:
    """A calendar date that is not in the future (a decision cannot be dated tomorrow+)."""
    if not _valid_date(value):
        return False
    limit = datetime.now(UTC).date() + timedelta(days=1)
    return datetime.fromisoformat(value).date() <= limit


def _header(text: str) -> str:
    """The document header: before the first `##` section, without fenced code or BOM.

    WHY (O44 review, 2026-11-09): an id or a date mentioned inside a code block, a quoted prior
    decision or a later section is narrative, not the statement of THIS decision.
    """
    text = text.lstrip("\ufeff")
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return re.split(r"(?m)^##\s", text, maxsplit=1)[0]


def _resolve_exp_id(text: str, exp_dir: str | None) -> tuple[str | None, str]:
    """(id, source) -- explicit id > verified folder structure > undetermined (None).

    WHY (O44, 2026-11-09): 215 of 215 real decision.md files carry no `**Experiment ID:**` line
    (the repo's own decision.md template has none), so the old fallback id "unknown" was the
    NORMAL case. It disabled the repeat check for index rows (3 saves = 3 rows) and filed
    results under a fake name. A folder `<YYYYMMDD>-<slug>` is the template's id form and is
    accepted only when its date prefix is a real date and the document's own heading does not
    name a DIFFERENT id; anything else stays undetermined rather than guessed.
    """
    text = _header(text)
    id_match = _ID_RE.search(text)
    if id_match:
        explicit = id_match.group(1).strip()
        if (
            _ID_SHAPE_RE.match(explicit)
            and explicit.lower() not in _JUNK_IDS
            and not explicit.upper().startswith("YYYY")
        ):
            return explicit, "explicit"
    if exp_dir:
        dir_match = _DIR_ID_RE.match(exp_dir)
        if dir_match and _valid_date(
            f"{dir_match.group(1)[:4]}-{dir_match.group(1)[4:6]}-{dir_match.group(1)[6:]}"
        ):
            for line in text.splitlines()[:5]:
                if line.lstrip().startswith("#"):
                    named = _TITLE_ID_RE.search(line)
                    if named and named.group(1).rstrip(".-") != exp_dir:
                        return None, "undetermined"  # the document names another id
            return exp_dir, "directory"
    return None, "undetermined"


def _parse_decision(text: str, exp_dir: str | None = None) -> dict:
    """Extract structured fields from decision.md content.

    `exp_dir` is the experiment folder name (evidence for the id when the file states none).
    """
    word, outcome, basis = _classify(text)

    exp_id, id_source = _resolve_exp_id(text, exp_dir)

    date = None
    head = _header(text)
    candidates = [m for m in (_DATE_RE.search(head), _DATE_PLAIN_RE.search(head)) if m]
    for date_match in sorted(candidates, key=lambda m: m.start()):  # first in document order
        if _stated_date_ok(date_match.group(1)):
            date = date_match.group(1)
            break

    reasoning_match = _REASONING_RE.search(text)
    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

    # Derive slug from experiment ID: take part after first dash-separated date
    # e.g. "20260514-prompt-injection" -> "prompt-injection"
    if exp_id is not None:
        slug_match = re.match(r"\d{8}-(.+)", exp_id)
        slug = slug_match.group(1) if slug_match else exp_id
    else:
        slug = exp_dir or "undetermined"  # the real folder name: a locator, not an id

    return {
        "verdict": word,
        "outcome": outcome,
        "basis": basis,
        "exp_id": exp_id,
        "id_source": id_source,
        "date": date,
        "date_source": "decision.md" if date else "not stated",
        "slug": slug,
        "reasoning": reasoning,
    }


def _project_of(file_path: str) -> dict:
    """Identity of the project that owns experiments/<id>/decision.md (no subprocess)."""
    p = Path(_norm_path(file_path))
    exp_dir = p.parent
    project_dir = exp_dir.parent.parent  # <project>/experiments/<id>/decision.md
    git_root = None
    home = Path.home().resolve()
    for cand in (project_dir, *project_dir.parents):
        # The home directory is itself a git repo here: the walk ends AT home, which is
        # never THE project (and nothing above it is one).
        if cand.resolve() == home:
            break
        if (cand / ".git").exists():
            git_root = cand
            break
    return {
        "name": (git_root or project_dir).name,
        "path": project_dir.as_posix(),
        "git_root": git_root,
        "project_dir": project_dir,
        "exp_dir_name": exp_dir.name,
    }


def _find_index(project: dict, name: str) -> Path | None:
    """Nearest <name>/INDEX.md between the project dir and its git root (inclusive)."""
    stop = project["git_root"] or project["project_dir"]
    cand = project["project_dir"]
    while True:
        idx = cand / name / "INDEX.md"
        if idx.exists():
            return idx
        if cand == stop or cand.parent == cand:
            return None
        cand = cand.parent


def _append_index_row(index: Path, row: str, exp_id: str) -> bool:
    """Insert `row` after the last table row of `index`. Idempotent per experiment id.

    The read-modify-write runs under lib.state.file_lock: two experiments finishing in one
    project at the same moment otherwise both read the old table and one row is lost. If the
    lock cannot be taken the row is skipped (the raw note is still written) -- never written
    unlocked, never allowed to hang the hook.
    """
    with file_lock(Path(f"{index}.lock"), timeout=5.0) as acquired:
        if not acquired:
            print(
                f"[experiment-insight] {index.parent.name}/INDEX.md busy: row not added",
                file=sys.stderr,
            )
            return False
        content = index.read_text(encoding="utf-8")
        if re.search(rf"^\|\s*{re.escape(exp_id)}\s*\|", content, re.MULTILINE):
            return False
        lines = content.split("\n")
        # WHY: insert after the LAST table row (starts AND ends with |) so new entries stay
        # inside the table, not after "## How to Add an Entry" sections.
        last = max(
            (
                i
                for i, line in enumerate(lines)
                if line.strip().startswith("|") and line.strip().endswith("|")
            ),
            default=-1,
        )
        if last == -1:
            return False  # malformed index: no table
        if "No entries yet" in lines[last]:
            lines[last] = row
        else:
            lines.insert(last + 1, row)
        atomic_write_text(index, "\n".join(lines))
        return True


def _short_why(reasoning: str) -> str:
    words = reasoning.split()
    return (
        " ".join(words[:10]) + ("…" if len(words) > 10 else "")
    ) or "see decision.md for details"


def _no_row_without_id(index_name: str) -> None:
    """An index row needs a reliable id (also its repeat key); the raw note is still written."""
    print(
        f"[experiment-insight] {index_name}/INDEX.md row skipped: no reliable experiment id "
        "(no **Experiment ID:** line and the folder is not <YYYYMMDD>-<slug>); "
        "the raw insight note is still written",
        file=sys.stderr,
    )


def _update_null_results_index(parsed: dict, project: dict | None = None) -> None:
    """Append one row to the project's null_results/INDEX.md (NEGATIVE outcomes only)."""
    if parsed["outcome"] != "NEGATIVE":
        return
    if parsed["exp_id"] is None:
        _no_row_without_id("null_results")
        return
    row = (
        f"| {parsed['exp_id']} | {parsed['date'] or 'not stated'} | {parsed['slug']} | "
        f"{parsed['verdict']} | {_short_why(parsed['reasoning'])} |"
    )
    if DRY_RUN:
        print(f"[dry-run] would append to null_results/INDEX.md: {row}", file=sys.stderr)
        return
    index = NULL_RESULTS_INDEX or (project and _find_index(project, "null_results"))
    if index and Path(index).exists():
        _append_index_row(Path(index), row, parsed["exp_id"])


def _update_parked_index(parsed: dict, project: dict | None = None) -> None:
    """Append one row to the project's parked/INDEX.md (ARCHIVE outcomes only)."""
    if parsed["outcome"] != "ARCHIVE":
        return
    if parsed["exp_id"] is None:
        _no_row_without_id("parked")
        return
    row = (
        f"| {parsed['exp_id']} | {parsed['date'] or 'not stated'} | {parsed['slug']} | "
        f"{_short_why(parsed['reasoning'])} | not stated (auto-captured; see decision.md) |"
    )
    if DRY_RUN:
        print(f"[dry-run] would append to parked/INDEX.md: {row}", file=sys.stderr)
        return
    index = project and _find_index(project, "parked")
    if index:
        _append_index_row(index, row, parsed["exp_id"])


def _capture_key(project: dict) -> str:
    raw = f"{project['path'].lower()}|{project['exp_dir_name'].lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _create_raw_insight(parsed: dict, project: dict, source: str) -> Path | None:
    """Write ONE raw note per (project, experiment, verdict). Returns the path if written."""
    outcome = parsed["outcome"]
    verdict = parsed["verdict"]
    slug = parsed["slug"]
    key = _capture_key(project)
    reasoning = redact_secrets(
        parsed["reasoning"] or "[reasoning section not found in decision.md]"
    )
    if len(reasoning) > _REASONING_LIMIT:
        reasoning = reasoning[:_REASONING_LIMIT] + " […обрезано]"
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    safe_slug = re.sub(r"[^\w\-]", "_", slug)[:50]
    safe_verdict = re.sub(r"[^\w\-]", "_", verdict)
    date_part = parsed["date"] or "undated"  # never today's date: it was not stated
    dest = RAW_DIR / f"{date_part}-{safe_slug}-{key}-{safe_verdict}-insight.md"

    # WHY processed/ too: raw_to_wiki moves a converted note to raw/processed/. Looking only at
    # raw/ made a repeated edit of decision.md re-create the note after conversion (a duplicate
    # that then stuck in raw/ forever, because moving it onto the existing processed/ file fails).
    prior = sorted(
        {
            p.name
            for folder in (RAW_DIR, RAW_DIR / "processed")
            if folder.exists()
            for p in folder.glob(f"*-{key}-*-insight.md")
        }
    )
    if dest.name in prior:
        return None  # idempotent: same experiment, same verdict
    supersedes = [n for n in prior if n != dest.name]
    note_type = "negative-result" if outcome in ("NEGATIVE", "ARCHIVE") else "experiment-outcome"
    tags = _TAGS[outcome]
    if outcome == "NEGATIVE" and verdict == "NULL":
        tags = tags.replace(" #rejected", "")  # a null result is not a rejection

    front = [
        "---",
        f'title: "Инсайт: {slug}"',
        f"type: {note_type}",
        f"source: {source}",
        f"project: {project['name']}",
        f"project_path: {project['path']}",
        f"experiment_id: {parsed['exp_id'] or 'undetermined'}",
        f"experiment_id_source: {parsed['id_source']}",
        f"experiment_dir: {project['exp_dir_name']}",
        f"decision_date: {parsed['date'] or 'not stated'}",
        f"captured_at: {today}",
        f"verdict_as_written: {verdict}",
        f"outcome: {outcome}",
        f"verdict_basis: {parsed['basis']}",
        "evidence: UNKNOWN",
        "evidence_scope: none",
        "status: auto-captured-not-verified",
        f"capture_key: {key}",
    ]
    if supersedes:
        front.append("supersedes: [" + ", ".join(supersedes) + "]")
    front.append("---")

    note = (
        "\n".join(front)
        + f"""

# Инсайт: {slug}

{tags} #{slug.replace("-", "_")}

**Эксперимент:** `{parsed["exp_id"] or "id не определён"}` (источник id: {parsed["id_source"]}; \
папка: `{project["exp_dir_name"]}`)
**Проект:** {project["name"]} (`{project["path"]}`)
**Вердикт автора:** {verdict} -> класс {outcome}
**Дата решения:** {parsed["date"] or "не указана в decision.md"}
**Источник:** `{source}`
**Статус:** автозахват со слов автора decision.md; не проверен, не подтверждён.

## Обоснование (из decision.md)

{reasoning}

## Не извлекалось автоматически

Механизм и область применимости в этой заметке не заполнялись. Первоисточник: decision.md.
"""
    )

    if DRY_RUN:
        print(f"[dry-run] would write raw insight: {dest}", file=sys.stderr)
        return None
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # pid-suffixed: two simultaneous captures of one experiment must not share a temp file
    tmp = dest.with_name(f"{dest.name}.tmp.{os.getpid()}")
    tmp.write_text(note, encoding="utf-8")
    os.replace(tmp, dest)
    print(f"[experiment-insight] raw note created: {dest.name}", file=sys.stderr)
    return dest


def main() -> None:
    data = parse_stdin()
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only act on experiments/*/decision*.md (Windows backslash paths included)
    if not _PATH_RE.search(_norm_path(file_path)):
        return

    # Read the written content (from stdin payload or from disk)
    content = tool_input.get("content", "")
    if not content:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, ValueError):  # unreadable, or not valid UTF-8
            return

    parsed = _parse_decision(content, Path(_norm_path(file_path)).parent.name)
    if parsed["outcome"] is None:
        if parsed["basis"] != "no-verdict":
            print(
                f"[experiment-insight] not captured ({parsed['basis']}: {parsed['verdict']})",
                file=sys.stderr,
            )
        return

    project = _project_of(file_path)
    _update_null_results_index(parsed, project)
    _update_parked_index(parsed, project)
    _create_raw_insight(parsed, project, _norm_path(file_path))


if __name__ == "__main__":
    hook_main(main)
