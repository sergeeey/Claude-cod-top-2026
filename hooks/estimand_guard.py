#!/usr/bin/env python3
"""SessionStart hook: warn when a project has an estimand/claim but key fields
(MCID, ICE strategy) are unfilled — so the design layer can actually be enforced.

WHY: estimand.md can sit in the repo with MCID/ICE left as template placeholders.
Then Skeptic and go/no-go run on generic triggers and the careful design is never
enforced (the 'design ↔ verification' gap). This cheap guard nudges: if you have
an estimand, finish MCID + ICE, then run /estimand-bridge to wire it into Skeptic.

Only fires when estimand/claim files exist — silent for non-research projects.
Stdlib only.
"""

import re
import sys
from pathlib import Path

PLACEHOLDER_MARKERS = ("[value", "[description", "[ice", "tbd", "todo", "xxx", "[variable", "...")

_BRACKET_PLACEHOLDER_RE = re.compile(r"\[[^\]]*\]")


def find_estimands(root: Path) -> list[Path]:
    try:
        return [p for p in root.glob("**/estimand.md") if "_template" not in str(p)]
    except (OSError, ValueError):
        return []


def field_unfilled(text: str, label: str) -> bool:
    """True if the VALUE line for `label` (e.g. 'MCID: ...') is missing or a placeholder.

    WHY: anchor on the value assignment 'label:' not the heading — the heading
    '### MCID (Minimum...)' is not where the value lives, and a fixed-width window
    from it misses the real '[value]' placeholder a few lines down.
    """
    target = label.lower() + ":"
    for raw in text.splitlines():
        line = raw.strip().lower()
        # match 'mcid:' but skip markdown headings like '### mcid (...)'
        if line.startswith("#"):
            continue
        if line.startswith(target) or (target in line and line.index(target) < 4):
            value = line.split(":", 1)[1].strip()
            if not value:
                return True
            return any(m in value for m in PLACEHOLDER_MARKERS)
    return True  # no value line found at all


def _has_filled_ice_table(text: str) -> bool:
    """True if an 'Intercurrent Event(s)' section contains a markdown table
    with at least one real (non-placeholder) data row.

    WHY: the actual estimand.md template (experiments/_template/estimand.md)
    documents ICE as a table under a '## Intercurrent Events (ICE)' heading,
    not a flat 'ICE: value' line. field_unfilled()'s flat-line check never
    matches this shape, so every real experiment following the template's own
    documented format was flagged as "unfilled" even when fully written —
    found 2026-07-29 when 2 of 2 files checked already had a complete table.
    """
    lower_text = text.lower()
    idx = lower_text.find("intercurrent event")
    if idx == -1:
        return False
    section = text[idx:]
    next_heading = section.find("\n## ", 1)
    if next_heading != -1:
        section = section[:next_heading]

    pipe_rows = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if not pipe_rows:
        return False
    # First pipe row is the header; drop it, then drop the '|---|---|' separator row(s).
    body_rows = [r for r in pipe_rows[1:] if not set(r.replace("|", "").replace(" ", "")) <= {"-"}]
    for row in body_rows:
        if _BRACKET_PLACEHOLDER_RE.search(row):
            continue  # template's own unfilled "[event name]" / "[why this strategy]" cells
        if any(m in row.lower() for m in PLACEHOLDER_MARKERS):
            continue
        return True
    return False


def _has_filled_prose_section(text: str, heading_needle: str, min_chars: int = 20) -> bool:
    """True if a markdown heading containing `heading_needle` is followed by
    real prose (written paragraphs) before the next heading -- a THIRD shape
    neither field_unfilled()'s flat-line scan nor _has_filled_ice_table()'s
    table-row scan detects.

    WHY (2026-09-01, found dogfooding /estimand-bridge on a real, fully-
    written estimand.md): same root cause as _has_filled_ice_table's own
    2026-07-29 fix, one format wider. A real MCID/ICE section can be written
    as a heading followed by plain paragraphs -- e.g. "## MCID (minimum
    practically important difference)\n\nArm B includes an explicit
    Artifact-class candidate AND Arm A does not." -- which is neither a flat
    'label: value' line nor a markdown table. field_unfilled() reaches end-
    of-file and returns True (line 48's "no value line found" fallback);
    _has_filled_ice_table() finds zero pipe rows and returns False. Both
    flagged a fully-written section as unfilled on
    experiments/20260728-hypothesis-arbiter-taxonomy-pilot/estimand.md,
    confirmed by direct read of the file.
    """
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("#") and heading_needle.lower() in stripped.lower():
            idx = text.index(raw)
            section = text[idx + len(raw) :]
            next_heading = section.find("\n#")
            if next_heading != -1:
                section = section[:next_heading]
            # WHY (2026-09-01, regression caught by
            # test_table_with_only_placeholder_row_still_warns): a markdown
            # table's header/separator/data row all count as "text" once
            # bracket-placeholders are stripped -- a header cell like
            # "Strategy" or a non-placeholder data cell like
            # "treatment-policy" is real text but is NOT prose, and a table
            # with only a placeholder data row must still be flagged
            # unfilled. Table shape is _has_filled_ice_table's job; drop any
            # line that looks like a table row here so this function only
            # ever credits genuine written paragraphs.
            prose_lines = [
                line for line in section.splitlines() if not line.strip().startswith("|")
            ]
            body = _BRACKET_PLACEHOLDER_RE.sub("", "\n".join(prose_lines))
            for marker in PLACEHOLDER_MARKERS:
                body = re.sub(re.escape(marker), "", body, flags=re.IGNORECASE)
            return len(body.strip()) >= min_chars
    return False


def _has_ice_pointer(text: str) -> bool:
    """True if the estimand explicitly points to another file's ICE table
    instead of duplicating it inline — a deliberate, documented pattern in
    this repo (e.g. 20260727-config-effectiveness-opportunistic/estimand.md:
    "See claim.md ICE table (...)" rather than repeating claim.md's content).

    Scoped to a single line containing all three markers together, not a
    whole-document scan — an unrelated "see X.md" elsewhere in a long
    estimand must not silently suppress a genuinely missing ICE section.
    """
    for raw in text.splitlines():
        line = raw.strip().lower()
        if "ice" in line and ".md" in line and ("see" in line or "table" in line):
            return True
    return False


def main() -> None:
    try:
        root = Path.cwd()
        if root == Path.home():
            # WHY (2026-08-09, found via boyko-scientific-consortium dogfood run):
            # a session with cwd == home directory made this hook's unbounded
            # root.glob("**/estimand.md") walk 66k+ dirs / 340k+ files (+ possible
            # OneDrive placeholder round-trips under ~/OneDrive) — measured hangs
            # up to the ~600s hook timeout ceiling. Home dir is never a real
            # project for this guard's purpose; skip the walk entirely.
            return
        estimands = find_estimands(root)
        # Also flag the case: claim.md exists but no estimand at all.
        has_claim = next(root.glob("**/claim.md"), None) is not None
        if not estimands:
            if has_claim:
                print(
                    "[estimand-guard] Found claim.md but no estimand.md — define the estimand "
                    "first (population/endpoint/MCID/ICE), else Skeptic can't enforce criteria."
                )
            return
        issues = []
        for est in estimands:
            try:
                text = est.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            missing = []
            # WHY also check _has_filled_prose_section (found 2026-09-01,
            # dogfooding /estimand-bridge): field_unfilled()'s flat-line scan
            # misses a heading followed by written paragraphs -- a third
            # real, filled shape alongside the flat-line and table shapes
            # already handled below. See that function's own docstring for
            # the exact real file this was found on.
            if field_unfilled(text, "MCID") and not _has_filled_prose_section(text, "mcid"):
                missing.append("MCID (significance threshold)")
            # WHY (Codex review): a bare `"strategy" in text` check was a false
            # negative — any heading like "## Strategy notes" suppressed the ICE
            # warning even with ICE: empty. Check the ICE field itself, allowing
            # either label form ("ICE:" or "ICE strategy:").
            # WHY also check _has_filled_ice_table / _has_ice_pointer (found
            # 2026-07-29): the flat-line checks above never match this repo's
            # own actual template format (a table under "## Intercurrent
            # Events (ICE)") or a deliberate cross-reference to another
            # file's table -- both are real, filled ICE strategies that the
            # original flat-line-only check flagged as missing.
            if (
                field_unfilled(text, "ICE")
                and field_unfilled(text, "ICE strategy")
                and not _has_filled_ice_table(text)
                and not _has_ice_pointer(text)
                and not _has_filled_prose_section(text, "ice")
            ):
                missing.append("ICE strategy")
            if missing:
                issues.append(f"{est.parent.name}: {', '.join(missing)}")
        if issues:
            print(
                "[estimand-guard] estimand.md present but key fields unfilled — "
                "Skeptic/go-no-go can't enforce them yet:\n  "
                + "\n  ".join(issues)
                + "\n  → fill them, then run /estimand-bridge to wire MCID/ICE into Skeptic."
            )
    except Exception as e:  # never block session start
        print(f"[estimand-guard] skipped ({type(e).__name__})", file=sys.stderr)


if __name__ == "__main__":
    main()
