"""Shared verdict extraction for `experiments/<id>/decision.md` artifacts.

WHY this module exists — a measured coverage failure, not a refactor for its own sake.
`experiments/20260912-cycle2-retrospective-replay/` replayed the repository's own gates
over its own 12 verdict-bearing experiments and found that
`hooks/reject_gate_guard.py`'s verdict detector — a single
`re.search(r"\\[x\\]\\s*REJECT", ...)` — recognised the verdict marker in **1 of 12**
artifacts. A gate documented as enforcing Kill-Analysis completeness since 2026-06-24 had
in practice been inspecting 8% of the corpus and reporting silence about the other 92% —
and silence reads as approval.

The cause is that the corpus is not format-consistent. Four verdict forms are in real use:

    1. `- [x] REJECT — claim falsified`      the _template's own checkbox form
    2. `## Verdict: ARCHIVE (parked) — ...`  heading form
    3. `## Decision: NEEDS-HUMAN (...)`      heading form, different noun
    4. `**STATUS: RESOLVED**`                bold status line

THREE OUTCOMES, KEPT DISTINCT — this is the load-bearing design decision:

    KNOWN          a recognised Falsification-Ladder verdict
    UNKNOWN_TOKEN  verdict-shaped, but not in the vocabulary (e.g. RESOLVED)
    UNPARSEABLE    no verdict form matched at all

An unknown token is NEVER silently normalised into the vocabulary. Collapsing
UNKNOWN_TOKEN into KNOWN would convert the corpus's real heterogeneity into a tidy
falsehood, and collapsing UNPARSEABLE into "no verdict" is precisely the failure that
made the old detector report a clean corpus it had never read. Whether `RESOLVED`,
`NEEDS-HUMAN` or `NEEDS-MORE-DATA` *should* join the vocabulary is an ontology decision
that belongs to the falsification-status semantics work, NOT to this parser.

The canonical vocabulary is the four checkboxes `experiments/_template/decision.md`
actually offers. Note that `NEEDS-MORE-DATA` is NOT among them, despite being used by two
real experiments (including the one that introduced this module's own motivating replay) —
that drift is reported, not silently absorbed.
"""

from __future__ import annotations

import re
from typing import NamedTuple

__all__ = [
    "FL_VERDICTS",
    "KNOWN",
    "UNKNOWN_TOKEN",
    "UNPARSEABLE",
    "VerdictResult",
    "extract_verdict",
    "has_verdict",
]

KNOWN = "KNOWN"
UNKNOWN_TOKEN = "UNKNOWN_TOKEN"
UNPARSEABLE = "UNPARSEABLE"

# The canonical vocabulary: exactly the four checkboxes experiments/_template/decision.md
# offers. Deliberately NOT extended with tokens the corpus happens to use -- see module
# docstring.
FL_VERDICTS = frozenset({"PROMOTE", "REPEAT", "REJECT", "ARCHIVE"})

# WHY each pattern requires an ALL-CAPS token: the template's own "Result Classification"
# section uses checkboxes too (`- [x] 💎 **Diamond**`), and a case-insensitive checkbox
# regex would happily return "Diamond" as the experiment's verdict. Requiring
# [A-Z][A-Z-]{2,} excludes title-case decoration structurally, rather than relying on a
# blocklist that would need updating every time someone adds a new medal emoji.
#
# WHY re.MULTILINE is not optional, recorded because its absence was caught by
# measurement rather than by tests: the first version of this module omitted the flag, so
# `^` anchored to the start of the whole document and the module scored 0/13 on the real
# corpus -- WORSE than the crude detector it replaces. Every single-line unit fixture
# (`extract_verdict("- [x] REJECT")`) would have passed, because in a one-line string the
# document start IS the line start. The regression corpus in tests/ therefore uses
# multi-line documents with the verdict below line 1, on purpose.
_MULTILINE = re.MULTILINE
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "checkbox",
        re.compile(
            r"^[ \t]*-?[ \t]*\[[xX]\][ \t]*\*{0,2}[ \t]*([A-Za-z][A-Za-z\-]{2,})", _MULTILINE
        ),
    ),
    (
        "heading",
        re.compile(
            r"^#+[ \t]*(?:Verdict|Decision)[ \t]*:[ \t]*\*{0,2}([A-Za-z][A-Za-z\-]{2,})", _MULTILINE
        ),
    ),
    (
        "bold_status",
        re.compile(
            r"^[ \t]*\*\*[ \t]*(?:STATUS|Verdict|Final Status)[ \t]*:[ \t]*\*{0,2}"
            r"([A-Za-z][A-Za-z\-]{2,})",
            _MULTILINE,
        ),
    ),
    (
        "plain",
        re.compile(
            r"^[ \t]*(?:Verdict|Final Status)[ \t]*:[ \t]*\*{0,2}([A-Za-z][A-Za-z\-]{2,})",
            _MULTILINE,
        ),
    ),
)

# Belt-and-braces only. The ALL-CAPS requirement above already excludes the template's
# own decoration; these are tokens that ARE all-caps in some real files and are
# unambiguously not verdicts.
_NOISE = frozenset({"PASS", "FAIL", "YES", "NO", "TODO", "TBD", "N", "NA"})


class VerdictResult(NamedTuple):
    """The outcome of trying to read one decision.md's verdict.

    `verdict` is populated ONLY when `outcome == KNOWN`. For UNKNOWN_TOKEN the raw
    `token` is preserved verbatim so a caller can report it without guessing what it
    meant; for UNPARSEABLE both are None.
    """

    outcome: str
    token: str | None = None
    verdict: str | None = None
    form: str | None = None

    @property
    def is_known(self) -> bool:
        return self.outcome == KNOWN


def _normalise(raw: str) -> str:
    return raw.strip().rstrip("-").strip().upper()


def extract_verdict(content: str) -> VerdictResult:
    """Read the verdict of one decision.md.

    Scans for each supported form in order and takes the FIRST verdict-shaped token
    found. In the template's own layout the Verdict section precedes every other
    checkbox section, so first-match is the document's actual verdict; a file that
    checks two different verdict boxes is malformed in a way this function does not
    try to adjudicate.
    """
    for form, pattern in _PATTERNS:
        for m in pattern.finditer(content):
            raw = m.group(1).strip()
            token = _normalise(raw)
            if token in _NOISE:
                continue
            # A vocabulary word counts regardless of casing: `- [X] reject` is
            # unambiguously the REJECT verdict.
            if token in FL_VERDICTS:
                return VerdictResult(KNOWN, token=token, verdict=token, form=form)
            # An OUT-OF-VOCABULARY word counts as verdict-shaped only when written in
            # caps. WHY the asymmetry: the template's Result Classification section uses
            # checkboxes too (`- [x] **Diamond**`, `- [x] **Gold**`), so a
            # case-insensitive rule here would report "Diamond" as an experiment's
            # verdict. Requiring caps for unknown tokens excludes title-case decoration
            # structurally, while the vocabulary branch above keeps lowercase spellings
            # of real verdicts working.
            if raw == raw.upper():
                return VerdictResult(UNKNOWN_TOKEN, token=token, form=form)
    return VerdictResult(UNPARSEABLE)


def has_verdict(content: str, verdict: str) -> bool:
    """True when the document's verdict is exactly `verdict` (a KNOWN one).

    An UNKNOWN_TOKEN never satisfies this: a file whose verdict reads `RESOLVED` is not
    asserting REJECT, and treating it as one would be the silent normalisation this
    module exists to prevent.
    """
    result = extract_verdict(content)
    return result.is_known and result.verdict == verdict.strip().upper()
