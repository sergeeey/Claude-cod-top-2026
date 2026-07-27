#!/usr/bin/env python3
"""Well-formedness + coverage gate for the RFC-001 claim-type benchmark corpus.

WHY (Sprint 4): tests/corpus/claims/claims.jsonl is the bilingual train/test substrate
RFC-001 would measure the claim pipeline against. This gate does NOT run the pipeline
(that needs claim-decomposer in the LLM loop, a human-in-loop follow-up) -- it only
guarantees the corpus is well-formed and actually spans the taxonomy, so the future
benchmark measures something real rather than a lopsided sample.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
CLAIMS = ROOT / "tests" / "corpus" / "claims" / "claims.jsonl"

VALID_TYPES = {
    "OBSERVATIONAL_FACT",
    "CAUSAL_CLAIM",
    "PREDICTION",
    "SCIENTIFIC_HYPOTHESIS",
    "METRIC_CLAIM",
    "NORMATIVE_CLAIM",
    "PROCEDURAL_CLAIM",
    "ARCHITECTURE_DECISION",
    "AMBIGUOUS",
    "UNVERIFIABLE",
}


def _rows():
    return [json.loads(ln) for ln in CLAIMS.read_text(encoding="utf-8").splitlines() if ln.strip()]


class TestClaimsCorpus:
    def test_rows_are_wellformed(self):
        for r in _rows():
            assert r["text"].strip()
            assert r["lang"] in {"en", "ru"}, f"unexpected lang: {r.get('lang')}"
            assert r["type"] in VALID_TYPES, f"unexpected type: {r.get('type')}"
            assert isinstance(r["verifiable"], bool)
            assert r.get("note"), "every row needs a rationale note"

    def test_corpus_is_bilingual(self):
        langs = {r["lang"] for r in _rows()}
        assert langs == {"en", "ru"}, f"corpus must have both languages, got {langs}"

    def test_every_routable_type_is_represented(self):
        """The 8 routable types must each appear, or the benchmark can't measure
        routing for a type that has no example. AMBIGUOUS/UNVERIFIABLE (abstain
        cases) must also appear -- abstention is the behaviour most worth testing."""
        present = {r["type"] for r in _rows()}
        missing = sorted(VALID_TYPES - present)
        assert not missing, f"claim types with no corpus example: {missing}"

    def test_abstain_cases_are_marked_unverifiable(self):
        for r in _rows():
            if r["type"] in {"AMBIGUOUS", "UNVERIFIABLE", "NORMATIVE_CLAIM"}:
                assert r["verifiable"] is False, (
                    f"{r['type']} row should be verifiable=false (abstain/flag, not route): {r['text'][:40]}"
                )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
