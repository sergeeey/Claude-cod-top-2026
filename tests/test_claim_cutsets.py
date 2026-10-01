"""Tests for scripts/claim_cutsets.py -- minimal support / cut sets of a claim's logic.

Hand-derived expectations (before the module was run). Synthetic structures verify the CODE;
they say nothing about whether the tool is useful on real claims -- that is the experiment's
job (experiments/20261001-epistemic-structure-layer).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import claim_cutsets as cc  # noqa: E402


def fam(*sets: str) -> frozenset[frozenset[str]]:
    """fam("AB", "CD") -> {{A,B},{C,D}} (single-letter names)."""
    return frozenset(frozenset(s) for s in sets)


def named(*sets: list[str]) -> frozenset[frozenset[str]]:
    return frozenset(frozenset(s) for s in sets)


# ---------------------------------------------------------------- parser
class TestParser:
    def test_and_binds_tighter_than_or(self):
        e = cc.parse_logic("A & B | C")
        assert isinstance(e, cc.Or) and len(e.children) == 2
        assert isinstance(e.children[0], cc.And)

    def test_parentheses_override_precedence(self):
        e = cc.parse_logic("A & (B | C)")
        assert isinstance(e, cc.And) and isinstance(e.children[1], cc.Or)

    def test_word_and_unicode_operators(self):
        assert cc.parse_logic("A AND B or C") == cc.parse_logic("A & B | C")
        assert cc.parse_logic("A ∧ B ∨ C") == cc.parse_logic("A & B | C")

    def test_left_hand_side_is_optional(self):
        assert cc.parse_logic("H = A & B") == cc.parse_logic("A & B")

    def test_nested_same_operator_is_flattened(self):
        e = cc.parse_logic("A & (B & C)")
        assert isinstance(e, cc.And) and len(e.children) == 3

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "A &",
            "& A",
            "(A",
            "A)",
            "A B",
            "A & ; import os",
            "__import__('os')",
            "A ** B",
            "A=B=C",
        ],
    )
    def test_anything_outside_the_grammar_is_a_parse_error(self, bad):
        with pytest.raises(cc.LogicParseError):
            cc.parse_logic(bad)

    def test_deep_nesting_is_an_error_not_a_crash(self):
        with pytest.raises(cc.LogicParseError):
            cc.parse_logic("(" * 400 + "A" + ")" * 400)

    @settings(max_examples=300, deadline=None)
    @given(st.text(max_size=60))
    def test_arbitrary_text_never_raises_anything_but_parse_error(self, text):
        try:
            cc.parse_logic(text)
        except cc.LogicParseError:
            pass


# ---------------------------------------------------------------- textbook structures
class TestTextbookStructures:
    def test_two_independent_pairs(self):
        # H = (A & B) | (C & D): supports {AB},{CD}; cuts = choose one from each pair.
        r = cc.analyze(cc.parse_logic("H = (A & B) | (C & D)"))
        assert cc.supports(cc.parse_logic("(A & B) | (C & D)")) == fam("AB", "CD")
        assert cc.cuts(cc.parse_logic("(A & B) | (C & D)")) == fam("AC", "AD", "BC", "BD")
        assert r["kappa"] == 2 and r["singleton_failures"] == []
        assert r["false_independence"] == [] and r["dead_nodes"] == []

    def test_three_paths_on_one_shared_leg_is_false_independence(self):
        # Three "independent" confirmations all rest on X.
        e = cc.parse_logic("(X & A1 & A2) | (X & B1 & B2) | (X & C1 & C2)")
        r = cc.analyze(e)
        # cuts: {X} plus one node from each path's private pair: 2*2*2 = 8 triples -> 9 total.
        assert r["kappa"] == 1
        assert r["singleton_failures"] == ["X"]
        assert r["false_independence"] == ["X"]
        assert len(r["minimal_cut_sets"]) == 9
        assert r["cut_order_histogram"] == {1: 1, 3: 8}

    def test_drug_example_blinding_is_a_single_point_of_failure(self):
        # H = Mechanism & Effect & Randomization & Blinding, Effect = (D1&An1)|(D2&An2)
        e = cc.parse_logic("M & ((D1 & An1) | (D2 & An2)) & R & B")
        r = cc.analyze(e)
        assert r["singleton_failures"] == ["B", "M", "R"]
        assert r["kappa"] == 1
        pair_cuts = {tuple(c) for c in r["minimal_cut_sets"] if len(c) == 2}
        assert pair_cuts == {("D1", "D2"), ("An1", "D2"), ("An2", "D1"), ("An1", "An2")}
        assert len(r["minimal_cut_sets"]) == 7

    def test_absorbed_alternative_leaves_a_dead_node(self):
        # A | (A & B): B can never matter on its own.
        r = cc.analyze(cc.parse_logic("A | (A & B)"))
        assert r["dead_nodes"] == ["B"]
        assert r["minimal_support_sets"] == [["A"]]

    def test_and_only_logic_is_flagged_as_no_redundancy(self):
        r = cc.analyze(cc.parse_logic("A & B & C"))
        assert r["only_and_logic"] is True and r["kappa"] == 1
        assert r["singleton_failures"] == ["A", "B", "C"]
        assert r["false_independence"] == []  # one path only: nothing is falsely independent
        assert "no redundancy" in r["note"]

    def test_single_node(self):
        r = cc.analyze(cc.parse_logic("A"))
        assert r["kappa"] == 1 and r["minimal_cut_sets"] == [["A"]]

    def test_minimal_sufficient_evidence_set_is_the_smallest_support(self):
        r = cc.analyze(cc.parse_logic("(A & B & C) | (D & E)"))
        assert r["minimal_sufficient_evidence_sets"] == [["D", "E"]]

    def test_avoid_set_is_the_minimum_order_cuts(self):
        r = cc.analyze(cc.parse_logic("X & (A | B)"))  # cuts: {X}, {A,B}; kappa 1
        assert r["avoid_set"] == ["X"]


class TestNodeMetadata:
    def test_infrastructure_cuts_are_separated_from_certification_cuts(self):
        nodes = {"CI": {"kind": "infrastructure"}}
        r = cc.analyze(cc.parse_logic("CI & (A | B)"), nodes)
        assert ["CI"] in r["infrastructure_only_cuts"]
        assert ["CI"] not in r["certification_cuts"]
        assert ["A", "B"] in r["certification_cuts"]

    def test_next_target_prefers_weak_low_order_cut_nodes(self):
        nodes = {"X": {"status": "verified"}, "Y": {"status": "weak"}}
        r = cc.analyze(cc.parse_logic("X & Y"), nodes)
        order = [t["node"] for t in r["next_verification_target"]]
        assert order == ["Y", "X"]
        assert "[WEAK]" in r["next_verification_target_note"]


# ---------------------------------------------------------------- size cap
class TestCap:
    def pairs_expr(self, n: int) -> str:
        return " | ".join(f"(a{i} & b{i})" for i in range(n))

    def test_exponential_cut_family_is_truncated_not_misreported(self):
        r = cc.analyze(cc.parse_logic(self.pairs_expr(15)), max_sets=5000)  # 2^15 cuts
        assert r["status"] == "TRUNCATED" and r["truncated"] is True
        assert "kappa" not in r

    def test_a_family_exactly_at_the_cap_is_accepted_and_one_over_is_not(self):
        # OR of 5 names has exactly 5 minimal supports (and 1 cut of size 5).
        e = cc.parse_logic("A | B | C | D | E")
        assert cc.analyze(e, max_sets=5)["status"] == "OK"
        assert cc.analyze(e, max_sets=4)["status"] == "TRUNCATED"

    def test_same_structure_fits_under_a_larger_cap(self):
        # Hand derivation: a cut must hit each of the 8 disjoint supports {a_i, b_i}; a MINIMAL
        # cut takes exactly one node per pair -> size 8, and there are 2^8 = 256 of them.
        r = cc.analyze(cc.parse_logic(self.pairs_expr(8)), max_sets=5000)
        assert r["status"] == "OK" and r["kappa"] == 8
        assert len(r["minimal_cut_sets"]) == 256
        assert r["cut_order_histogram"] == {8: 256}


# ---------------------------------------------------------------- AND/OR duality (cross-checks)
names = st.sampled_from(list("ABCDEFG"))


@st.composite
def exprs(draw: st.DrawFn, depth: int = 0) -> cc.Expr:
    if depth >= 3 or draw(st.integers(0, 3)) == 0:
        return cc.Var(draw(names))
    kind = draw(st.sampled_from([cc.And, cc.Or]))
    kids = tuple(draw(exprs(depth + 1)) for _ in range(draw(st.integers(2, 3))))
    return kind(kids)


class TestDuality:
    @settings(max_examples=200, deadline=None)
    @given(exprs())
    def test_cuts_are_the_minimal_transversals_of_supports(self, e):
        assert cc.cuts(e) == cc.minimal_transversals(cc.supports(e))

    @settings(max_examples=200, deadline=None)
    @given(exprs())
    def test_supports_are_the_minimal_transversals_of_cuts(self, e):
        assert cc.supports(e) == cc.minimal_transversals(cc.cuts(e))

    @settings(max_examples=200, deadline=None)
    @given(exprs())
    def test_every_cut_meets_every_support(self, e):
        sup, cut = cc.supports(e), cc.cuts(e)
        assert all(c & s for c in cut for s in sup)

    @settings(max_examples=200, deadline=None)
    @given(exprs())
    def test_both_families_are_antichains(self, e):
        for family in (cc.supports(e), cc.cuts(e)):
            for a in family:
                for b in family:
                    assert a == b or not a < b

    @settings(max_examples=150, deadline=None)
    @given(exprs())
    def test_adding_an_or_alternative_never_lowers_kappa(self, e):
        base = cc.analyze(e)["kappa"]
        more = cc.analyze(cc.Or((e, cc.Var("Z1"))))["kappa"]
        assert more >= base

    @settings(max_examples=150, deadline=None)
    @given(exprs())
    def test_adding_an_and_dependency_never_raises_kappa(self, e):
        base = cc.analyze(e)["kappa"]
        more = cc.analyze(cc.And((e, cc.Var("Z1"))))["kappa"]
        assert more <= base


class TestMutationSensitivity:
    """Plausible bugs must be distinguishable by the textbook case, or the suite proves nothing."""

    @staticmethod
    def mutant_supports_without_minimization(e: cc.Expr) -> cc.Family:
        if isinstance(e, cc.Var):
            return frozenset({frozenset({e.name})})
        fams = [TestMutationSensitivity.mutant_supports_without_minimization(c) for c in e.children]
        acc = fams[0]
        for f in fams[1:]:
            acc = (
                frozenset(acc | f)
                if isinstance(e, cc.Or)
                else frozenset(x | y for x in acc for y in f)
            )
        return acc

    def test_missing_absorption_would_be_caught(self):
        e = cc.parse_logic("A | (A & B)")
        assert cc.supports(e) == fam("A")
        assert self.mutant_supports_without_minimization(e) == fam("A", "AB")

    def test_swapping_and_or_in_cuts_would_be_caught(self):
        e = cc.parse_logic("(A & B) | (C & D)")
        # a "cuts" that forgot the duality swap would return the supports instead
        assert cc.cuts(e) != cc.supports(e)


# ---------------------------------------------------------------- decomposer adapter
DECOMPOSER = """Claim Register
C1: pipeline reads the right file  [TYPE: empirical]  [EVIDENCE: cite]
C2: the file format is stable  [TYPE: logical]  [EVIDENCE: none]
C3: the parser extracts the verdict  [TYPE: logical]  [EVIDENCE: cite]
C4: documentation is readable  [TYPE: definitional]  [EVIDENCE: none]

BLOCKING_ATOMS: [C3]
LOAD_BEARING: [C2]
INDEPENDENT: [C4]

C1 → C2 → C3
"""


class TestDecomposerAdapter:
    def test_parse_extracts_atoms_edges_and_declarations(self):
        d = cc.parse_decomposer(DECOMPOSER)
        assert set(d["atoms"]) == {"C1", "C2", "C3", "C4"}
        assert d["edges"] == [("C1", "C2"), ("C2", "C3")]
        assert d["blocking"] == ["C3"] and d["independent"] == ["C4"]

    def test_transitive_dependencies_of_a_blocking_atom_are_implied_blockers(self):
        # C3 blocking; C3 relies on C2; C2 relies on C1 -> C1 and C2 are required too,
        # yet the run declared only C3: a mechanical inconsistency in the skill's own output.
        r = cc.decomposer_analysis(DECOMPOSER, None, 5000)
        assert r["status"] == "OK"
        assert r["declared_blocking_atoms"] == ["C3"]
        assert r["computed_singleton_failures"] == ["C1", "C2", "C3"]
        assert r["implied_but_undeclared"] == ["C1", "C2"]
        assert r["independent_but_required"] == []

    def test_an_atom_declared_independent_but_required_is_flagged(self):
        text = DECOMPOSER.replace("INDEPENDENT: [C4]", "INDEPENDENT: [C2]")
        r = cc.decomposer_analysis(text, None, 5000)
        assert r["independent_but_required"] == ["C2"]

    def test_logic_override_supplies_the_or_structure(self):
        r = cc.decomposer_analysis(DECOMPOSER, "H = C3 & (C1 | C2)", 5000)
        assert r["logic_source"] == "--logic"
        assert r["computed_singleton_failures"] == ["C3"]
        assert r["declared_but_not_singleton"] == []

    def test_unannotated_text_is_insufficient(self):
        assert cc.decomposer_analysis("nothing here", None, 5000)["status"] == "INSUFFICIENT_DATA"

    def test_no_blocking_and_no_logic_is_insufficient(self):
        text = "C1: a  [TYPE: x]  [EVIDENCE: none]\nC2: b  [TYPE: x]  [EVIDENCE: none]\n"
        assert cc.decomposer_analysis(text, None, 5000)["status"] == "INSUFFICIENT_DATA"

    def test_template_placeholders_do_not_create_blockers(self):
        text = "C1: [x]  [TYPE]  [EVIDENCE]\nBLOCKING_ATOMS: [C?, C?]\n"
        assert cc.decomposer_analysis(text, None, 5000)["status"] == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------- CLI
class TestCli:
    def test_logic_json(self, capsys):
        assert cc.main(["--logic", "H = (A & B) | (C & D)", "--json"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["kappa"] == 2 and out["status"] == "OK"

    def test_parse_error_exits_two(self, capsys):
        assert cc.main(["--logic", "A &"]) == 2
        assert "claim_cutsets" in capsys.readouterr().err

    def test_decomposer_file(self, tmp_path, capsys):
        f = tmp_path / "run.md"
        f.write_text(DECOMPOSER, encoding="utf-8")
        assert cc.main(["--decomposer", str(f), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["implied_but_undeclared"] == ["C1", "C2"]

    def test_requires_an_input(self):
        with pytest.raises(SystemExit):
            cc.main([])


class TestOnlyAndFlag:
    def test_an_or_inside_an_and_is_not_only_and(self):
        r = cc.analyze(cc.parse_logic("H = A & (B | C)"), {}, 5000)
        assert r["only_and_logic"] is False and r["note"] is None
        assert r["minimal_cut_sets"] == [["A"], ["B", "C"]]

    def test_a_pure_conjunction_and_a_single_variable_are_only_and(self):
        assert cc.analyze(cc.parse_logic("A & B & C"), {}, 5000)["only_and_logic"] is True
        assert cc.analyze(cc.parse_logic("A"), {}, 5000)["only_and_logic"] is True

    def test_a_pure_disjunction_is_not_only_and(self):
        assert cc.analyze(cc.parse_logic("A | B"), {}, 5000)["only_and_logic"] is False


class TestCapAppliesToTheOutput:
    """Found by the automated Codex review of PR #491."""

    def test_a_parent_can_absorb_an_oversized_child_before_the_cap_applies(self):
        # The child (A & (B|C|D)) has 3 supports, above max_sets=2, but the whole claim is just A.
        r = cc.analyze(cc.parse_logic("A | (A & (B | C | D))"), {}, 2)
        assert r["status"] == "OK"
        assert r["minimal_support_sets"] == [["A"]] and r["minimal_cut_sets"] == [["A"]]

    def test_a_genuinely_large_output_is_still_truncated(self):
        r = cc.analyze(cc.parse_logic("(A | B | C) & (D | E | F)"), {}, 2)
        assert r["status"] == "TRUNCATED" and r["truncated"] is True and "kappa" not in r

    def test_the_public_cap_is_exact_for_the_final_family(self):
        fam = cc.supports(cc.parse_logic("A | B | C"), cap=3)
        assert len(fam) == 3
        with pytest.raises(cc.TooLarge):
            cc.supports(cc.parse_logic("A | B | C"), cap=2)
