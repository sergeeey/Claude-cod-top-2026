"""Tests for scripts/ach_quotient.py -- quotient view over an ACH matrix.

Every numeric expectation was derived by hand (see the comment on each case) before the
module was run. Synthetic fixtures verify the CODE only -- they say nothing about whether
the tool is useful on real data (that is the experiment's job, not this file's).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ach_quotient as aq  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "experiments" / "_template" / "ach_matrix.md"


def mx(hyps: list[str], rows: list[tuple[str, list[str], float | None]]) -> aq.Matrix:
    """rows: (test id, symbols per hypothesis, cost)."""
    return aq.Matrix(
        tuple(hyps),
        tuple(r[0] for r in rows),
        tuple(r[2] for r in rows),
        tuple(tuple(r[1]) for r in rows),
    )


def groups(m: aq.Matrix) -> set[frozenset[str]]:
    return {frozenset(c.members) for c in aq.compute_classes(m)}


# ---------------------------------------------------------------- parsing
MD = """# ach_matrix.md

## Competing Hypotheses
| ID | Hypothesis | Status |
|---|---|---|
| H1 | a | alive |

## Matrix
| Evidence / Test | Cost | H1 | H2 | H3 | Diagnostic? | Priority |
|---|---|---|---|---|---|---|
| T1 | 2 | C | C | I | yes | run next |
| T2 | 1 | I | I | C | yes | run next |
| T3 | 5 | **C** | n/a | C | no | deferred |

## Optional: Expected Information Gain
| x | y |
"""


class TestParsing:
    def test_markdown_table_parsed(self):
        m = aq.parse_ach_markdown(MD)
        assert m.hypotheses == ("H1", "H2", "H3")
        assert m.tests == ("T1", "T2", "T3")
        assert m.costs == (2.0, 1.0, 5.0)
        # `**C**` (markdown emphasis) is C; `n/a` is NA, a third distinct symbol.
        assert m.cells[2] == ("C", "NA", "C")

    def test_crlf_input_is_equivalent(self):
        assert aq.parse_ach_markdown(MD.replace("\n", "\r\n")) == aq.parse_ach_markdown(MD)

    def test_template_has_only_placeholders_so_data_is_insufficient(self):
        m = aq.parse_ach_markdown(TEMPLATE.read_text(encoding="utf-8"))
        assert m.n_rows == 0
        assert m.skipped_placeholder_rows >= 1
        assert aq.summarize(m)["status"] == "INSUFFICIENT_DATA"

    def test_bad_cell_is_an_error_not_silently_skipped(self):
        bad = MD.replace("| T2 | 1 | I | I | C |", "| T2 | 1 | I | maybe | C |")
        with pytest.raises(aq.MatrixParseError, match="maybe"):
            aq.parse_ach_markdown(bad)

    def test_no_matrix_section(self):
        with pytest.raises(aq.MatrixParseError):
            aq.parse_ach_markdown("# nothing here")

    def test_json_matrix(self):
        m = aq.parse_json_matrix(
            {
                "hypotheses": ["A", "B"],
                "tests": [{"id": "t", "cost": 3, "cells": {"A": "C", "B": "I"}}],
            }
        )
        assert m.cells == (("C", "I"),) and m.costs == (3.0,)

    def test_json_unknown_hypothesis_rejected(self):
        with pytest.raises(aq.MatrixParseError):
            aq.parse_json_matrix({"hypotheses": ["A"], "tests": [{"id": "t", "cells": {"Z": "C"}}]})


# ---------------------------------------------------------------- classes
class TestClasses:
    def test_identical_vectors_form_one_class(self):
        # H1 = H2 = (C, I, C, C); H3 = (I, C, C, I).
        # d_certain(H1, H3): rows where both known & differ: row1 C/I, row2 I/C, row4 C/I = 3.
        m = mx(
            ["H1", "H2", "H3"],
            [
                ("t1", ["C", "C", "I"], None),
                ("t2", ["I", "I", "C"], None),
                ("t3", ["C", "C", "C"], None),
                ("t4", ["C", "C", "I"], None),
            ],
        )
        s = aq.summarize(m)
        assert s["n_classes"] == 2 and s["qc"] == pytest.approx(1.5)
        assert s["n_nonsingleton_resolved"] == 1
        assert s["d_min"] == 3
        eq = [c for c in s["classes"] if c["status"] == "EQUIVALENT"]
        assert eq[0]["members"] == ("H1", "H2")

    def test_na_is_a_distinct_symbol_never_agreement(self):
        # H1 = (C, NA), H2 = (C, C): NOT equal, and compatible-but-unresolved (d_certain = 0).
        m = mx(["H1", "H2"], [("t1", ["C", "C"], None), ("t2", ["NA", "C"], None)])
        s = aq.summarize(m)
        assert s["n_classes"] == 2
        assert s["pair_relations"][0]["relation"] == "COMPATIBLE_UNRESOLVED"
        assert s["d_min"] == 0

    def test_all_na_columns_do_not_merge_with_known_columns(self):
        m = mx(
            ["H1", "H2", "H3"], [("t1", ["NA", "NA", "C"], None), ("t2", ["NA", "NA", "I"], None)]
        )
        by_member = {c.members: c for c in aq.compute_classes(m)}
        assert ("H1", "H2") in by_member and ("H3",) in by_member
        # identical but empty of commitments: below coverage threshold -> unresolved, not equivalent
        assert by_member[("H1", "H2")].status == "UNRESOLVED_LOW_COVERAGE"
        assert aq.summarize(m)["n_nonsingleton_resolved"] == 0

    def test_fragile_separation_is_one_certain_test(self):
        m = mx(["H1", "H2"], [("t1", ["C", "I"], None), ("t2", ["C", "C"], None)])
        assert aq.summarize(m)["pair_relations"][0]["relation"] == "FRAGILE_SEPARATION"

    def test_insufficient_inputs(self):
        assert aq.summarize(mx(["H1"], [("t", ["C"], None)]))["status"] == "INSUFFICIENT_DATA"
        assert aq.summarize(mx(["H1", "H2"], [("t", ["NA", "NA"], None)]))["status"] == (
            "INSUFFICIENT_DATA"
        )


# ---------------------------------------------------------------- identify
class TestIdentify:
    def test_minimum_cost_separating_set(self):
        # rows r1: A=C B=I C=I (1); r2: A=C B=C C=I (1); r3: A=I B=C C=C (5)
        # A-B separated by {r1, r3}; A-C by {r1, r2, r3}; B-C by {r2} only.
        # r2 is mandatory (B-C); A-B needs r1 or r3 (r1 cheaper) -> {r1, r2}, cost 2.
        m = mx(
            ["A", "B", "C"],
            [
                ("r1", ["C", "I", "I"], 1.0),
                ("r2", ["C", "C", "I"], 1.0),
                ("r3", ["I", "C", "C"], 5.0),
            ],
        )
        out = aq.identify(m)
        assert out["method"] == "exact"
        assert out["tests"] == ["r1", "r2"] and out["total_cost"] == 2.0
        assert out["unseparable_class_pairs"] == []

    def test_compatible_pairs_are_reported_not_forced(self):
        m = mx(["H1", "H2"], [("t1", ["C", "C"], None), ("t2", ["NA", "C"], None)])
        out = aq.identify(m)
        assert out["unseparable_class_pairs"] == [[["H1"], ["H2"]]]

    def test_unknown_cost_is_flagged(self):
        m = mx(["H1", "H2"], [("t1", ["C", "I"], None)])
        assert aq.identify(m)["cost_unknown_assumed_1"] is True


# ---------------------------------------------------------------- refine / essential / place
class TestRefineAndPlace:
    def base(self) -> aq.Matrix:
        return mx(
            ["H1", "H2", "H3"],
            [
                ("t1", ["C", "C", "I"], None),
                ("t2", ["I", "I", "C"], None),
            ],
        )  # classes: {H1,H2}, {H3}

    def test_candidate_that_splits_a_class_is_accepted(self):
        r = aq.candidate_refines(self.base(), {"H1": "C", "H2": "I", "H3": "C"})
        assert r["refines"] and r["splits_classes"] == [["H1", "H2"]]

    def test_candidate_that_splits_nothing_is_rejected(self):
        r = aq.candidate_refines(self.base(), {"H1": "C", "H2": "C", "H3": "I"})
        assert not r["refines"]
        assert r["verdict"] == "TEST REJECTED: cannot refine"

    def test_candidate_with_na_does_not_certainly_split(self):
        r = aq.candidate_refines(self.base(), {"H1": "C", "H2": "NA", "H3": "I"})
        assert not r["refines"]

    def test_candidate_resolves_a_compatible_pair(self):
        m = mx(["H1", "H2"], [("t1", ["C", "C"], None), ("t2", ["NA", "C"], None)])
        r = aq.candidate_refines(m, {"H1": "C", "H2": "I"})
        assert r["refines"] and r["resolves_compatible_pairs"] == [[["H1"], ["H2"]]]

    def test_unknown_hypothesis_in_candidate_rejected(self):
        with pytest.raises(ValueError):
            aq.candidate_refines(self.base(), {"Z": "C"})

    def test_leave_one_out_essentiality(self):
        m = mx(["H1", "H2"], [("sep", ["C", "I"], None), ("const", ["C", "C"], None)])
        assert aq.row_essential(m) == {"sep": True, "const": False}

    def test_place_existing_compatible_new(self):
        m = mx(["H1", "H2"], [("t1", ["C", "I"], None), ("t2", ["I", "NA"], None)])
        assert aq.place_candidate(m, {"t1": "C", "t2": "I"})["placement"] == "EXISTING_CLASS"
        assert aq.place_candidate(m, {"t1": "C", "t2": "C"})["placement"] == "NEW_CLASS"
        # (C, NA) vs H1=(C, I): agrees where both known -> compatible, not new, not merged
        assert (
            aq.place_candidate(m, {"t1": "C", "t2": "NA"})["placement"] == "COMPATIBLE_UNRESOLVED"
        )


# ---------------------------------------------------------------- decode
class TestDecode:
    def test_clean_observation_decodes(self):
        m = mx(["H1", "H2"], [(f"t{i}", ["C", "I"], None) for i in range(5)])
        out = aq.decode(m, {f"t{i}": "C" for i in range(5)})
        assert out["decision"] == "DECODED" and out["class"] == ["H1"]

    def test_corrects_up_to_radius_errors(self):
        # d = 5 -> radius 2; two flipped bits (t0, t1) still decode to H1.
        m = mx(["H1", "H2"], [(f"t{i}", ["C", "I"], None) for i in range(5)])
        obs = {"t0": "I", "t1": "I", "t2": "C", "t3": "C", "t4": "C"}
        assert aq.decode(m, obs)["decision"] == "DECODED"

    def test_all_erased_is_a_tie_not_a_guess(self):
        m = mx(["H1", "H2"], [(f"t{i}", ["C", "I"], None) for i in range(3)])
        assert aq.decode(m, {})["decision"] == "AMBIGUOUS_TIE"

    def test_far_from_every_class_is_uncorrectable(self):
        # H1 = (C,C,C,C), H2 = (C,C,I,I): d_min = 2 -> radius 0.
        # obs = (I,I,C,C): 2 disagreements with H1 (> radius 0), 4 with H2 -> UNCORRECTABLE.
        m = mx(
            ["H1", "H2"],
            [
                ("t1", ["C", "C"], None),
                ("t2", ["C", "C"], None),
                ("t3", ["C", "I"], None),
                ("t4", ["C", "I"], None),
            ],
        )
        out = aq.decode(m, {"t1": "I", "t2": "I", "t3": "C", "t4": "C"})
        assert out["decision"] == "UNCORRECTABLE"
        assert out["class"] == ["H1"] and out["radius"] == 0

    @staticmethod
    def erasure_matrix() -> aq.Matrix:
        # H1 = (C,C,C,NA), H2 = (I,I,I,C): d_certain = 3 (rows 1-3), so radius = 1.
        # Row 4 is NOT a certain separator (H1 makes no prediction there) but an observed I
        # there counts against H2 only -> H1 is the strict nearest class without any tie.
        return mx(
            ["H1", "H2"],
            [
                ("r1", ["C", "I"], None),
                ("r2", ["C", "I"], None),
                ("r3", ["C", "I"], None),
                ("r4", ["NA", "C"], None),
            ],
        )

    def test_pairwise_erasure_bound_is_strict(self):
        # obs: r1=I (error vs H1), r2 erased, r3=C (agrees), r4=I.
        # H1 disagreements 1 (<= radius 1), H2 disagreements 2 -> best is H1, no tie.
        # On the separating set {r1,r2,r3}: e = 1, s = 1, d = 3 -> 2e + s = 3, NOT < 3.
        # The radius check alone would accept this; the pairwise bound must refuse it.
        out = aq.decode(self.erasure_matrix(), {"r1": "I", "r3": "C", "r4": "I"})
        assert out["decision"] == "UNCORRECTABLE"
        assert out["class"] == ["H1"] and out["errors_vs_class"] == 1 and out["radius"] == 1
        assert out["failed_pair"] == {"vs": ["H2"], "d": 3, "e": 1, "s": 1}

    def test_one_erasure_less_decodes(self):
        # Same as above but r2 observed as C: e = 1, s = 0 -> 2 < 3 -> decodable.
        obs = {"r1": "I", "r2": "C", "r3": "C", "r4": "I"}
        assert aq.decode(self.erasure_matrix(), obs)["decision"] == "DECODED"

    def test_compatible_classes_cannot_be_decoded(self):
        m = mx(["H1", "H2"], [("t1", ["C", "C"], None), ("t2", ["NA", "C"], None)])
        assert aq.decode(m, {"t1": "C", "t2": "C"})["decision"] == "AMBIGUOUS_COMPATIBLE"

    def test_unknown_test_in_observation_rejected(self):
        m = mx(["H1", "H2"], [("t1", ["C", "I"], None)])
        with pytest.raises(ValueError):
            aq.decode(m, {"zzz": "C"})


# ---------------------------------------------------------------- floor (shuffle null)
class TestFloor:
    def test_constant_rows_always_merge_so_floor_is_reached(self):
        m = mx(["H1", "H2"], [("t", ["C", "C"], None)])
        out = aq.floor_null(m, trials=200, seed=1)
        assert out["observed_nonsingleton_resolved"] == 1
        assert out["p_ge_observed"] == 1.0 and out["exceeds_floor"] is False

    def test_sparse_matrix_merges_by_chance_so_it_does_not_exceed_floor(self):
        # Observed H1 == H2; but each row has a single I among 5 cells, so any pair of columns is
        # identical across 4 rows with prob (3/5)^4 ~ 0.13: chance alone merges columns often.
        m = mx(
            ["H1", "H2", "H3", "H4", "H5"],
            [
                ("r1", ["C", "C", "I", "C", "C"], None),
                ("r2", ["C", "C", "C", "I", "C"], None),
                ("r3", ["C", "C", "C", "C", "I"], None),
                ("r4", ["C", "C", "I", "C", "C"], None),
            ],
        )
        out = aq.floor_null(m, trials=2000, seed=3)
        assert out["observed_nonsingleton_resolved"] == 1
        assert out["p_ge_observed"] > 0.3 and out["exceeds_floor"] is False

    def test_a_duplicate_among_many_rows_exceeds_floor(self):
        import random

        rng = random.Random(1)
        rows = []
        for i in range(12):
            first = rng.choice(["C", "I"])
            rest = [rng.choice(["C", "I"]) for _ in range(6)]
            rows.append((f"r{i}", [first, first, *rest], None))
        m = mx([f"H{k}" for k in range(1, 9)], rows)
        out = aq.floor_null(m, trials=3000, seed=11)
        assert out["observed_nonsingleton_resolved"] >= 1
        assert out["exceeds_floor"] is True and out["p_ge_observed"] <= 0.05

    def test_floor_is_seed_deterministic(self):
        m = mx(["H1", "H2", "H3"], [("a", ["C", "I", "C"], None), ("b", ["I", "C", "C"], None)])
        assert aq.floor_null(m, 300, 5) == aq.floor_null(m, 300, 5)

    def test_floor_reports_insufficient(self):
        assert aq.floor_null(mx(["H1"], [("t", ["C"], None)]))["status"] == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------- metamorphic properties (EMT on ourselves)
sym = st.sampled_from(["C", "I", "NA"])


@st.composite
def matrices(draw: st.DrawFn) -> aq.Matrix:
    n_h = draw(st.integers(2, 6))
    n_t = draw(st.integers(1, 6))
    rows = [(f"t{i}", [draw(sym) for _ in range(n_h)], None) for i in range(n_t)]
    return mx([f"H{j}" for j in range(n_h)], rows)


class TestMetamorphicProperties:
    @settings(max_examples=150, deadline=None)
    @given(matrices(), st.randoms(use_true_random=False))
    def test_hypothesis_order_does_not_change_the_partition(self, m, rnd):
        order = list(range(len(m.hypotheses)))
        rnd.shuffle(order)
        permuted = aq.Matrix(
            tuple(m.hypotheses[j] for j in order),
            m.tests,
            m.costs,
            tuple(tuple(row[j] for j in order) for row in m.cells),
        )
        assert groups(permuted) == groups(m)

    @settings(max_examples=150, deadline=None)
    @given(matrices(), st.randoms(use_true_random=False))
    def test_test_order_does_not_change_the_partition(self, m, rnd):
        order = list(range(m.n_rows))
        rnd.shuffle(order)
        permuted = aq.Matrix(
            m.hypotheses,
            tuple(m.tests[i] for i in order),
            tuple(m.costs[i] for i in order),
            tuple(m.cells[i] for i in order),
        )
        assert groups(permuted) == groups(m)

    @settings(max_examples=150, deadline=None)
    @given(matrices(), st.integers(0, 5))
    def test_duplicating_a_column_adds_a_hypothesis_but_no_class(self, m, which):
        j = which % len(m.hypotheses)
        dup = aq.Matrix(
            (*m.hypotheses, "DUP"),
            m.tests,
            m.costs,
            tuple((*row, row[j]) for row in m.cells),
        )
        assert len(dup.hypotheses) == len(m.hypotheses) + 1
        assert len(aq.compute_classes(dup)) == len(aq.compute_classes(m))

    @settings(max_examples=150, deadline=None)
    @given(matrices(), st.lists(sym, min_size=6, max_size=6))
    def test_adding_a_test_only_refines_the_partition(self, m, extra):
        extra = extra[: len(m.hypotheses)]
        bigger = aq.Matrix(
            m.hypotheses,
            (*m.tests, "new"),
            (*m.costs, None),
            (*m.cells, tuple(extra)),
        )
        old = groups(m)
        new = groups(bigger)
        assert len(new) >= len(old)
        for g in new:  # every new group sits inside one old group
            assert any(g <= o for o in old)

    @settings(max_examples=150, deadline=None)
    @given(matrices())
    def test_d_certain_is_symmetric_and_nonnegative(self, m):
        cls = aq.compute_classes(m)
        for a in cls:
            for b in cls:
                assert aq.d_certain(a.vector, b.vector) == aq.d_certain(b.vector, a.vector) >= 0

    @settings(max_examples=150, deadline=None)
    @given(matrices())
    def test_an_all_na_column_never_joins_a_column_with_a_known_cell(self, m):
        extra = aq.Matrix(
            (*m.hypotheses, "EMPTY"),
            m.tests,
            m.costs,
            tuple((*row, "NA") for row in m.cells),
        )
        for c in aq.compute_classes(extra):
            if "EMPTY" in c.members and len(c.members) > 1:
                assert all(s == "NA" for s in c.vector)


class TestMutationSensitivity:
    """A property test that cannot fail proves nothing: show a plausible bug is caught."""

    @staticmethod
    def mutant_classes(m: aq.Matrix) -> int:
        # BUG: treats NA as agreement with a default 'C' before grouping.
        seen = {
            tuple("C" if s == "NA" else s for s in m.column(j)) for j in range(len(m.hypotheses))
        }
        return len(seen)

    def test_the_na_equals_agreement_mutant_is_distinguishable(self):
        m = mx(["H1", "H2"], [("t1", ["C", "C"], None), ("t2", ["NA", "C"], None)])
        assert len(aq.compute_classes(m)) == 2  # real implementation
        assert self.mutant_classes(m) == 1  # the mutant merges them -> this test would catch it


# ---------------------------------------------------------------- CLI
class TestCli:
    def write(self, tmp_path: Path, text: str) -> Path:
        p = tmp_path / "ach_matrix.md"
        p.write_text(text, encoding="utf-8")
        return p

    def test_classes_json(self, tmp_path, capsys):
        rc = aq.main(["classes", str(self.write(tmp_path, MD)), "--json"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "OK" and out["n_hypotheses"] == 3

    def test_template_reports_insufficient_data_and_exits_zero(self, capsys):
        assert aq.main(["classes", str(TEMPLATE), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "INSUFFICIENT_DATA"

    def test_parse_error_exits_two(self, tmp_path, capsys):
        bad = MD.replace("| T2 | 1 | I | I | C |", "| T2 | 1 | I | maybe | C |")
        assert aq.main(["classes", str(self.write(tmp_path, bad))]) == 2
        assert "maybe" in capsys.readouterr().err

    def test_refine_and_decode_via_cli(self, tmp_path, capsys):
        p = self.write(tmp_path, MD)
        assert (
            aq.main(["refine", str(p), "--candidate", '{"H1":"C","H2":"I","H3":"C"}', "--json"])
            == 0
        )
        assert json.loads(capsys.readouterr().out)["verdict"] in {
            "ACCEPT",
            "TEST REJECTED: cannot refine",
        }
        assert aq.main(["decode", str(p), "--observation", '{"T1":"C","T2":"I"}', "--json"]) == 0


# ---------------------------------------------------------------- regressions from the 2026-10-01 review
class TestReviewRegressions:
    """Each case was reproduced with a concrete input before being fixed."""

    def test_decode_radius_is_the_best_class_not_the_global_closest_pair(self):
        # H2 and H3 are compatible (d_certain 0) but far from H1: an observation that IS H1
        # must decode to H1, not UNCORRECTABLE because of an unrelated close pair.
        m = mx(
            ["H1", "H2", "H3"],
            [
                ("T1", ["C", "I", "I"], 1),
                ("T2", ["C", "I", "I"], 1),
                ("T3", ["C", "I", "NA"], 1),
            ],
        )
        out = aq.decode(m, {"T1": "C", "T2": "C", "T3": "C"})
        assert out["decision"] == "DECODED" and out["class"] == ["H1"]
        assert out["d_best"] == 2 and out["radius"] == 0 and out["d_min"] == 0

    def test_greedy_identify_takes_a_free_test_that_separates_something(self):
        hyps = ["A", "B", "C"]
        rows = [("r0", ["C", "I", "I"], 1)]
        rows += [(f"r{i}", ["C", "C", "C"], 1) for i in range(1, 12)]
        rows += [("r12", ["C", "C", "I"], 0)]  # free; the only test separating B from C
        out = aq.identify(mx(hyps, rows))
        assert out["method"] == "greedy"
        assert set(out["tests"]) == {"r0", "r12"}

    def test_place_candidate_rejects_unknown_test_ids(self):
        m = mx(["H1", "H2"], [("T1", ["C", "I"], 1)])
        with pytest.raises(ValueError, match="unknown tests"):
            aq.place_candidate(m, {"T1": "C", "TYPO": "I"})

    def test_floor_needs_at_least_one_trial(self):
        m = mx(["H1", "H2"], [("T1", ["C", "I"], 1)])
        with pytest.raises(ValueError, match="trials"):
            aq.floor_null(m, trials=0)

    def test_mixed_case_na_is_a_valid_symbol_not_a_dropped_row(self):
        md = "## Matrix\n| Test | H1 | H2 |\n|---|---|---|\n| T1 | C | I |\n| T2 | N/a | C |\n"
        assert aq.parse_ach_markdown(md).tests == ("T1", "T2")

    def test_a_row_mixing_valid_and_unparseable_cells_raises(self):
        md = "## Matrix\n| Test | H1 | H2 |\n|---|---|---|\n| T1 | C | I |\n| T2 | C/I | C |\n"
        with pytest.raises(aq.MatrixParseError):
            aq.parse_ach_markdown(md)

    def test_an_all_placeholder_template_row_is_still_skipped(self):
        md = "## Matrix\n| Test | H1 | H2 |\n|---|---|---|\n| T1 | C | I |\n| T2 | C/I/N/A | C/I/N/A |\n"
        assert aq.parse_ach_markdown(md).tests == ("T1",)

    def test_duplicate_test_ids_are_rejected_like_duplicate_hypotheses(self):
        md = "## Matrix\n| Test | H1 | H2 |\n|---|---|---|\n| T1 | C | I |\n| T1 | I | C |\n"
        with pytest.raises(aq.MatrixParseError, match="duplicate test"):
            aq.parse_ach_markdown(md)
        with pytest.raises(aq.MatrixParseError, match="duplicate test"):
            aq.parse_json_matrix(
                {
                    "hypotheses": ["A", "B"],
                    "tests": [{"id": "T", "cells": {"A": "C"}}, {"id": "T", "cells": {"B": "I"}}],
                }
            )
