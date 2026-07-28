#!/usr/bin/env python3
"""Unit tests for score_pilot.py's statistics (paired_permutation_test,
leave_one_out) -- these directly determine the experiment's go/no-go verdict,
so a silent bug here would be the highest-impact possible error in this
experiment. Stdlib unittest, no pytest dependency required to run standalone.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import score_pilot  # noqa: E402
from score_pilot import (  # noqa: E402
    BELOW_MCID,
    BETTER,
    NOT_SIGNIFICANT,
    WORSE,
    _safe_task_dir,
    classify_direction,
    leave_one_out,
    paired_permutation_test,
    resolve_blind_grades,
)


class TestPairedPermutationTest(unittest.TestCase):
    def test_all_zero_diffs_gives_zero_observed_and_high_p(self):
        diffs = [0, 0, 0, 0, 0, 0, 0, 0]
        observed, p = paired_permutation_test(diffs, n_perm=500, seed=1)
        self.assertEqual(observed, 0.0)
        self.assertGreater(p, 0.5)

    def test_all_positive_diffs_gives_low_p(self):
        # C always catches, A never does -- the strongest possible real signal.
        # At n=8, the true p is ~1/128=0.0078 (only all-same-sign permutations
        # are as extreme as observed) -- a 0.01 threshold sits too close to that
        # floor and flakes on RNG realization. Use a threshold with real margin
        # (0.05, ~6x the true value) rather than one riding the noise boundary.
        diffs = [1, 1, 1, 1, 1, 1, 1, 1]
        observed, p = paired_permutation_test(diffs, n_perm=2000, seed=1)
        self.assertEqual(observed, 1.0)
        self.assertLess(p, 0.05)

    def test_mixed_diffs_matches_manual_mean(self):
        diffs = [1, 0, 1, -1, 0, 1, 1, 0]
        observed, _ = paired_permutation_test(diffs, n_perm=100, seed=1)
        self.assertAlmostEqual(observed, sum(diffs) / len(diffs))

    def test_p_value_never_zero(self):
        diffs = [1, 1, 1, 1, 1, 1, 1, 1]
        _, p = paired_permutation_test(diffs, n_perm=50, seed=1)
        self.assertGreater(p, 0.0)


class TestLeaveOneOut(unittest.TestCase):
    def test_stable_result_reports_no_flips(self):
        # 7 positive, 1 zero -- removing any single task keeps the sign positive
        diffs = [1, 1, 1, 1, 1, 1, 1, 0]
        self.assertEqual(leave_one_out(diffs), [])

    def test_fragile_result_reports_flip_index(self):
        # exactly one +1 driving an otherwise-zero-sum population -- removing
        # that single task flips the sign from positive to zero/non-positive
        diffs = [1, 0, 0, -1]
        flips = leave_one_out(diffs)
        # removing index 0 (the sole +1) should flip away from the base sign
        self.assertIn(0, flips)

    def test_single_task_returns_none(self):
        self.assertIsNone(leave_one_out([1]))

    def test_two_tasks_evaluates_without_error(self):
        result = leave_one_out([1, -1])
        self.assertIsInstance(result, list)


class TestResolveBlindGrades(unittest.TestCase):
    """Covers the blind-grading fix added after an independent review flagged
    self-referential grading bias (2026-07-27) -- a bug here would silently
    mis-attribute grades to the wrong copy, corrupting every blind-graded
    task's result."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_log_root = score_pilot.LOG_ROOT
        score_pilot.LOG_ROOT = Path(self._tmpdir.name)

    def tearDown(self):
        score_pilot.LOG_ROOT = self._orig_log_root
        self._tmpdir.cleanup()

    def _write_mapping(self, task_id, mapping):
        task_dir = score_pilot.LOG_ROOT / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        with open(task_dir / "blind_mapping.json", "w") as f:
            json.dump(mapping, f)

    def test_correctly_translates_shuffled_mapping(self):
        # Output_1 was actually Copy C, Output_2 was A, Output_3 was B
        self._write_mapping("task-x", {"Output_1": "C", "Output_2": "A", "Output_3": "B"})
        catch_a, catch_b, catch_c = resolve_blind_grades("task-x", 1, 0, 1)
        # grader said Output_1=1 (that's C), Output_2=0 (that's A), Output_3=1 (that's B)
        self.assertEqual((catch_a, catch_b, catch_c), (0, 1, 1))

    def test_identity_mapping_passes_through_unchanged(self):
        self._write_mapping("task-y", {"Output_1": "A", "Output_2": "B", "Output_3": "C"})
        catch_a, catch_b, catch_c = resolve_blind_grades("task-y", 1, 0, 1)
        self.assertEqual((catch_a, catch_b, catch_c), (1, 0, 1))

    def test_missing_mapping_file_raises_clear_error(self):
        with self.assertRaises(SystemExit):
            resolve_blind_grades("nonexistent-task", 1, 0, 1)


class TestClassifyDirection(unittest.TestCase):
    """Regression coverage for classify_direction() -- external audit TEST-01
    (2026-07-28): the production fix existed (this function was pulled out of
    summarize() specifically to make it testable) but had zero direct test
    coverage. All 4 assertions verified empirically against the real function
    before being written here, not assumed.

    The case this function exists to fix: a prior version's
    `mcid_met = abs(risk_diff) >= MCID and p < 0.05` could not distinguish
    "standard beats comparator" from "standard LOSES to comparator" -- both
    satisfy a magnitude-only check. test_opposite_sign_same_magnitude_differs
    is the direct regression test for that exact bug.
    """

    def test_better_when_above_mcid_and_significant(self):
        self.assertEqual(classify_direction(0.3, 0.01), BETTER)

    def test_worse_when_below_negative_mcid_and_significant(self):
        self.assertEqual(classify_direction(-0.3, 0.01), WORSE)

    def test_opposite_sign_same_magnitude_differs(self):
        # WHY this is THE regression test: the original bug's magnitude-only
        # check (abs(risk_diff) >= MCID) gives the same True/True for these
        # two inputs -- it could not tell them apart. classify_direction()
        # must return two DIFFERENT labels here or the fix has regressed.
        better = classify_direction(0.3, 0.01)
        worse = classify_direction(-0.3, 0.01)
        self.assertNotEqual(better, worse)
        self.assertEqual(better, BETTER)
        self.assertEqual(worse, WORSE)

    def test_not_significant_when_magnitude_met_but_p_high(self):
        self.assertEqual(classify_direction(0.3, 0.5), NOT_SIGNIFICANT)

    def test_below_mcid_when_magnitude_not_met_even_if_p_low(self):
        # p=0.01 alone must NOT be enough -- magnitude gates first.
        self.assertEqual(classify_direction(0.05, 0.01), BELOW_MCID)

    def test_below_mcid_holds_for_small_negative_diff_too(self):
        self.assertEqual(classify_direction(-0.05, 0.01), BELOW_MCID)

    def test_boundary_at_exact_mcid_counts_as_met(self):
        # risk_diff == mcid exactly (not just >) must classify as BETTER,
        # confirming the >= (not >) comparison in the real function.
        self.assertEqual(classify_direction(0.2, 0.01, mcid=0.2), BETTER)

    def test_boundary_at_exact_negative_mcid_counts_as_met(self):
        self.assertEqual(classify_direction(-0.2, 0.01, mcid=0.2), WORSE)


class TestSafeTaskDir(unittest.TestCase):
    """Regression coverage for _safe_task_dir() -- external audit TEST-01
    (2026-07-28): path-containment logic existed in production but had zero
    direct traversal-rejection test. Behavior verified empirically against
    the real function before writing these assertions.
    """

    def test_normal_task_id_resolves_inside_log_root(self):
        result = _safe_task_dir("task01")
        self.assertEqual(result, (score_pilot.LOG_ROOT / "task01").resolve())

    def test_relative_traversal_rejected(self):
        with self.assertRaises(SystemExit):
            _safe_task_dir("../../../etc")

    def test_absolute_path_rejected(self):
        # WHY "/etc/passwd", not "C:/Windows/System32" (CI regression, found
        # live on PR #236's first push): a drive-letter path is absolute on
        # Windows but on POSIX (this repo's CI runs on ubuntu-latest) "C:" is
        # just a literal directory name, not a drive -- the path resolves
        # INSIDE LOG_ROOT instead of outside it, so no SystemExit is raised
        # and the test fails on Linux while passing on Windows. A leading "/"
        # is genuinely absolute on both platforms: on POSIX it's filesystem
        # root; on Windows (verified empirically before writing this) it
        # resolves to the current drive's root, still well outside a path
        # several directories deep under experiments/.../logs.
        with self.assertRaises(SystemExit):
            _safe_task_dir("/etc/passwd")

    def test_traversal_that_stays_contained_is_allowed(self):
        # "foo/../bar" resolves to LOG_ROOT/bar -- still inside LOG_ROOT, so
        # this is legitimately allowed; the guard is containment, not "no dots
        # anywhere in the string".
        result = _safe_task_dir("foo/../bar")
        self.assertEqual(result, (score_pilot.LOG_ROOT / "bar").resolve())


if __name__ == "__main__":
    unittest.main(verbosity=2)
