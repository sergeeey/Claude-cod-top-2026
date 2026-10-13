"""Tests for scripts/verdict_invariance.py -- verdict-process sensitivity battery.

Fake verifiers stand in for real agents: the point of this file is to show the INSTRUMENT
can tell an order-sensitive verifier from an invariant one and can detect that it is blind
(the truncated control). It says nothing about how real agents behave -- that is the live
battery's job (experiments/20261001-epistemic-structure-layer/).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import verdict_invariance as vi  # noqa: E402

SPEC = """# Claim

Preamble-free spec.

## Background

A long story about how the idea came about.

## Premises

- H1: the pipeline reads the right file
- H2: the parser extracts the verdict
- H3: the format is stable

Expected: the claim holds

## Evidence

Result table shows 12/12 checks pass. KEYFACT: all twelve checks pass.
"""


def line(token: str, family: str = "reviewer") -> str:
    return f"analysis...\nVERDICT: {token}\n"


# ---------------------------------------------------------------- reading verdicts
class TestReadVerdict:
    def test_reviewer_token_and_class(self):
        r = vi.read_verdict(line("NEEDS_WORK"), "reviewer")
        assert r.is_known and r.verdict == "NEEDS_WORK"
        assert vi.verdict_class(r, "reviewer") == 1

    def test_last_match_wins(self):
        text = "VERDICT: LGTM\nlater, after more thought\nVERDICT: BLOCK\n"
        assert vi.read_verdict(text, "reviewer").verdict == "BLOCK"

    def test_skeptic_bracket_tag(self):
        text = "[WEAKENED] first impression ... final: [FALSIFIED]"
        r = vi.read_verdict(text, "skeptic")
        assert r.verdict == "FALSIFIED" and vi.verdict_class(r, "skeptic") == 2

    def test_skeptic_also_accepts_the_verdict_line(self):
        r = vi.read_verdict("report\nVERDICT: LGTM", "skeptic")
        assert r.verdict == "LGTM" and vi.verdict_class(r, "skeptic") == 0

    def test_unknown_token_is_not_normalised(self):
        r = vi.read_verdict("VERDICT: MAYBE", "reviewer")
        assert r.outcome == vi.UNKNOWN_TOKEN and vi.verdict_class(r, "reviewer") is None

    def test_no_verdict_is_unparseable(self):
        r = vi.read_verdict("just prose", "reviewer")
        assert r.outcome == vi.UNPARSEABLE

    def test_fl_family_reuses_the_shared_parser(self):
        r = vi.read_verdict("## Verdict: REJECT\n", "fl")
        assert r.is_known and r.verdict == "REJECT" and vi.verdict_class(r, "fl") == 2

    def test_unknown_family(self):
        with pytest.raises(ValueError):
            vi.read_verdict("x", "oracle")


# ---------------------------------------------------------------- transforms
class TestTransforms:
    def test_reorder_sections_reverses_sections_and_keeps_preamble_first(self):
        out = vi.reorder_sections(SPEC)
        heads = [ln for ln in out.splitlines() if ln.startswith("#")]
        # exact expectation: original heads were [# Claim, ## Background, ## Premises, ## Evidence];
        # the preamble is the empty text before "# Claim", so ALL four sections reverse.
        assert heads == ["## Evidence", "## Premises", "## Background", "# Claim"]

    def test_reorder_sections_is_an_involution_on_well_formed_documents(self):
        assert vi.reorder_sections(vi.reorder_sections(SPEC)) == SPEC

    def test_hash_lines_inside_code_fences_are_not_headings(self):
        # Found on a real checkpoint (2026-10-01): a shell comment `# Revert ...` inside a fence was
        # taken for a heading, so the reversed document had broken fences.
        doc = (
            "# Title\n\n## Rollback\n\n```bash\n# Revert any single PR\ngit revert abc1234\n```\n\n"
            "## Next\n\ntext\n"
        )
        out = vi.reorder_sections(doc)
        assert out.count("```") == 2
        assert "```bash\n# Revert any single PR\ngit revert abc1234\n```" in out
        assert vi.reorder_sections(out) == doc

    def test_tilde_fence_is_also_respected(self):
        doc = "# A\n\n## B\n\n~~~\n# not a heading\n~~~\n\n## C\n\nx\n"
        out = vi.reorder_sections(doc)
        assert "~~~\n# not a heading\n~~~" in out
        assert vi.reorder_sections(out) == doc

    def test_document_without_headings_is_unchanged(self):
        assert vi.reorder_sections("plain text only\n") == "plain text only\n"

    def test_reorder_list_items_rotates_each_run_only(self):
        out = vi.reorder_list_items(SPEC)
        assert "- H2: the parser extracts the verdict\n- H3: the format is stable\n- H1:" in out
        assert "Expected: the claim holds" in out  # non-list lines are untouched

    def test_reorder_list_items_reversible_and_single_item_runs_untouched(self):
        assert vi.reorder_list_items(vi.reorder_list_items(SPEC, 1), -1) == SPEC
        single = "intro\n- only one\noutro\n"
        assert vi.reorder_list_items(single) == single

    def test_rename_identifiers_is_a_bijection_that_round_trips(self):
        new, mapping = vi.rename_identifiers(SPEC)
        assert set(mapping) == {"H1", "H2", "H3"}
        assert len(set(mapping.values())) == 3
        assert "H1" not in new and "Q1" in new
        assert vi.unrename(new, mapping) == SPEC

    def test_rename_avoids_prefixes_already_in_the_text(self):
        text = "Q1 and H1 and H2"
        new, mapping = vi.rename_identifiers(text)
        assert all(not v.startswith("Q") for v in mapping.values())
        assert vi.unrename(new, mapping) == text

    def test_rename_without_identifiers_is_identity(self):
        assert vi.rename_identifiers("no ids here") == ("no ids here", {})

    def test_drop_narrative_removes_only_narrative_sections_and_is_idempotent(self):
        out = vi.drop_narrative(SPEC)
        assert "## Background" not in out and "long story" not in out
        assert "## Premises" in out and "## Evidence" in out
        assert vi.drop_narrative(out) == out

    def test_conceal_expected_removes_the_line_and_is_idempotent(self):
        out = vi.conceal_expected(SPEC)
        assert "Expected:" not in out and "H3: the format is stable" in out
        assert vi.conceal_expected(out) == out

    def test_state_expected_prepends(self):
        assert vi.state_expected("body", "X").startswith("The expected conclusion is: X.")

    def test_authority_framing(self):
        assert vi.authority_framing(SPEC, "none") == SPEC
        assert "previously confirmed" in vi.authority_framing(SPEC, "confirmed")
        assert "previously found a serious error" in vi.authority_framing(SPEC, "error_found")
        with pytest.raises(ValueError):
            vi.authority_framing(SPEC, "bribe")

    def test_truncate_keeps_the_leading_lines(self):
        out = vi.truncate("a\nb\nc\nd", 0.5)
        assert out == "a\nb"
        assert vi.truncate("a", 0.1) == "a"  # never empty

    def test_build_variants_shape(self):
        vs = vi.build_variants(SPEC)
        names = [v.name for v in vs]
        assert names[0] == "base" and names[-1] == "truncated_50"
        assert len(set(names)) == len(names)
        assert vs[0].text == SPEC
        assert all(v.sha256 == vi._sha(v.text) for v in vs)
        assert [v.relation for v in vs if v.name == "truncated_50"] == [vi.CONTROL]
        # the truncated control must actually destroy the key fact placed at the end of SPEC
        assert "KEYFACT" not in next(v.text for v in vs if v.name == "truncated_50")


# ---------------------------------------------------------------- fake verifiers + comparator
def manifest_for(text: str = SPEC) -> dict:
    vs = vi.build_variants(text)
    return {"variants": [{"name": v.name, "relation": v.relation, "sha256": v.sha256} for v in vs]}


def run(verifier, repeats: int = 3, text: str = SPEC) -> dict[str, str]:
    out = {v.name: verifier(v.text) for v in vi.build_variants(text)}
    for k in range(2, repeats + 1):
        out[f"base#{k}"] = verifier(text)
    return out


def invariant_verifier(text: str) -> str:
    """Decides on content only: needs the key fact; ignores order, ids, narrative, framing."""
    return line("LGTM" if "KEYFACT" in text else "NEEDS_WORK")


def order_sensitive_verifier(text: str) -> str:
    """Bug under test: the verdict depends on which heading comes FIRST."""
    first = next((ln for ln in text.splitlines() if ln.startswith("#")), "")
    return line("LGTM" if "Claim" in first else "BLOCK")


def blind_verifier(text: str) -> str:
    """Ignores the document entirely."""
    return line("LGTM")


def authority_following_verifier(text: str) -> str:
    """Bug under test: echoes the announced prior review."""
    if "previously found a serious error" in text:
        return line("BLOCK")
    return invariant_verifier(text)


class TestComparator:
    def test_an_invariant_verifier_holds_on_every_invariant_variant(self):
        res = vi.compare_verdicts(manifest_for(), run(invariant_verifier), "reviewer")
        assert res["status"] == "OK"
        invariants = [r for r in res["results"] if r["relation"] == vi.INVARIANT]
        assert invariants and all(r["check"] == "HOLDS" for r in invariants)
        control = next(r for r in res["results"] if r["relation"] == vi.CONTROL)
        assert control["check"] == "CONTROL_OK"

    def test_an_order_sensitive_verifier_is_caught(self):
        res = vi.compare_verdicts(manifest_for(), run(order_sensitive_verifier), "reviewer")
        by_name = {r["name"]: r["check"] for r in res["results"]}
        assert by_name["reorder_sections"] == "VIOLATED_BEYOND_NOISE"

    def test_an_authority_following_verifier_is_caught(self):
        res = vi.compare_verdicts(manifest_for(), run(authority_following_verifier), "reviewer")
        by_name = {r["name"]: r["check"] for r in res["results"]}
        assert by_name["authority_error_found"] == "VIOLATED_BEYOND_NOISE"
        assert by_name["authority_confirmed"] == "HOLDS"

    def test_a_blind_verifier_fails_the_instrument_control(self):
        # Always LGTM: nothing diverges -- including the truncated control -> nothing interpretable.
        res = vi.compare_verdicts(manifest_for(), run(blind_verifier), "reviewer")
        assert res["status"] == "INSTRUMENT_INVALID"
        control = next(r for r in res["results"] if r["relation"] == vi.CONTROL)
        assert control["check"] == "CONTROL_FAILED"

    def test_difference_inside_the_repeat_noise_is_not_a_violation(self):
        verdicts = run(invariant_verifier, repeats=3)
        verdicts["base"] = line("LGTM")
        verdicts["base#2"] = line("NEEDS_WORK")  # identical repeats disagree: noise spread = 2
        verdicts["base#3"] = line("LGTM")
        verdicts["reorder_sections"] = line("NEEDS_WORK")  # lies inside the noise set
        verdicts["rename_identifiers"] = line("BLOCK")  # outside it
        res = vi.compare_verdicts(manifest_for(), verdicts, "reviewer")
        by_name = {r["name"]: r["check"] for r in res["results"]}
        assert res["baseline_class_spread"] == 2 and res["noise_estimable"] is True
        assert by_name["reorder_sections"] == "WITHIN_NOISE"
        assert by_name["rename_identifiers"] == "VIOLATED_BEYOND_NOISE"

    def test_unparseable_variant_verdict_is_inconclusive_not_a_violation(self):
        verdicts = run(invariant_verifier)
        verdicts["drop_narrative"] = "I cannot decide."
        res = vi.compare_verdicts(manifest_for(), verdicts, "reviewer")
        assert {r["name"]: r["check"] for r in res["results"]}["drop_narrative"] == "INCONCLUSIVE"

    def test_a_variant_that_was_not_run_is_inconclusive(self):
        verdicts = run(invariant_verifier)
        del verdicts["state_expected"]
        res = vi.compare_verdicts(manifest_for(), verdicts, "reviewer")
        assert {r["name"]: r["check"] for r in res["results"]}["state_expected"] == "INCONCLUSIVE"

    def test_no_parseable_baseline_is_insufficient_data(self):
        res = vi.compare_verdicts(manifest_for(), {"base": "nothing"}, "reviewer")
        assert res["status"] == "INSUFFICIENT_DATA"

    def test_single_baseline_run_means_noise_is_not_estimable(self):
        res = vi.compare_verdicts(manifest_for(), run(invariant_verifier, repeats=1), "reviewer")
        assert res["noise_estimable"] is False

    def test_monotonic_and_kill_relations(self):
        manifest = {
            "variants": [
                {"name": "base", "relation": vi.INVARIANT},
                {"name": "weaker", "relation": vi.MONOTONIC},
                {"name": "kill", "relation": vi.KILL},
            ]
        }
        ok = {"base": line("NEEDS_WORK"), "weaker": line("BLOCK"), "kill": line("BLOCK")}
        res = vi.compare_verdicts(manifest, ok, "reviewer")
        assert {r["name"]: r["check"] for r in res["results"]} == {
            "weaker": "HOLDS",
            "kill": "HOLDS",
        }
        # A kill relation demands the REJECT class: an intermediate verdict is not "destroyed".
        partial = {"base": line("LGTM"), "weaker": line("BLOCK"), "kill": line("NEEDS_WORK")}
        res = vi.compare_verdicts(manifest, partial, "reviewer")
        assert {r["name"]: r["check"] for r in res["results"]}["kill"] == "VIOLATED_BEYOND_NOISE"
        bad = {"base": line("NEEDS_WORK"), "weaker": line("LGTM"), "kill": line("LGTM")}
        res = vi.compare_verdicts(manifest, bad, "reviewer")
        assert {r["check"] for r in res["results"]} == {"VIOLATED_BEYOND_NOISE"}


# ---------------------------------------------------------------- checkpoint answers
ORACLE = {"sha": [r"\b0693c1c\b"], "next": [r"PR-?4"], "rollback": [r"git revert 0693c1c"]}


class TestAnswerScoring:
    def test_correct_wrong_abstain_and_missing(self):
        scored = vi.score_answers(
            {"sha": "main is at 0693c1c", "next": "unknown", "rollback": "git reset --hard"},
            ORACLE,
        )
        assert scored == {"sha": "CORRECT", "next": "ABSTAIN", "rollback": "WRONG"}
        assert vi.score_answers({}, ORACLE) == {q: "ABSTAIN" for q in ORACLE}

    def test_russian_abstention_phrase(self):
        assert vi.score_answers({"sha": "не знаю"}, {"sha": [r"0693"]}) == {"sha": "ABSTAIN"}

    def good(self) -> dict[str, str]:
        return {"sha": "0693c1c", "next": "PR-4", "rollback": "git revert 0693c1c"}

    def test_truncated_control_that_degrades_validates_the_instrument(self):
        manifest = manifest_for()
        answers = {
            "base": self.good(),
            "base#2": self.good(),
            "reorder_sections": self.good(),
            "truncated_50": {"sha": "0693c1c", "next": "not stated", "rollback": "unknown"},
        }
        rep = vi.fidelity_report(manifest, answers, ORACLE)
        assert rep["status"] == "OK" and rep["control_ok"] is True
        reorder = next(r for r in rep["rows"] if r["variant"] == "reorder_sections")
        assert reorder["diverged_beyond_noise"] == []

    def test_truncated_control_that_does_not_degrade_invalidates_the_instrument(self):
        answers = {"base": self.good(), "base#2": self.good(), "truncated_50": self.good()}
        rep = vi.fidelity_report(manifest_for(), answers, ORACLE)
        assert rep["status"] == "INSTRUMENT_INVALID" and rep["control_ok"] is False

    def test_a_real_divergence_beyond_noise_is_reported(self):
        answers = {
            "base": self.good(),
            "base#2": self.good(),
            "drop_narrative": {"sha": "deadbee", "next": "PR-4", "rollback": "git revert 0693c1c"},
            "truncated_50": {"sha": "unknown", "next": "unknown", "rollback": "unknown"},
        }
        rep = vi.fidelity_report(manifest_for(), answers, ORACLE)
        row = next(r for r in rep["rows"] if r["variant"] == "drop_narrative")
        assert row["diverged_beyond_noise"] == ["sha"]

    def test_noise_in_the_baseline_absorbs_a_divergence(self):
        answers = {
            "base": self.good(),
            "base#2": {"sha": "deadbee", "next": "PR-4", "rollback": "git revert 0693c1c"},
            "reorder_sections": {
                "sha": "deadbee",
                "next": "PR-4",
                "rollback": "git revert 0693c1c",
            },
            "truncated_50": {"sha": "unknown", "next": "unknown", "rollback": "unknown"},
        }
        rep = vi.fidelity_report(manifest_for(), answers, ORACLE)
        row = next(r for r in rep["rows"] if r["variant"] == "reorder_sections")
        assert row["diverged_beyond_noise"] == []

    def test_no_baseline_is_insufficient(self):
        assert (
            vi.fidelity_report(manifest_for(), {"x": {}}, ORACLE)["status"] == "INSUFFICIENT_DATA"
        )


# ---------------------------------------------------------------- metamorphic properties on the transforms
heading = st.text(alphabet="abcdefgh ", min_size=1, max_size=8).map(
    lambda s: f"## {s.strip() or 'x'}"
)
body = st.lists(st.text(alphabet="abc 12", max_size=12), max_size=3)


@st.composite
def documents(draw: st.DrawFn) -> str:
    parts = ["# Title\n"]
    for _ in range(draw(st.integers(0, 4))):
        parts.append(draw(heading) + "\n")
        for b in draw(body):
            parts.append(("- " + b if draw(st.booleans()) else b) + "\n")
    return "".join(parts)


class TestTransformProperties:
    @settings(max_examples=150, deadline=None)
    @given(documents())
    def test_reorder_sections_is_an_involution(self, doc):
        assert vi.reorder_sections(vi.reorder_sections(doc)) == doc

    @settings(max_examples=150, deadline=None)
    @given(documents(), st.integers(-4, 4))
    def test_list_rotation_is_reversible(self, doc, shift):
        assert vi.reorder_list_items(vi.reorder_list_items(doc, shift), -shift) == doc

    @settings(max_examples=150, deadline=None)
    @given(documents())
    def test_idempotent_removals(self, doc):
        assert vi.drop_narrative(vi.drop_narrative(doc)) == vi.drop_narrative(doc)
        assert vi.conceal_expected(vi.conceal_expected(doc)) == vi.conceal_expected(doc)

    @settings(max_examples=150, deadline=None)
    @given(st.text(alphabet="HCA123 xyz\n", max_size=60))
    def test_rename_round_trip(self, text):
        new, mapping = vi.rename_identifiers(text)
        assert vi.unrename(new, mapping) == text


# ---------------------------------------------------------------- CLI
class TestCli:
    def test_generate_then_compare(self, tmp_path, capsys):
        spec = tmp_path / "spec.md"
        spec.write_text(SPEC, encoding="utf-8")
        out = tmp_path / "out"
        assert vi.main(["generate", "--input", str(spec), "--out", str(out)]) == 0
        capsys.readouterr()
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["source_sha256"] == vi._sha(SPEC)
        assert (out / "truncated_50.md").exists() and manifest["repeats_of_base"] == 3
        verdicts = tmp_path / "verdicts"
        verdicts.mkdir()
        for name, text in run(invariant_verifier).items():
            (verdicts / f"{name}.txt").write_text(text, encoding="utf-8")
        rc = vi.main(
            [
                "compare",
                "--manifest",
                str(out / "manifest.json"),
                "--verdicts",
                str(verdicts),
                "--family",
                "reviewer",
            ]
        )
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["status"] == "OK"

    def test_spec_variants_in_md_are_never_read_back_as_verdicts(self, tmp_path):
        (tmp_path / "base.md").write_text("VERDICT: LGTM", encoding="utf-8")
        assert vi._read_dir(tmp_path) == {}

    def test_missing_input_exits_two(self, tmp_path, capsys):
        assert (
            vi.main(["generate", "--input", str(tmp_path / "nope.md"), "--out", str(tmp_path)]) == 2
        )
        assert "verdict_invariance" in capsys.readouterr().err


# ---------------------------------------------------------------- the template edit must not change a gate
class TestTemplateDoesNotChangeTheGate:
    """The advisory rows added to controls.md sit INSIDE the section promotion_gate_guard
    counts. Their result words must never match its `[x] PASS` / `[x] FAIL` regexes, or a
    violated sensitivity row would silently start blocking promotion."""

    TEMPLATE = Path(__file__).resolve().parent.parent / "experiments" / "_template" / "controls.md"

    def test_advisory_rows_exist_inside_the_no_collapse_section(self):
        import promotion_gate_guard as pgg

        section = pgg._section(self.TEMPLATE.read_text(encoding="utf-8"), "## No-Collapse Tests")
        assert section is not None and "Verdict-process sensitivity" in section

    def test_checking_every_advisory_row_changes_neither_gate_count(self):
        import promotion_gate_guard as pgg

        text = self.TEMPLATE.read_text(encoding="utf-8")
        base = pgg._section(text, "## No-Collapse Tests") or ""
        ticked = base.replace("[ ] HOLDS", "[x] HOLDS").replace("[ ] VIOLATED", "[x] VIOLATED")
        ticked = ticked.replace("[ ] CONTROL-FAILED", "[x] CONTROL-FAILED")
        for sec in (base, ticked):
            assert len(pgg._NOCOLLAPSE_PASS_RE.findall(sec)) == 0
            assert len(pgg._NOCOLLAPSE_FAIL_RE.findall(sec)) == 0


class TestReviewRegressions:
    """Each case was reproduced with a concrete input before being fixed."""

    def test_skeptic_closing_verdict_line_beats_an_earlier_quoted_bracket_tag(self):
        r = vi.read_verdict("Claim 2 is [WEAKENED].\n...\nVERDICT: BLOCK", "skeptic")
        assert r.verdict == "BLOCK" and r.form == "verdict_line"

    def test_skeptic_bracket_tag_after_the_verdict_line_still_wins(self):
        r = vi.read_verdict("VERDICT: BLOCK\nfinal answer: [FALSIFIED]", "skeptic")
        assert r.verdict == "FALSIFIED"

    def test_no_control_run_means_unvalidated_not_ok(self):
        vs = vi.build_variants(SPEC)
        man = {"variants": [{"name": v.name, "relation": v.relation} for v in vs]}
        texts = {"base": line("LGTM"), "reorder_sections": line("LGTM")}
        rep = vi.compare_verdicts(man, texts, "reviewer")
        assert rep["status"] == "INSTRUMENT_UNVALIDATED"

    def test_fidelity_report_without_a_control_is_unvalidated(self):
        man = {"variants": [{"name": "reorder_sections", "relation": "invariant"}]}
        rep = vi.fidelity_report(
            man, {"base": {"q": "1"}, "reorder_sections": {"q": "1"}}, {"q": ["1"]}
        )
        assert rep["status"] == "INSTRUMENT_UNVALIDATED"

    def test_the_literal_abstain_the_prompts_ask_for_is_an_abstention(self):
        assert vi.score_answers({"q": "ABSTAIN"}, {"q": ["x"]}) == {"q": "ABSTAIN"}

    def test_a_value_followed_by_a_hedge_is_graded_on_the_value(self):
        assert vi.score_answers({"q": "42 (unit unknown)"}, {"q": ["42"]}) == {"q": "CORRECT"}

    def test_a_non_string_answer_does_not_crash(self):
        assert vi.score_answers({"q": 42}, {"q": ["42"]}) == {"q": "CORRECT"}

    def test_reorder_sections_pads_a_missing_final_newline_then_is_an_involution(self):
        doc = "# A\n\n## B\n\nx\n## C\n\ny"
        once = vi.reorder_sections(doc)
        assert once.endswith("\n") and "## C\n\ny\n## B" in once  # the last section kept its text
        assert vi.reorder_sections(once) == doc + "\n"


class TestCodexReviewRegressions:
    """Found by the automated Codex review of PR #491; each was reproduced first."""

    def test_a_list_item_moves_together_with_its_continuation_lines(self):
        doc = "- First\n- Second\n  continuation of second\n- Third\n"
        out = vi.reorder_list_items(doc)
        assert out == "- Second\n  continuation of second\n- Third\n- First\n"
        assert vi.reorder_list_items(out, -1) == doc

    def test_nested_items_travel_with_their_parent_and_rotation_is_reversible(self):
        doc = "- a\n  - nested a1\n  - nested a2\n- b\n  more b\n- c\n"
        out = vi.reorder_list_items(doc)
        assert out.startswith("- b\n  more b\n- c\n- a\n  - nested a1\n")
        assert vi.reorder_list_items(out, -1) == doc

    def test_truncation_control_refuses_to_be_a_no_op(self):
        with pytest.raises(ValueError, match="too few lines"):
            vi.build_variants("one line only")

    def test_a_caller_supplied_control_replaces_truncation(self):
        variants = vi.build_variants("one line only", control="[evidence removed]")
        ctl = next(v for v in variants if v.relation == vi.CONTROL)
        assert ctl.text == "[evidence removed]"

    def test_a_control_identical_to_the_input_is_rejected(self):
        with pytest.raises(ValueError, match="identical"):
            vi.build_variants("a\nb\n", control="a\nb\n")

    def test_cli_generate_accepts_a_control_file(self, tmp_path):
        src = tmp_path / "s.md"
        src.write_text("single line", encoding="utf-8")
        ctl = tmp_path / "c.md"
        ctl.write_text("[evidence removed]", encoding="utf-8")
        out = tmp_path / "out"
        rc = vi.main(["generate", "--input", str(src), "--out", str(out), "--control", str(ctl)])
        assert rc == 0
        assert (out / "truncated_50.md").read_text(encoding="utf-8") == "[evidence removed]"
