"""Tests for reject_gate_guard.py — the NULL Exploitation Gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from reject_gate_guard import (
    _check_reason_specific,
    _check_relaxation_map,
    _check_what_killed,
    _check_what_survived,
    _has_reject,
    _is_decision_md,
    _is_placeholder,
    _section,
)

# ── path / verdict helpers ────────────────────────────────────────────────────


class TestIsDecisionMd:
    def test_valid(self):
        assert _is_decision_md("experiments/20260101-x/decision.md")

    def test_nested(self):
        assert _is_decision_md("D:/repo/experiments/20260101-x/decision.md")

    def test_wrong_name(self):
        assert not _is_decision_md("experiments/20260101-x/claim.md")

    def test_no_experiments(self):
        assert not _is_decision_md("docs/decision.md")


class TestHasReject:
    def test_detects_checked(self):
        assert _has_reject("- [x] REJECT — claim falsified")

    def test_ignores_unchecked(self):
        assert not _has_reject("- [ ] REJECT — claim falsified")

    def test_case_insensitive(self):
        assert _has_reject("- [X] reject")

    def test_promote_is_not_reject(self):
        assert not _has_reject("- [x] PROMOTE — holds")


class TestIsPlaceholder:
    def test_empty(self):
        assert _is_placeholder("")
        assert _is_placeholder("{  }")
        assert _is_placeholder("A_")
        assert _is_placeholder("V1:")

    def test_real_value(self):
        assert not _is_placeholder("spinor index argument")


# ── section extraction ────────────────────────────────────────────────────────


class TestSection:
    def test_extracts_until_same_level(self):
        md = "### What Was Killed\nbody1\n### What Was NOT Killed\nbody2\n"
        sec = _section(md, "What Was Killed")
        assert "body1" in sec
        assert "body2" not in sec

    def test_missing_returns_none(self):
        assert _section("## Other\n", "Nonexistent") is None

    def test_stops_at_higher_level(self):
        md = "### Relaxation Map\nrow\n## Rescue Review\nother\n"
        sec = _section(md, "Relaxation Map")
        assert "row" in sec
        assert "other" not in sec


# ── condition 1: what was killed ──────────────────────────────────────────────


class TestWhatKilled:
    def test_empty_template_fails(self):
        md = (
            "### What Was Killed\n"
            "_instruction_\n"
            "- The claim as stated under: {  }\n"
            "- Specifically, assumption(s) killed: {  }\n"
            "### What Was NOT Killed\n"
        )
        passed, _ = _check_what_killed(md)
        assert not passed

    def test_filled_passes(self):
        md = (
            "### What Was Killed\n"
            "- The claim as stated under: single-bundle ansatz on S6\n"
            "### What Was NOT Killed\n"
        )
        passed, _ = _check_what_killed(md)
        assert passed

    def test_missing_section_fails(self):
        passed, detail = _check_what_killed("## Rationale\nx\n")
        assert not passed
        assert "missing" in detail


# ── condition 2: what survived ────────────────────────────────────────────────


class TestWhatSurvived:
    def test_empty_template_fails(self):
        md = (
            "### What Was NOT Killed\n"
            "- [ ] Core mechanism / theoretical basis:\n"
            "- [ ] Assumption [A_]: (survived because: )\n"
            "### Relaxation Map\n"
        )
        passed, _ = _check_what_survived(md)
        assert not passed

    def test_checked_survivor_passes(self):
        md = (
            "### What Was NOT Killed\n"
            "- [x] Core mechanism / theoretical basis: Atiyah-Singer index argument\n"
            "### Relaxation Map\n"
        )
        passed, _ = _check_what_survived(md)
        assert passed

    def test_colon_value_passes(self):
        md = (
            "### What Was NOT Killed\n"
            "- Assumption A1: lambda stays constant across the fibre\n"
            "### Relaxation Map\n"
        )
        passed, _ = _check_what_survived(md)
        assert passed


# ── condition 3: relaxation map ───────────────────────────────────────────────


class TestRelaxationMap:
    def test_only_placeholders_fails(self):
        md = (
            "### Relaxation Map\n"
            "| Assumption | Modification | New Path | Known kill-evidence? | Cheapest test |\n"
            "|---|---|---|---|---|\n"
            "| A_ | Remove | V1: | No | [test, N days] |\n"
            "| A_ | Weaken | V2: | No | [test, N days] |\n"
            "### Escape Point\n"
        )
        passed, _ = _check_relaxation_map(md)
        assert not passed

    def test_real_row_passes(self):
        md = (
            "### Relaxation Map\n"
            "| Assumption | Modification | New Path | Known kill-evidence? | Cheapest test |\n"
            "|---|---|---|---|---|\n"
            "| equal radii | Weaken | V2: unequal S3/S6 radii | No | spectral recompute, 1d |\n"
            "### Escape Point\n"
        )
        passed, _ = _check_relaxation_map(md)
        assert passed

    def test_missing_section_fails(self):
        passed, detail = _check_relaxation_map("## Rationale\n")
        assert not passed
        assert "missing" in detail


# ── condition 4: reason specificity ───────────────────────────────────────────


class TestReasonSpecific:
    def test_vague_reason_fails(self):
        md = "## Rationale\nThe experiment didn't work, moving on.\n## Next\n"
        passed, detail = _check_reason_specific(md)
        assert not passed
        assert "vague" in detail

    def test_russian_vague_fails(self):
        md = "## Rationale\nНе получилось добиться результата.\n## Next\n"
        passed, _ = _check_reason_specific(md)
        assert not passed

    def test_structural_reason_passes(self):
        md = (
            "## Rationale\n"
            "χ(S6)=2 forbids a single bundle with c3=6 giving index 3; the "
            "topological obstruction is exact.\n"
            "## Next\n"
        )
        passed, _ = _check_reason_specific(md)
        assert passed


# ── integration: a fully filled REJECT passes all four ────────────────────────


class TestFullDecisionPasses:
    def test_complete_kill_analysis(self):
        md = (
            "- [x] REJECT — claim falsified\n"
            "## Rationale\n"
            "χ(S6)=2 is an exact topological obstruction; no single bundle works.\n"
            "## If REJECT: Kill Analysis\n"
            "### What Was Killed\n"
            "- The claim as stated under: single-bundle ansatz, c3=6\n"
            "### What Was NOT Killed\n"
            "- [x] Core mechanism: multi-bundle index decomposition survives\n"
            "### Relaxation Map\n"
            "| Assumption | Modification | New Path | Known kill-evidence? | Cheapest test |\n"
            "|---|---|---|---|---|\n"
            "| single bundle | Replace | V3: split into 3 line bundles | No | index calc, 1d |\n"
            "### Escape Point\n"
        )
        for fn in (
            _check_what_killed,
            _check_what_survived,
            _check_relaxation_map,
            _check_reason_specific,
        ):
            passed, detail = fn(md)
            assert passed, f"{fn.__name__} failed: {detail}"
