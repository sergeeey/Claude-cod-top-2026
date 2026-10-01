"""Tests for scripts/eig_calculator.py -- Expected Information Gain for ach_matrix.md.

Every numeric expectation here was hand-derived independently (not copied from the
module under test) before this file was written -- see the comment on each test for
the derivation, matching audit-verification-gate.md's "agent's [VERIFIED] = your
[INFERRED]" discipline applied to my own code, not just an agent's.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eig_calculator import EIGInputError, expected_information_gain  # noqa: E402


class TestWorkedExamples:
    """The two examples from the 2026-09-14 pearl_registry entry, reproduced here
    as executable checks instead of prose someone could silently drift from."""

    def test_strong_discriminating_test(self):
        # Hand derivation: P(pos)=P(neg)=0.5 by symmetry.
        # H1,pos: 0.5*0.9*log2(0.9/0.5) = 0.45*log2(1.8) = 0.45*0.847997 = 0.381599
        # H1,neg: 0.5*0.1*log2(0.1/0.5) = 0.05*log2(0.2) = 0.05*(-2.321928) = -0.116096
        # H2,pos: 0.5*0.1*log2(0.1/0.5) = -0.116096 (symmetric to H1,neg)
        # H2,neg: 0.5*0.9*log2(0.9/0.5) = 0.381599 (symmetric to H1,pos)
        # sum = 0.381599 - 0.116096 - 0.116096 + 0.381599 = 0.531007
        result = expected_information_gain(
            {"H1": 0.5, "H2": 0.5},
            {"H1": {"pos": 0.9, "neg": 0.1}, "H2": {"pos": 0.1, "neg": 0.9}},
        )
        assert result.eig_bits == pytest.approx(0.531007, abs=1e-5)

    def test_weak_discriminating_test(self):
        # Hand derivation: P(pos)=P(neg)=0.5 by symmetry.
        # H1,pos: 0.5*0.6*log2(0.6/0.5) = 0.3*log2(1.2) = 0.3*0.263034 = 0.078910
        # H1,neg: 0.5*0.4*log2(0.4/0.5) = 0.2*log2(0.8) = 0.2*(-0.321928) = -0.064386
        # H2,pos: 0.5*0.4*log2(0.4/0.5) = -0.064386
        # H2,neg: 0.5*0.6*log2(0.6/0.5) = 0.078910
        # sum = 0.078910 - 0.064386 - 0.064386 + 0.078910 = 0.029048
        result = expected_information_gain(
            {"H1": 0.5, "H2": 0.5},
            {"H1": {"pos": 0.6, "neg": 0.4}, "H2": {"pos": 0.4, "neg": 0.6}},
        )
        assert result.eig_bits == pytest.approx(0.029048, abs=1e-5)

    def test_strong_test_beats_weak_test_by_roughly_18x(self):
        # Not a new claim -- restates the ratio the pearl_registry entry cites,
        # checked here so a future edit to either worked example is forced to
        # keep the comparison honest instead of drifting silently.
        strong = expected_information_gain(
            {"H1": 0.5, "H2": 0.5},
            {"H1": {"pos": 0.9, "neg": 0.1}, "H2": {"pos": 0.1, "neg": 0.9}},
        )
        weak = expected_information_gain(
            {"H1": 0.5, "H2": 0.5},
            {"H1": {"pos": 0.6, "neg": 0.4}, "H2": {"pos": 0.4, "neg": 0.6}},
        )
        ratio = strong.eig_bits / weak.eig_bits
        assert 15.0 < ratio < 22.0  # ~18.28x by hand; wide band, this isn't the precise claim


class TestEdgeCases:
    def test_identical_likelihoods_give_zero_gain(self):
        """A test where every hypothesis predicts the outcome identically cannot
        discriminate between them -- EIG must be exactly 0, not approximately."""
        result = expected_information_gain(
            {"H1": 0.5, "H2": 0.5},
            {"H1": {"pos": 0.5, "neg": 0.5}, "H2": {"pos": 0.5, "neg": 0.5}},
        )
        assert result.eig_bits == pytest.approx(0.0, abs=1e-9)

    def test_perfectly_separating_test_equals_prior_entropy(self):
        """A test that deterministically reveals which hypothesis is true collapses
        all uncertainty -- EIG must equal H(prior) exactly (here 1 bit, for a fair
        coin flip between two equally likely hypotheses). This is the textbook
        upper bound: no test can be MORE informative than the entropy already in
        the prior, and a perfectly diagnostic test achieves exactly that bound."""
        result = expected_information_gain(
            {"H1": 0.5, "H2": 0.5},
            {"H1": {"a": 1.0, "b": 0.0}, "H2": {"a": 0.0, "b": 1.0}},
        )
        assert result.eig_bits == pytest.approx(1.0, abs=1e-9)

    def test_skewed_prior_perfectly_separating_test_equals_that_entropy(self):
        """Same perfectly-separating structure, but an unequal prior -- EIG must
        equal the BINARY ENTROPY of the skewed prior (0.2/0.8), not 1 bit. This
        catches a bug class the two 50/50 tests above cannot: an implementation
        that silently assumes a uniform prior anywhere in the calculation."""
        p = 0.2
        expected_bits = -(p * math.log2(p) + (1 - p) * math.log2(1 - p))  # H(0.2) approx 0.7219
        result = expected_information_gain(
            {"H1": p, "H2": 1 - p},
            {"H1": {"a": 1.0, "b": 0.0}, "H2": {"a": 0.0, "b": 1.0}},
        )
        assert result.eig_bits == pytest.approx(expected_bits, abs=1e-9)

    def test_na_default_of_half_gives_zero_gain(self):
        """ach_matrix.md's own suggested default for 'N/A' (no discriminating
        power) is 0.5 for both hypotheses -- confirms that default is internally
        consistent with EIG=0, i.e. the qualitative N/A and the quantitative
        default agree on 'this test tells you nothing', not just by convention."""
        result = expected_information_gain(
            {"H1": 0.5, "H2": 0.5},
            {"H1": {"pos": 0.5, "neg": 0.5}, "H2": {"pos": 0.5, "neg": 0.5}},
        )
        assert result.eig_bits == pytest.approx(0.0, abs=1e-9)

    def test_independent_derivation_via_entropy_route(self):
        """Skeptic-found (2026-09-14): every other test's expectation was derived
        by the SAME double-sum formula the code implements -- a bug in the formula
        itself, not just its coding, would pass all of them. This test computes
        the expectation via a genuinely different route: I(H;O) = H(O) - H(O|H),
        entropy of the marginal minus the prior-weighted average conditional
        entropy, coded independently in this test, not imported from the module.

        Inputs: priors {H1:0.3, H2:0.7}, H1{pos:.8,neg:.2}, H2{pos:.3,neg:.7}.
        marginal: P(pos)=0.3*0.8+0.7*0.3=0.45, P(neg)=0.55.
        H(O) = -(0.45*log2(0.45) + 0.55*log2(0.55)) = 0.992774
        H(O|H1) = -(0.8*log2(0.8) + 0.2*log2(0.2)) = 0.721928
        H(O|H2) = -(0.3*log2(0.3) + 0.7*log2(0.7)) = 0.881291
        H(O|H) = 0.3*0.721928 + 0.7*0.881291 = 0.833482
        I(H;O) = 0.992774 - 0.833482 = 0.159292
        """

        def _h2(p: float) -> float:
            if p <= 0.0 or p >= 1.0:
                return 0.0
            return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))

        priors = {"H1": 0.3, "H2": 0.7}
        likelihoods = {"H1": {"pos": 0.8, "neg": 0.2}, "H2": {"pos": 0.3, "neg": 0.7}}
        p_pos = sum(priors[h] * likelihoods[h]["pos"] for h in priors)
        h_o = _h2(p_pos)
        h_o_given_h = sum(priors[h] * _h2(likelihoods[h]["pos"]) for h in priors)
        expected = h_o - h_o_given_h

        result = expected_information_gain(priors, likelihoods)
        assert result.eig_bits == pytest.approx(expected, abs=1e-6)
        assert result.eig_bits == pytest.approx(0.159292, abs=1e-5)

    def test_result_is_independent_of_caller_dict_mutation(self):
        """Skeptic-found (2026-09-14): EIGResult.likelihoods was a shallow copy --
        the inner {outcome: p} dicts stayed shared with the caller's own objects,
        so @dataclass(frozen=True) looked immutable while actually being mutable
        through its own stored reference."""
        priors = {"H1": 0.5, "H2": 0.5}
        likelihoods = {"H1": {"pos": 0.9, "neg": 0.1}, "H2": {"pos": 0.1, "neg": 0.9}}
        result = expected_information_gain(priors, likelihoods)

        priors["H1"] = 0.9  # mutate the caller's own dict after the call
        likelihoods["H1"]["pos"] = 0.01
        result.likelihoods["H2"]["pos"] = 0.99  # mutate the result's own stored dict

        assert result.priors == {"H1": 0.5, "H2": 0.5}, "caller mutation leaked into result"
        assert likelihoods["H1"]["pos"] == 0.01, "mutating the caller's dict is fine"
        # the result's OWN copy must not have been the same object we just mutated
        # via `likelihoods["H1"]["pos"] = 0.01` above:
        assert result.likelihoods["H1"]["pos"] == 0.9

    def test_three_hypotheses_not_just_binary(self):
        """The formula and this implementation are not special-cased to exactly
        two hypotheses -- confirm with three, one of which the test does not
        discriminate from the others (H3 has the same likelihood as H1)."""
        result = expected_information_gain(
            {"H1": 1 / 3, "H2": 1 / 3, "H3": 1 / 3},
            {
                "H1": {"pos": 0.9, "neg": 0.1},
                "H2": {"pos": 0.1, "neg": 0.9},
                "H3": {"pos": 0.9, "neg": 0.1},  # identical to H1 -- test can't tell them apart
            },
        )
        # Sanity bounds, not a precise hand-derivation: must discriminate H1/H3 from
        # H2 (EIG > 0), but less than the 2-hypothesis strong case since H1 vs H3 is
        # invisible to this test -- an undiscriminated pair only dilutes information.
        assert 0.0 < result.eig_bits < 0.531007

    def test_returns_marginal_and_inputs_for_audit(self):
        """EIGResult must carry enough state to audit the number later without
        re-deriving it -- audit-verification-gate.md discipline applied to this
        module's own output, not just to agent claims."""
        priors = {"H1": 0.5, "H2": 0.5}
        likelihoods = {"H1": {"pos": 0.9, "neg": 0.1}, "H2": {"pos": 0.1, "neg": 0.9}}
        result = expected_information_gain(priors, likelihoods)
        assert result.priors == priors
        assert result.likelihoods == likelihoods
        assert result.marginal_outcome["pos"] == pytest.approx(0.5, abs=1e-9)
        assert result.marginal_outcome["neg"] == pytest.approx(0.5, abs=1e-9)


class TestInputValidation:
    """The gating rule this whole module exists to enforce is a HUMAN discipline
    (don't invent probabilities) that no code can check -- but the code CAN and
    must reject inputs that are not even valid probability distributions, which
    is a different, narrower, and fully mechanical check."""

    def test_priors_must_sum_to_one(self):
        with pytest.raises(EIGInputError, match="priors must sum to 1.0"):
            expected_information_gain(
                {"H1": 0.5, "H2": 0.6},
                {"H1": {"pos": 0.5, "neg": 0.5}, "H2": {"pos": 0.5, "neg": 0.5}},
            )

    def test_likelihood_row_must_sum_to_one(self):
        with pytest.raises(EIGInputError, match=r"likelihoods\['H1'\] must sum to 1.0"):
            expected_information_gain(
                {"H1": 0.5, "H2": 0.5},
                {"H1": {"pos": 0.9, "neg": 0.9}, "H2": {"pos": 0.5, "neg": 0.5}},
            )

    def test_hypothesis_sets_must_match(self):
        with pytest.raises(EIGInputError, match="must name the same hypotheses"):
            expected_information_gain(
                {"H1": 0.5, "H2": 0.5},
                {"H1": {"pos": 0.5, "neg": 0.5}, "H3": {"pos": 0.5, "neg": 0.5}},
            )

    def test_outcome_sets_must_match_across_hypotheses(self):
        """An outcome must mean the same thing under every hypothesis to be
        summed over -- {'pos','neg'} for H1 and {'yes','no'} for H2 is a modeling
        error (probably a typo), not a case this function can silently paper over."""
        with pytest.raises(EIGInputError, match="SAME outcome"):
            expected_information_gain(
                {"H1": 0.5, "H2": 0.5},
                {"H1": {"pos": 0.5, "neg": 0.5}, "H2": {"yes": 0.5, "no": 0.5}},
            )

    def test_negative_probability_rejected(self):
        # WHY match= (skeptic-found, 2026-09-14): a bare pytest.raises(EIGInputError)
        # passes for ANY reason the call fails, including an unrelated bug that
        # happens to also raise EIGInputError -- this pins the failure to the
        # actual out-of-bounds value, not just "some EIGInputError was raised".
        with pytest.raises(EIGInputError, match=r"H1'\] = 1.1 is not a valid probability"):
            expected_information_gain(
                {"H1": 1.1, "H2": -0.1},  # sums to 1.0 -- must be caught by the per-value bound
                {"H1": {"pos": 0.5, "neg": 0.5}, "H2": {"pos": 0.5, "neg": 0.5}},
            )

    def test_nan_prior_rejected_not_silently_propagated(self):
        """Skeptic-found (2026-09-14): before this fix, `abs(nan - 1.0) > tol` and
        `nan < 0.0` are both False in Python, so a NaN prior passed validation
        silently and produced a NaN EIGResult instead of an error. NaN is a
        realistic input, not a hypothetical one -- it's what 0/0 from an empty
        historical bucket looks like, i.e. exactly the "empirically measured
        rate" this module's own gating rule tells callers to use."""
        with pytest.raises(EIGInputError, match="not a finite number"):
            expected_information_gain(
                {"H1": float("nan"), "H2": 0.5},
                {"H1": {"pos": 0.5, "neg": 0.5}, "H2": {"pos": 0.5, "neg": 0.5}},
            )

    def test_single_hypothesis_rejected(self):
        """Skeptic-found (2026-09-14): a single hypothesis is valid as a probability
        distribution (trivially sums to 1) but has nothing to discriminate --
        ach_matrix.md's own header says exactly this ("a 1-column matrix has
        nothing to discriminate"). Silently returning EIG=0 would be correct
        arithmetic and a useless answer to a malformed question."""
        with pytest.raises(EIGInputError, match="need >=2 hypotheses"):
            expected_information_gain({"H1": 1.0}, {"H1": {"pos": 0.5, "neg": 0.5}})

    def test_value_just_over_one_from_float_roundoff_is_tolerated(self):
        """Skeptic-found (2026-09-14): the first version checked the per-value
        bound EXACTLY ([0.0, 1.0]) while the sum check used a 1e-6 tolerance --
        a value like 1.0000000001, the kind of thing float roundoff in an
        upstream normalization produces, failed the strict per-value check while
        being fine by the sum check's own standard. One tolerance, applied to
        both, closes that inconsistency."""
        result = expected_information_gain(
            {"H1": 1.0000000001, "H2": -0.0000000001},
            {"H1": {"pos": 0.5, "neg": 0.5}, "H2": {"pos": 0.5, "neg": 0.5}},
        )
        assert result.eig_bits == pytest.approx(0.0, abs=1e-6)


class TestCLI:
    """Skeptic-found (2026-09-14): the CLI's --priors/--likelihoods path (added
    in response to the same finding) had zero test coverage of its own -- only
    the library function and the --demo path were tested."""

    def test_priors_and_likelihoods_flags_compute_real_input(self):
        import subprocess
        import sys as _sys

        proc = subprocess.run(
            [
                _sys.executable,
                "scripts/eig_calculator.py",
                "--priors",
                '{"H1":0.5,"H2":0.5}',
                "--likelihoods",
                '{"H1":{"pos":0.9,"neg":0.1},"H2":{"pos":0.1,"neg":0.9}}',
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert proc.returncode == 0, proc.stderr
        assert "0.5310" in proc.stdout

    def test_invalid_input_exits_nonzero_with_message(self):
        import subprocess
        import sys as _sys

        proc = subprocess.run(
            [
                _sys.executable,
                "scripts/eig_calculator.py",
                "--priors",
                '{"H1":0.5,"H2":0.6}',
                "--likelihoods",
                '{"H1":{"pos":0.5,"neg":0.5},"H2":{"pos":0.5,"neg":0.5}}',
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert proc.returncode == 1
        assert "must sum to 1.0" in proc.stderr


class TestDemo:
    def test_demo_runs_without_error(self, capsys):
        """The --demo CLI path is what a human actually runs to sanity-check the
        module -- confirm it executes and prints both worked examples' numbers."""
        from eig_calculator import _demo

        _demo()
        out = capsys.readouterr().out
        assert "0.531" in out or "0.5310" in out
        assert "0.029" in out or "0.0290" in out


class TestEquivalentHypotheses:
    """2026-10-01 (epistemic-structure-layer W2): identical likelihood rows are ONE hypothesis.

    This replaces a "prediction" that the first plan draft made and that an adversarial
    review showed to be mathematically false: for exact-duplicate rows the EIG does NOT
    change when the priors are passed explicitly -- only the prior MASS changes when the
    priors were written as uniform over the listed hypotheses. Both facts are pinned here.
    """

    ROW = {"pos": 0.9, "neg": 0.1}
    OTHER = {"pos": 0.1, "neg": 0.9}

    def likelihoods(self):
        return {"H1": dict(self.ROW), "H1b": dict(self.ROW), "H2": dict(self.OTHER)}

    def test_finds_the_duplicate_group(self):
        from eig_calculator import find_equivalent_hypotheses

        assert find_equivalent_hypotheses(self.likelihoods()) == [["H1", "H1b"]]

    def test_distinct_rows_have_no_group(self):
        from eig_calculator import find_equivalent_hypotheses

        assert find_equivalent_hypotheses({"A": self.ROW, "B": self.OTHER}) == []

    def test_different_outcome_sets_are_never_equivalent(self):
        from eig_calculator import find_equivalent_hypotheses

        assert find_equivalent_hypotheses({"A": {"x": 1.0}, "B": {"y": 1.0}}) == []

    def test_merge_sums_prior_mass_and_leaves_eig_unchanged(self):
        from eig_calculator import merge_equivalent

        priors = {"H1": 0.25, "H1b": 0.25, "H2": 0.5}
        merged_p, merged_l, groups = merge_equivalent(priors, self.likelihoods())
        assert groups == [["H1", "H1b"]]
        assert merged_p == {"H1+H1b": pytest.approx(0.5), "H2": pytest.approx(0.5)}
        before = expected_information_gain(priors, self.likelihoods()).eig_bits
        after = expected_information_gain(merged_p, merged_l).eig_bits
        assert after == pytest.approx(before, abs=1e-12)
        # ... and equals the textbook strong-test value for two hypotheses at 0.5 / 0.5.
        assert after == pytest.approx(0.531007, abs=1e-5)

    def test_uniform_priors_over_a_duplicate_shift_the_mass_and_the_number(self):
        # Hand derivation. Uniform 1/3 over (H1, H1b, H2) -> class masses H1: 2/3, H2: 1/3.
        # P(pos) = 2/3*0.9 + 1/3*0.1 = 0.633333; P(neg) = 0.366667.
        #  H1/pos : 0.6   * log2(0.9/0.633333) = 0.6 * 0.5069  =  0.3041
        #  H1/neg : 0.0667* log2(0.1/0.366667) = 0.0667*(-1.8745) = -0.1250
        #  H2/pos : 0.0333* log2(0.1/0.633333) = 0.0333*(-2.6630) = -0.0888
        #  H2/neg : 0.3   * log2(0.9/0.366667) = 0.3 * 1.2955  =  0.3887   -> sum ~ 0.4791 bits
        # versus 0.5310 for the intended two-rival 0.5 / 0.5 prior.
        from eig_calculator import find_equivalent_hypotheses, prior_mass_warning

        uniform = {"H1": 1 / 3, "H1b": 1 / 3, "H2": 1 / 3}
        eig = expected_information_gain(uniform, self.likelihoods()).eig_bits
        assert eig == pytest.approx(0.4791, abs=2e-4)
        assert eig < 0.531007 - 0.05
        warning = prior_mass_warning(uniform, find_equivalent_hypotheses(self.likelihoods()))
        assert warning is not None and "uniform" in warning

    def test_no_warning_when_priors_were_deliberately_non_uniform(self):
        from eig_calculator import find_equivalent_hypotheses, prior_mass_warning

        explicit = {"H1": 0.25, "H1b": 0.25, "H2": 0.5}
        assert prior_mass_warning(explicit, find_equivalent_hypotheses(self.likelihoods())) is None

    def test_no_warning_without_duplicates(self):
        from eig_calculator import prior_mass_warning

        assert prior_mass_warning({"A": 0.5, "B": 0.5}, []) is None

    def test_cli_merge_flag_prints_the_merged_priors_and_same_eig(self):
        import subprocess
        import sys as _sys

        base = [
            _sys.executable,
            "scripts/eig_calculator.py",
            "--priors",
            '{"H1":0.25,"H1b":0.25,"H2":0.5}',
            "--likelihoods",
            '{"H1":{"pos":0.9,"neg":0.1},"H1b":{"pos":0.9,"neg":0.1},"H2":{"pos":0.1,"neg":0.9}}',
        ]
        cwd = str(Path(__file__).resolve().parent.parent)
        plain = subprocess.run(base, capture_output=True, text=True, cwd=cwd)
        merged = subprocess.run(
            [*base, "--merge-equivalent"], capture_output=True, text=True, cwd=cwd
        )
        assert plain.returncode == 0 and merged.returncode == 0
        assert "merged equivalent hypotheses" in merged.stdout
        eig = lambda out: [ln for ln in out.splitlines() if ln.startswith("EIG")][0]  # noqa: E731
        assert eig(plain.stdout) == eig(merged.stdout)

    def test_cli_warns_on_stderr_for_uniform_priors_with_a_duplicate(self):
        import subprocess
        import sys as _sys

        proc = subprocess.run(
            [
                _sys.executable,
                "scripts/eig_calculator.py",
                "--priors",
                '{"H1":0.3333333333333333,"H1b":0.3333333333333333,"H2":0.3333333333333334}',
                "--likelihoods",
                '{"H1":{"pos":0.9,"neg":0.1},"H1b":{"pos":0.9,"neg":0.1},"H2":{"pos":0.1,"neg":0.9}}',
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert proc.returncode == 0
        assert "warning:" in proc.stderr and "uniform" in proc.stderr


class TestMergeEquivalentValidation:
    """Found by the 2026-10-01 review: --merge-equivalent skipped the name check and crashed."""

    def test_mismatched_hypothesis_names_fail_cleanly_with_the_flag(self):
        import subprocess

        script = Path(__file__).resolve().parent.parent / "scripts" / "eig_calculator.py"
        for lk in (
            '{"H1":{"pos":0.9,"neg":0.1}}',
            '{"H1":{"pos":0.9,"neg":0.1},"H2":{"pos":0.1,"neg":0.9},"H3":{"pos":0.5,"neg":0.5}}',
        ):
            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--priors",
                    '{"H1":0.5,"H2":0.5}',
                    "--likelihoods",
                    lk,
                    "--merge-equivalent",
                ],
                capture_output=True,
                text=True,
            )
            assert r.returncode == 1 and "must name the same hypotheses" in r.stderr
            assert "Traceback" not in r.stderr


class TestMergedIdCollision:
    """Found by the automated Codex review of PR #491."""

    def test_a_merged_id_that_collides_with_an_existing_hypothesis_is_rejected(self):
        from eig_calculator import merge_equivalent

        priors = {"A": 0.2, "B": 0.3, "A+B": 0.5}
        rows = {
            "A": {"p": 0.9, "n": 0.1},
            "B": {"p": 0.9, "n": 0.1},
            "A+B": {"p": 0.2, "n": 0.8},
        }
        with pytest.raises(EIGInputError, match="collides"):
            merge_equivalent(priors, rows)

    def test_merging_without_a_collision_still_preserves_eig(self):
        from eig_calculator import merge_equivalent

        priors = {"A": 0.25, "B": 0.25, "C": 0.5}
        rows = {
            "A": {"p": 0.9, "n": 0.1},
            "B": {"p": 0.9, "n": 0.1},
            "C": {"p": 0.2, "n": 0.8},
        }
        before = expected_information_gain(priors, rows).eig_bits
        merged_priors, merged_rows, groups = merge_equivalent(priors, rows)
        assert groups == [["A", "B"]] and merged_priors["A+B"] == pytest.approx(0.5)
        assert expected_information_gain(merged_priors, merged_rows).eig_bits == pytest.approx(
            before
        )
