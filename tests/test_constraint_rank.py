"""Tests for skills/extensions/boyko-constraint-engine/scripts/constraint_rank.py.

Fixtures are deterministic toy tables with known answers (verified by hand), so these are
[VERIFIED-SYNTHETIC]: they test the arithmetic, not any real system.
"""

import importlib.util
import itertools
import pathlib

SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "skills"
    / "extensions"
    / "boyko-constraint-engine"
    / "scripts"
    / "constraint_rank.py"
)
spec = importlib.util.spec_from_file_location("constraint_rank", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def table(values: dict[tuple, float]) -> list[dict]:
    return [{"fixed": list(k), "value": v} for k, v in values.items()]


def additive(base, gains):
    names = list(gains)
    return {
        c: base + sum(gains[n] for n in c)
        for k in range(len(names) + 1)
        for c in itertools.combinations(names, k)
    }


def test_additive_two_constraints_shapley_equals_solo():
    runs = table(additive(0.5, {"A": 0.10, "B": 0.20}))
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "runs": runs})
    assert abs(r["total_gap"] - 0.30) < 1e-9
    assert abs(r["shapley"]["A"] - 0.10) < 1e-9
    assert abs(r["shapley"]["B"] - 0.20) < 1e-9
    assert abs(r["budget_ratio_sum_solo_over_total"] - 1.0) < 1e-9
    assert r["pairwise"]["A+B"]["kind"] == "additive"
    assert r["verdict"] == "MULTIPLE_CONSTRAINTS"
    assert r["priority"][0]["constraint"] == "B"


def test_overlapping_constraints_budget_ratio_exceeds_one():
    # Either fix alone captures the whole gain: solo gains sum to 2x the total gap.
    vals = {(): 0.5, ("A",): 0.8, ("B",): 0.8, ("A", "B"): 0.8}
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "runs": table(vals)})
    assert abs(r["budget_ratio_sum_solo_over_total"] - 2.0) < 1e-9
    assert r["pairwise"]["A+B"]["kind"].startswith("overlapping")
    assert abs(r["shapley"]["A"] - 0.15) < 1e-9  # efficiency: shares sum to the gap


def test_complementary_constraints_have_no_solo_effect():
    vals = {(): 0.5, ("A",): 0.5, ("B",): 0.5, ("A", "B"): 0.9}
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "runs": table(vals)})
    assert r["pairwise"]["A+B"]["kind"].startswith("complementary")
    assert r["verdict"] == "NO_SINGLE_BOTTLENECK_FOUND"


def test_masked_constraint_detected():
    # A does nothing alone (B masks it) but gains once B is fixed.
    vals = {(): 0.5, ("A",): 0.5, ("B",): 0.7, ("A", "B"): 0.9}
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "runs": table(vals)})
    assert any(m.startswith("A (hidden behind B)") for m in r["masked"])


def test_single_dominant():
    runs = table(additive(0.5, {"A": 0.30, "B": 0.02}))
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "runs": runs})
    assert r["verdict"] == "SINGLE_DOMINANT"


def test_null_system_returns_no_constraint():
    runs = table(additive(0.5, {"A": 0.002, "B": -0.003}))
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "runs": runs})
    assert r["verdict"] == "NO_CONSTRAINT_DETECTED"


def test_not_measured_is_missing_not_zero():
    runs = table(additive(0.5, {"A": 0.10, "B": 0.20}))
    for run in runs:
        if run["fixed"] == ["A", "B"]:
            run["value"] = None
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "runs": runs})
    assert r["not_measured_runs"] == 1
    assert r["total_gap"] is None
    assert r["verdict"] == "UNDEFINED"
    assert r["shapley"] is None


def test_unknown_noise_caps_the_claim():
    runs = table(additive(0.5, {"A": 0.10, "B": 0.20}))
    r = mod.rank({"constraints": ["A", "B"], "runs": runs})
    assert r["verdict"] == "UNCLASSIFIED"
    assert r["pairwise"]["A+B"]["kind"].startswith("unclassified")


def test_lower_is_better_flips_sign():
    vals = {(): 10.0, ("A",): 6.0, ("B",): 9.0, ("A", "B"): 5.0}
    r = mod.rank(
        {"constraints": ["A", "B"], "higher_is_better": False, "noise": 0.1, "repeats": 4, "runs": table(vals)}
    )
    assert abs(r["solo_gain"]["A"] - 4.0) < 1e-9


def test_gray_zone_below_mcid():
    runs = table(additive(0.5, {"A": 0.30, "B": 0.02}))
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "mcid": 0.05, "runs": runs})
    assert r["gray_zone"] == ["B"]


def test_cost_changes_priority_order():
    runs = table(additive(0.5, {"A": 0.20, "B": 0.10}))
    r = mod.rank(
        {"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "costs": {"A": 10, "B": 1}, "runs": runs}
    )
    assert r["priority"][0]["constraint"] == "B"


def test_substitutes_are_not_called_single_dominant():
    # Two substitutes each reach 70% of the gap alone; they overlap, neither is "the" bottleneck.
    vals = {(): 0.50, ("A",): 0.57, ("B",): 0.57, ("A", "B"): 0.60}
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.002, "repeats": 4, "runs": table(vals)})
    assert r["verdict"] == "MULTIPLE_CONSTRAINTS"
    assert r["pairwise"]["A+B"]["kind"].startswith("overlapping")
    assert abs(r["shapley"]["A"] - 0.05) < 1e-9


def test_margin_uses_standard_error_not_raw_noise():
    # Interaction 0.012 with one repeat at noise 0.01: SE_I = 0.02, so it is indistinguishable from 0.
    vals = {(): 0.5, ("A",): 0.6, ("B",): 0.6, ("A", "B"): 0.712}
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.01, "repeats": 1, "runs": table(vals)})
    assert r["pairwise"]["A+B"]["kind"] == "additive"


def test_missing_repeats_blocks_the_verdict():
    runs = table(additive(0.5, {"A": 0.10, "B": 0.20}))
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.01, "runs": runs})
    assert r["verdict"] == "UNCLASSIFIED"


def test_gap_below_mcid_is_not_acted_on():
    runs = table(additive(0.5, {"A": 0.018, "B": 0.002}))
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.002, "repeats": 4, "mcid": 0.03, "runs": runs})
    assert r["verdict"] == "BELOW_MCID"


def test_empty_constraint_list_is_undefined_not_no_constraint():
    r = mod.rank({"constraints": [], "noise": 0.01, "repeats": 4, "runs": [{"fixed": [], "value": 0.5}]})
    assert r["verdict"] == "UNDEFINED"


def test_bad_inputs_are_rejected():
    ok = table(additive(0.5, {"A": 0.1}))
    dup = ok + [{"fixed": ["A"], "value": 0.7}]
    assert mod.rank({"constraints": ["A"], "noise": 0.01, "repeats": 4, "runs": dup})["verdict"] == "UNDEFINED"
    ghost = ok + [{"fixed": ["Z"], "value": 0.7}]
    assert mod.rank({"constraints": ["A"], "noise": 0.01, "repeats": 4, "runs": ghost})["verdict"] == "UNDEFINED"
    assert (
        mod.rank({"constraints": ["A"], "costs": {"A": 0}, "noise": 0.01, "repeats": 4, "runs": ok})["verdict"]
        == "UNDEFINED"
    )


def test_incomplete_table_uses_leave_one_out_so_complementary_pair_is_not_last():
    # Four constraints, no full table. C and D are complementary (no solo effect, large leave-one-out).
    names = ["A", "B", "C", "D"]
    vals = {(): 0.5, ("A",): 0.6, ("B",): 0.55, ("C",): 0.5, ("D",): 0.5}
    vals[("A", "B", "C", "D")] = 0.95
    vals[("B", "C", "D")] = 0.80
    vals[("A", "C", "D")] = 0.85
    vals[("A", "B", "D")] = 0.65
    vals[("A", "B", "C")] = 0.65
    r = mod.rank({"constraints": names, "noise": 0.005, "repeats": 4, "runs": table(vals)})
    assert r["table_complete"] is False
    assert r["priority_basis"].startswith("max(")
    ranked = [p["constraint"] for p in r["priority"]]
    assert ranked.index("C") < ranked.index("B")  # C's leave-one-out (0.30) beats B's best (0.10)


def test_three_constraint_glove_game_shapley_and_efficiency():
    # R is needed plus at least one of L1/L2. Exact Shapley: R=2/3, L1=L2=1/6 (hand-computed).
    names = ["L1", "L2", "R"]
    vals = {
        c: (1.0 if "R" in c and ("L1" in c or "L2" in c) else 0.0)
        for k in range(4)
        for c in itertools.combinations(names, k)
    }
    r = mod.rank({"constraints": names, "noise": 0.01, "repeats": 4, "runs": table(vals)})
    assert abs(r["shapley"]["R"] - 2 / 3) < 1e-9
    assert abs(r["shapley"]["L1"] - 1 / 6) < 1e-9
    assert abs(sum(r["shapley"].values()) - r["total_gap"]) < 1e-9


def test_efficiency_on_random_tables():
    import random

    rng = random.Random(7)
    names = ["A", "B", "C", "D"]
    for _ in range(50):
        vals = {c: rng.random() for k in range(5) for c in itertools.combinations(names, k)}
        r = mod.rank({"constraints": names, "noise": 0.0001, "repeats": 4, "runs": table(vals)})
        assert abs(sum(r["shapley"].values()) - r["total_gap"]) < 1e-9


def test_masked_verdict_is_reported():
    vals = {(): 0.5, ("A",): 0.5, ("B",): 0.7, ("A", "B"): 0.9}
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "runs": table(vals)})
    assert r["verdict"] == "MASKED_CONSTRAINTS"


def test_dominance_boundary_at_seventy_percent():
    # gap 0.30: A=0.22 (73%) -> dominant; A=0.18 (60%) with B real -> multiple
    hi = table(additive(0.5, {"A": 0.22, "B": 0.08}))
    lo = table(additive(0.5, {"A": 0.18, "B": 0.12}))
    assert mod.rank({"constraints": ["A", "B"], "noise": 0.002, "repeats": 4, "runs": hi})["verdict"] == "SINGLE_DOMINANT"
    assert mod.rank({"constraints": ["A", "B"], "noise": 0.002, "repeats": 4, "runs": lo})["verdict"] == "MULTIPLE_CONSTRAINTS"


def test_nan_and_string_fixed_are_rejected():
    import pytest

    with pytest.raises(ValueError):
        mod.rank({"constraints": ["A"], "noise": 0.01, "repeats": 4,
                  "runs": [{"fixed": [], "value": float("nan")}]})
    with pytest.raises(ValueError):
        mod.rank({"constraints": ["A"], "noise": 0.01, "repeats": 4,
                  "runs": [{"fixed": "A", "value": 0.6}, {"fixed": [], "value": 0.5}]})


def test_partial_costs_are_rejected():
    runs = table(additive(0.5, {"A": 0.1, "B": 0.1}))
    r = mod.rank({"constraints": ["A", "B"], "costs": {"A": 2}, "noise": 0.01, "repeats": 4, "runs": runs})
    assert r["verdict"] == "UNDEFINED"


def test_negative_total_gap_is_an_anomaly_not_a_null():
    vals = {(): 0.8, ("A",): 0.75, ("B",): 0.8, ("A", "B"): 0.70}
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.005, "repeats": 4, "runs": table(vals)})
    assert r["verdict"] == "ANOMALOUS_NEGATIVE_GAP"
    assert "A" in r["harmful_when_fixed"]


def test_budget_ratio_is_not_reported_below_noise():
    runs = table(additive(0.8, {"A": 0.002, "B": -0.003}))
    r = mod.rank({"constraints": ["A", "B"], "noise": 0.01, "repeats": 4, "runs": runs})
    assert "budget_ratio_sum_solo_over_total" not in r


def test_null_system_false_positive_rate_is_bounded():
    import random

    rng = random.Random(11)
    sigma, reps, trials = 0.01, 4, 2000
    hits = 0
    for _ in range(trials):
        vals = {c: 0.5 + rng.gauss(0, sigma / reps**0.5) for k in range(3) for c in itertools.combinations(["A", "B"], k)}
        r = mod.rank({"constraints": ["A", "B"], "noise": sigma, "repeats": reps, "runs": table(vals)})
        hits += r["verdict"] == "NO_CONSTRAINT_DETECTED"
    assert hits / trials >= 0.92  # 2-SE margin: about 95% expected on a null system


def test_cancelling_constraints_are_a_trade_off_not_a_null():
    vals = {(): 0.5, ("a",): 0.7, ("b",): 0.3, ("a", "b"): 0.505}
    r = mod.rank({"constraints": ["a", "b"], "noise": 0.01, "repeats": 4, "runs": table(vals)})
    assert r["verdict"] == "TRADE_OFF"


def test_masked_is_found_from_leave_one_out_without_pair_rows():
    vals = {
        (): 0.5, ("a",): 0.5, ("b",): 0.8, ("c",): 0.5, ("d",): 0.5,
        ("a", "b", "c", "d"): 0.9,
        ("b", "c", "d"): 0.8, ("a", "c", "d"): 0.5, ("a", "b", "d"): 0.9, ("a", "b", "c"): 0.9,
    }
    r = mod.rank({"constraints": ["a", "b", "c", "d"], "noise": 0.01, "repeats": 4, "runs": table(vals)})
    assert any(m.startswith("a (hidden") for m in r["masked"])
    assert r["verdict"] == "MASKED_CONSTRAINTS"


def test_invalid_noise_repeats_costs_and_duplicate_names_exit_cleanly():
    import pytest

    runs = table(additive(0.5, {"a": 0.1}))
    for bad in ({"noise": -0.01, "repeats": 4}, {"noise": float("nan"), "repeats": 4},
                {"noise": 0.01, "repeats": 0}, {"noise": 0.01, "repeats": 4, "costs": ["a"]}):
        with pytest.raises(ValueError):
            mod.rank({"constraints": ["a"], "runs": runs, **bad})
    with pytest.raises(ValueError):
        mod.rank({"constraints": ["a", "a"], "noise": 0.01, "repeats": 4, "runs": runs})


def test_zero_noise_float_residue_is_not_an_interaction():
    vals = {(): 0.5, ("a",): 0.6, ("b",): 0.7, ("a", "b"): 0.8}
    r = mod.rank({"constraints": ["a", "b"], "noise": 0.0, "repeats": 4, "runs": table(vals)})
    assert r["pairwise"]["a+b"]["kind"] == "additive"
