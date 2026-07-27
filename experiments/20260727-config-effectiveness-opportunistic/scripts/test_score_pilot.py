#!/usr/bin/env python3
"""Unit tests for score_pilot.py's statistics (paired_permutation_test,
leave_one_out) -- these directly determine the experiment's go/no-go verdict,
so a silent bug here would be the highest-impact possible error in this
experiment. Stdlib unittest, no pytest dependency required to run standalone.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_pilot import leave_one_out, paired_permutation_test  # noqa: E402


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
