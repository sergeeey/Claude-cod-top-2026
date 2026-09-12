"""Tests for hooks/lib/verdicts.py — the shared decision.md verdict extractor.

THE FIXTURES ARE DELIBERATELY MULTI-LINE, with the verdict never on line 1.

That is not stylistic. The first version of `verdicts.py` omitted `re.MULTILINE`, so `^`
anchored to the start of the whole document instead of each line. It scored **0/13** on
the real corpus — worse than the crude detector it replaced — and *every single-line unit
fixture would still have passed*, because in a one-line string the document start IS the
line start. A test suite that cannot distinguish "works" from "works only on my fixture
shape" is not a test suite. Hence: real document shapes, verdict below line 1, plus a
coverage test against the actual repository corpus at the bottom.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from lib.verdicts import (  # noqa: E402
    FL_VERDICTS,
    KNOWN,
    UNKNOWN_TOKEN,
    UNPARSEABLE,
    extract_verdict,
    has_verdict,
)

# --- the four real formats, as whole documents -------------------------------

_CHECKBOX = """# decision.md — 20260101-example

## Verdict

- [ ] PROMOTE — claim holds
- [x] REJECT — claim falsified
- [ ] ARCHIVE — valid but deprioritized

## Evidence Summary
"""

_HEADING_VERDICT = """# decision.md — 20260101-example

## Verdict: ARCHIVE (parked) — shadow-mode calibration stalled at step 6

Some prose about why.
"""

_HEADING_DECISION = """# decision.md — 20260101-example

## Decision: REPEAT (informational — premise needs re-testing)

Some prose.
"""

_BOLD_STATUS = """# decision.md — 20260101-example

**STATUS: PROMOTE**

## Claim
"""


class TestTheFourRealFormats:
    """Each format appears in this repository's own history. See verdicts.py's docstring."""

    def test_checkbox_form(self):
        r = extract_verdict(_CHECKBOX)
        assert r.outcome == KNOWN
        assert r.verdict == "REJECT"
        assert r.form == "checkbox"

    def test_heading_verdict_form(self):
        r = extract_verdict(_HEADING_VERDICT)
        assert r.outcome == KNOWN
        assert r.verdict == "ARCHIVE"
        assert r.form == "heading"

    def test_heading_decision_form(self):
        r = extract_verdict(_HEADING_DECISION)
        assert r.outcome == KNOWN
        assert r.verdict == "REPEAT"

    def test_bold_status_form(self):
        r = extract_verdict(_BOLD_STATUS)
        assert r.outcome == KNOWN
        assert r.verdict == "PROMOTE"
        assert r.form == "bold_status"

    def test_verdict_below_line_one_is_found(self):
        """The re.MULTILINE regression, stated as its own test.

        Without the flag this passes for a one-line string and fails for every real
        document — which is exactly how the bug survived its first implementation."""
        doc = "\n" * 40 + "- [x] PROMOTE — claim holds\n"
        assert extract_verdict(doc).verdict == "PROMOTE"


class TestWhatMustNotMatch:
    def test_unchecked_box_is_not_a_verdict(self):
        doc = "# decision.md\n\n## Verdict\n\n- [ ] PROMOTE — not chosen\n"
        assert extract_verdict(doc).outcome == UNPARSEABLE

    def test_title_case_decoration_is_not_a_verdict(self):
        """The template's Result Classification section uses checkboxes too. A
        case-insensitive rule for unknown tokens would return 'Diamond' as the verdict."""
        doc = (
            "# decision.md\n\n## Result Classification\n\n"
            "- [x] 💎 **Diamond** — unexpected result, valuable outside the original scope\n"
            "- [ ] 🥇 **Gold** — answers the project's main question\n"
        )
        assert extract_verdict(doc).outcome == UNPARSEABLE

    def test_title_case_decoration_without_emoji_is_not_a_verdict(self):
        """The emoji-free variant, which is the one that actually exercises the
        capitalisation rule.

        Mutation testing caught the version above passing for the WRONG reason: the
        emoji sits between `[x]` and `**Diamond**`, so the pattern never matches that
        line at all and the caps check is never reached. Disabling the caps check left
        that test green. This fixture reaches the branch.
        """
        doc = "# decision.md\n\n## Result Classification\n\n- [x] **Diamond** — unexpected\n"
        assert extract_verdict(doc).outcome == UNPARSEABLE

    def test_prose_mentioning_a_verdict_word_is_not_a_verdict(self):
        doc = "# decision.md\n\nWe considered whether to REJECT this, but did not.\n"
        assert extract_verdict(doc).outcome == UNPARSEABLE


class TestUnknownTokensAreNeverNormalised:
    """The load-bearing constraint: an out-of-vocabulary token is reported as itself.

    Silently mapping RESOLVED->PROMOTE (or NEEDS-HUMAN->ARCHIVE) would convert the
    corpus's real heterogeneity into a tidy falsehood. Whether any of these SHOULD join
    the vocabulary is an ontology decision for the falsification-status work, not
    something this parser may decide.
    """

    @pytest.mark.parametrize(
        ("doc", "token"),
        [
            ("# d\n\n**STATUS: RESOLVED**\n", "RESOLVED"),
            ("# d\n\n## Decision: NEEDS-HUMAN (premise was already false)\n", "NEEDS-HUMAN"),
            ("# d\n\n- [x] **NEEDS-MORE-DATA** — infrastructure verified\n", "NEEDS-MORE-DATA"),
        ],
    )
    def test_out_of_vocabulary_token_reported_verbatim(self, doc: str, token: str):
        r = extract_verdict(doc)
        assert r.outcome == UNKNOWN_TOKEN
        assert r.token == token
        assert r.verdict is None, "an unknown token must never be given a canonical verdict"
        assert not r.is_known

    def test_unknown_token_never_satisfies_has_verdict(self):
        doc = "# d\n\n**STATUS: RESOLVED**\n"
        assert not has_verdict(doc, "PROMOTE")
        assert not has_verdict(doc, "REJECT")

    def test_vocabulary_is_exactly_the_template_checkboxes(self):
        """If this fails, someone widened the vocabulary — which is an ontology change
        and must be a deliberate, separately-reviewed decision, not a parser tweak."""
        assert FL_VERDICTS == {"PROMOTE", "REPEAT", "REJECT", "ARCHIVE"}


class TestUnparseable:
    def test_no_verdict_at_all(self):
        assert extract_verdict("# decision.md\n\n## Claim\n\nSome text.\n").outcome == UNPARSEABLE

    def test_two_verdicts_at_different_levels_is_not_guessed(self):
        """Regression fixture from `20260728-hypothesis-arbiter-taxonomy-pilot`, which
        records TWO verdicts at different levels:

            **Filing status: ARCHIVE → `parked/`**
            **Claim-level result: REJECT** (falsified as stated)

        That is not a formatting quirk — the author needed a distinction the four-checkbox
        vocabulary cannot express (where the file goes vs. what happened to the claim).
        The parser must NOT pick one: choosing between them is an ontology decision.
        Reporting UNPARSEABLE here is the correct, honest behaviour, and this fixture
        exists so that a future change which starts guessing fails loudly.
        """
        doc = (
            "# decision.md — example\n\n## Verdict\n\n"
            "**Filing status: ARCHIVE → `parked/`** (corrected after external review)\n\n"
            "**Claim-level result: REJECT** (falsified as stated)\n"
        )
        assert extract_verdict(doc).outcome == UNPARSEABLE


class TestHasVerdict:
    def test_exact_match(self):
        assert has_verdict(_CHECKBOX, "REJECT")
        assert has_verdict(_CHECKBOX, "reject"), "case-insensitive on the query side"

    def test_non_match(self):
        assert not has_verdict(_CHECKBOX, "PROMOTE")


class TestRealCorpusCoverage:
    """The measured claim this module exists to make, asserted against the real corpus.

    This is the test that would have caught the re.MULTILINE bug, and it is deliberately
    phrased as a floor rather than an exact number so that adding a well-formed experiment
    does not break it — but a REGRESSION in coverage will.
    """

    def _corpus(self) -> list[Path]:
        return sorted(
            p for p in REPO_ROOT.glob("experiments/*/decision.md") if p.parent.name != "_template"
        )

    def test_corpus_is_not_empty(self):
        """Guards the guard: if the glob breaks, the coverage assertion below would
        pass vacuously over zero files."""
        assert len(self._corpus()) >= 10

    def test_definite_reading_for_nearly_the_whole_corpus(self):
        """Measured move: the previous checkbox-only detector recognised a verdict in
        1 of 13 files. This asserts the fixed floor, not the aspiration."""
        corpus = self._corpus()
        definite = [
            p
            for p in corpus
            if extract_verdict(p.read_text(encoding="utf-8", errors="replace")).outcome
            in (KNOWN, UNKNOWN_TOKEN)
        ]
        assert len(definite) >= len(corpus) - 1, (
            "coverage regression: at most one artifact in the corpus may be UNPARSEABLE "
            f"(the known two-level-verdict record). Unreadable: "
            f"{[p.parent.name for p in corpus if p not in definite]}"
        )

    def test_no_corpus_artifact_is_silently_normalised(self):
        """Every out-of-vocabulary verdict in the real corpus must surface as
        UNKNOWN_TOKEN with its raw token, never as a canonical verdict."""
        for p in self._corpus():
            r = extract_verdict(p.read_text(encoding="utf-8", errors="replace"))
            if r.outcome == UNKNOWN_TOKEN:
                assert r.token, f"{p.parent.name}: unknown token must be preserved"
                assert r.token not in FL_VERDICTS
