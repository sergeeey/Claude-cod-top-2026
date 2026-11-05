"""Skill Audit 2.1 №2: v1 (current) vs v2 (citation-based) critical predicate.

Labels are the author's own, on 10 hand-written cases. This is a PRELIMINARY comparison
(n=10), not a benchmark. Measured result: v2 removes one false alarm (c06, a real DOI
citation) and changes no critical case; the T1+T2 conjunction misses most author-labelled
critical cases in both versions (see c03/c04/c07/c08/c10). Adoption of v2 needs a larger
labelled set and a T1 fix, not only the citation check.
"""

import importlib.util
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "skeptic_auto_trigger.py"

# (id, tool, text, label) -- label True = should be CRITICAL (no real-data citation)
CASES = [
    (
        "c01-plain-perfect",
        "Agent",
        "All 10 niches passed. F1=1.000 across all evaluation sets.",
        True,
    ),
    (
        "c02-tagged-with-url",
        "Agent",
        "All 10 niches passed. F1=1.000 on the held-out set. [VERIFIED-REAL] "
        "dataset: https://data.example.org/corpus.csv",
        False,
    ),
    (
        "c03-logs-mentioned-not-cited",
        "Agent",
        "All tests passed and F1=1.000. Production logs are in the appendix, section 7.",
        True,
    ),
    (
        "c04-external-word-no-link",
        "Agent",
        "Results: F1=1.000 on the synthetic cases only; an external dataset exists elsewhere.",
        True,
    ),
    (
        "c05-bash-pytest-output",
        "Bash",
        "2475 passed in 40s. F1=0.912 on the holdout corpus at https://s3.example/holdout.parquet",
        False,
    ),
    (
        "c06-real-corpus-doi",
        "Agent",
        "All 12 checks passed, zero failures, F1=1.000 on corpus doi:10.1234/abcd.5678.",
        False,
    ),
    (
        "c07-fixtures-precision",
        "Agent",
        "The feature is fine. Precision=1.0 on the synthetic fixtures we wrote ourselves.",
        True,
    ),
    (
        "c08-accuracy-internal-fixtures",
        "Agent",
        "Accuracy=1.000 reported by the agent; dataset source: internal fixtures only.",
        True,
    ),
    (
        "c09-prod-export-with-link",
        "Agent",
        "Measured p95 latency 180 ms on production logs (dataset: prod export 2026-10-01, "
        "https://internal.example/export/2026-10-01.csv).",
        False,
    ),
    (
        "c10-zero-failures-no-data",
        "Agent",
        "Refactored the parser; pytest reports zero failures in 40 seconds, all green.",
        True,
    ),
]


@pytest.fixture(scope="module")
def hook():
    spec = importlib.util.spec_from_file_location("skeptic_auto_trigger", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _score(predicate, cases):
    tp = fp = tn = fn = 0
    rows = []
    for cid, _tool, text, label in cases:
        pred = predicate(text)
        rows.append((cid, label, pred))
        if pred and label:
            tp += 1
        elif pred and not label:
            fp += 1
        elif not pred and label:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}, rows


def test_comparison_table(hook, capsys):
    v1, v1_rows = _score(hook.is_argosarb_critical_pattern, CASES)
    v2, v2_rows = _score(hook.is_argosarb_critical_v2, CASES)
    print("\n| case | label | v1 | v2 |")
    print("|---|---|---|---|")
    for (cid, label, p1), (_, _, p2) in zip(v1_rows, v2_rows, strict=True):
        print(f"| {cid} | {'critical' if label else 'ok'} | {p1} | {p2} |")
    print(f"\nv1: {v1}\nv2: {v2}")
    # v2 must not miss a critical case that v1 catches
    assert v2["fn"] <= v1["fn"]
    # v2 must not add false alarms relative to v1 on this set
    assert v2["fp"] <= v1["fp"]


def test_c03_is_missed_by_both_because_t1_needs_all_plus_number(hook):
    # Recorded finding, not a goal. c03 says "All tests passed"; Trigger 1 only matches
    # "all <number>", "100%", "zero failures" or "perfect <word>". So T1 is False and the
    # uncited-claim check never runs. This is a recall gap in T1 for both v1 and v2.
    assert hook._TRIGGER_1_PATTERN.search(CASES[2][2]) is None
    assert hook.is_argosarb_critical_pattern(CASES[2][2]) is False
    assert hook.is_argosarb_critical_v2(CASES[2][2]) is False


def test_v1_suppresses_on_bare_phrase_v2_does_not(hook):
    # The one input where the two predicates differ on purpose. v1's _REAL_DATA_MARKERS
    # switch the signal off on the phrase "production logs" alone; v2 needs a concrete
    # URL/DOI/path, so it stays critical.
    text = "All 10 niches passed. F1=1.000. Production logs are in appendix section 7."
    assert hook.is_argosarb_critical_pattern(text) is False
    assert hook.is_argosarb_critical_v2(text) is True


def test_v2_keeps_cited_case_non_critical(hook):
    _, rows = _score(hook.is_argosarb_critical_v2, [CASES[8]])
    assert rows[0][2] is False
