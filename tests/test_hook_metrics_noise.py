"""Tests for the noise census in scripts/hook_metrics.py.

The census is DESCRIPTIVE: the trigger log records that a hook fired, never what happened next, so
none of these tests (or the report) claim a warning was "heeded". What is tested is what the data
holds: counts, duplicates, sessions, concentration, and whether the same warning came back.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import hook_metrics as hm  # noqa: E402

T0 = datetime(2026, 10, 2, 12, 0, 0, tzinfo=UTC)


def row(hook="h", trigger="t", sample="s", sid="S1", at=0.0, action="warning"):
    return {
        "ts": (T0 + timedelta(seconds=at)).isoformat(),
        "hook": hook,
        "trigger": trigger,
        "action": action,
        "sample": sample,
        "session_id": sid,
    }


def one(rows, hook="h"):
    return next(r for r in hm.compute_noise(rows) if r["hook"] == hook)


class TestDuplicates:
    def test_the_same_trigger_logged_twice_within_the_window_is_one_firing(self):
        r = one([row(at=0), row(at=0.9)])
        assert (r["fires"], r["duplicates"], r["distinct"]) == (2, 1, 1)

    def test_the_window_boundary_is_inclusive_at_two_seconds(self):
        assert one([row(at=0), row(at=2.0)])["duplicates"] == 1
        assert one([row(at=0), row(at=2.01)])["duplicates"] == 0

    def test_a_run_of_rapid_rows_is_chained_from_the_last_kept_one(self):
        # 0, 1, 2 are one firing (each within 2 s of the kept 0? no: 2.0 is, 3.5 is not)
        r = one([row(at=0), row(at=1), row(at=2), row(at=3.5)])
        assert r["duplicates"] == 2 and r["distinct"] == 2

    @pytest.mark.parametrize(
        "other",
        [
            row(at=0.5, sample="another sample"),
            row(at=0.5, trigger="another trigger"),
            row(at=0.5, sid="S2"),
        ],
    )
    def test_rows_that_differ_in_sample_trigger_or_session_are_not_duplicates(self, other):
        assert one([row(at=0), other])["duplicates"] == 0

    def test_a_row_with_an_unparseable_timestamp_is_never_merged_and_never_crashes(self):
        bad = row(at=0)
        bad["ts"] = "not a time"
        missing = row(at=0)
        del missing["ts"]
        r = one([row(at=0), bad, missing])
        assert r["fires"] == 3 and r["duplicates"] == 0
        # they still count as firings of their session: dropping them would hide real noise
        assert r["distinct"] == 3 and r["max_per_session"] == 3

    def test_naive_timestamps_are_read_as_utc(self):
        a, b = row(at=0), row(at=1)
        a["ts"], b["ts"] = a["ts"].replace("+00:00", ""), b["ts"]
        assert one([a, b])["duplicates"] == 1


class TestSessionsAndConcentration:
    def test_rows_without_a_session_are_excluded_from_per_session_columns(self):
        r = one([row(sid="", at=0), row(sid="", at=10), row(sid="S1", at=20)])
        assert r["no_session"] == 2 and r["sessions"] == 1
        assert r["max_per_session"] == 1 and r["top_session_share"] == 1.0

    def test_they_are_never_pooled_into_one_pseudo_session(self):
        r = one([row(sid="", sample=f"s{n}", at=10 * n) for n in range(5)])
        assert r["sessions"] == 0 and r["max_per_session"] == 0
        assert r["top_session_share"] is None and r["pairs"] == 0 and r["continued_share"] is None

    def test_a_hook_that_fired_only_in_one_session_is_flagged_by_the_share(self):
        rows = [row(sid="BIG", sample=f"s{n}", at=10 * n) for n in range(18)]
        rows += [row(sid="A", at=1000), row(sid="B", at=2000)]
        r = one(rows)
        assert r["sessions"] == 3 and r["max_per_session"] == 18
        assert r["top_session_share"] == pytest.approx(18 / 20)

    def test_median_is_the_middle_of_per_session_counts(self):
        rows = [row(sid="A", sample=f"a{n}", at=10 * n) for n in range(1)]
        rows += [row(sid="B", sample=f"b{n}", at=10 * n) for n in range(3)]
        rows += [row(sid="C", sample=f"c{n}", at=10 * n) for n in range(10)]
        assert one(rows)["median_per_session"] == 3
        rows += [row(sid="D", sample=f"d{n}", at=10 * n) for n in range(5)]
        assert one(rows)["median_per_session"] == 4  # mean of 3 and 5

    def test_duplicates_do_not_inflate_the_per_session_count(self):
        r = one([row(at=0), row(at=0.5), row(at=1.0)])
        assert r["max_per_session"] == 1


class TestContinuedAfterWarning:
    def test_a_warning_that_came_back_later_is_continued(self):
        r = one([row(sample="file.py", at=0), row(sample="file.py", at=60)])
        assert (r["pairs"], r["continued"], r["continued_share"]) == (1, 1, 1.0)

    def test_a_warning_seen_once_is_not_continued(self):
        r = one([row(sample="file.py", at=0), row(sample="other.py", at=60)])
        assert (r["pairs"], r["continued"], r["continued_share"]) == (2, 0, 0.0)

    def test_a_rapid_duplicate_is_not_a_continuation(self):
        r = one([row(sample="file.py", at=0), row(sample="file.py", at=1)])
        assert r["continued"] == 0

    def test_the_same_sample_in_two_sessions_is_two_separate_warnings(self):
        r = one([row(sid="A", sample="f", at=0), row(sid="B", sample="f", at=60)])
        assert r["pairs"] == 2 and r["continued"] == 0

    def test_only_the_first_80_characters_of_the_sample_identify_a_warning(self):
        base = "x" * 80
        r = one([row(sample=base + "AAA", at=0), row(sample=base + "BBB", at=60)])
        assert r["pairs"] == 1 and r["continued"] == 1


class TestShape:
    def test_empty_input_gives_nothing(self):
        assert hm.compute_noise([]) == []

    def test_hooks_are_sorted_by_firings_then_name(self):
        rows = [row(hook="b", at=0), row(hook="a", at=0), row(hook="a", sample="x", at=10)]
        assert [r["hook"] for r in hm.compute_noise(rows)] == ["a", "b"]
        rows += [row(hook="b", sample="y", at=20), row(hook="b", sample="z", at=30)]
        assert [r["hook"] for r in hm.compute_noise(rows)] == ["b", "a"]

    def test_a_row_without_a_hook_name_is_kept_under_unknown(self):
        e = row()
        del e["hook"]
        assert [r["hook"] for r in hm.compute_noise([e])] == ["<unknown>"]

    def test_the_census_is_part_of_the_metrics_and_survives_json(self):
        metrics = hm.compute_metrics([row(at=0), row(at=60)])
        assert metrics["noise"][0]["hook"] == "h"
        assert json.loads(json.dumps(metrics, default=dict))["noise"][0]["fires"] == 2

    def test_empty_metrics_carry_an_empty_census(self):
        assert hm.compute_metrics([])["noise"] == []

    @given(
        st.lists(
            st.tuples(
                st.sampled_from(["a", "b"]),
                st.sampled_from(["", "S1", "S2"]),
                st.sampled_from(["x", "y"]),
                st.floats(min_value=0, max_value=30),
            ),
            max_size=40,
        )
    )
    @settings(max_examples=150, deadline=None)
    def test_the_numbers_always_add_up(self, items):
        rows = [row(hook=h, sid=s, sample=sm, at=t) for h, s, sm, t in items]
        out = hm.compute_noise(rows)
        assert sum(r["fires"] for r in out) == len(rows)
        for r in out:
            assert r["duplicates"] + r["distinct"] == r["fires"]
            assert 0 <= r["continued"] <= r["pairs"]
            # sessionless rows and the busiest session are disjoint parts of the distinct rows
            assert r["distinct"] >= r["no_session"] + r["max_per_session"]
            assert (r["sessions"] == 0) == (r["max_per_session"] == 0) == (r["pairs"] == 0)
            if r["top_session_share"] is not None:
                assert 0 < r["top_session_share"] <= 1
            if r["continued_share"] is not None:
                assert 0 <= r["continued_share"] <= 1


class TestRendering:
    def render(self, rows):
        since = T0 - timedelta(days=7)
        return hm.render_markdown(hm.compute_metrics(rows), since, Path("log.jsonl"))

    def test_the_section_appears_with_its_caption_and_a_row_per_hook(self):
        md = self.render([row(hook="alpha", at=0), row(hook="beta", at=0)])
        assert "## Noise census (descriptive, not outcomes)" in md
        assert "`alpha`" in md and "`beta`" in md

    def test_the_caption_says_what_is_not_measured(self):
        md = self.render([row(at=0)])
        assert "**Not measured:**" in md and "whether a warning changed what was done" in md
        assert "never pooled into one pseudo-session" in md and "not calibrated" in md

    def test_the_section_sits_between_the_per_hook_table_and_the_trigger_ranking(self):
        md = self.render([row(at=0)])
        assert (
            md.index("## Per-hook breakdown") < md.index("## Noise census") < md.index("## Top-10")
        )

    def test_unknown_shares_render_as_a_dash_never_as_zero(self):
        md = self.render([row(sid="", at=0)])
        line = next(
            ln
            for ln in md.splitlines()
            if ln.startswith("| `h` |") and "No session_id" not in ln and "—" in ln
        )
        assert "0/0 (—)" in line

    def test_known_values_are_rendered(self):
        rows = [row(sample="f", at=0), row(sample="f", at=60), row(sid="S2", at=100)]
        md = self.render(rows)
        assert "| `h` | 3 | 0 | 2 | 1.5 | 2 | 67% | 1/2 (50%) | 0 |" in md

    def test_no_section_when_the_window_is_empty(self):
        md = self.render([])
        assert "Noise census" not in md and "No triggers in window" in md


class TestRealLogShape:
    def test_a_line_as_the_real_log_writes_it_is_understood(self, tmp_path):
        log = tmp_path / "hook_triggers.jsonl"
        line = {
            "ts": "2026-10-02T11:34:58.589295+00:00", "hook": "locality_escalation_guard",
            "trigger": "repeated_local_edit", "action": "warning",
            "sample": "C:\\Users\\x\\scratch\\index.html", "session_id": "c0a467b1-d82b",
        }  # fmt: skip
        log.write_text(
            json.dumps(line) + "\n" + "not json\n" + json.dumps(line) + "\n", encoding="utf-8"
        )
        entries = hm.load_entries(log)
        r = one(entries, "locality_escalation_guard")
        assert r["fires"] == 2 and r["duplicates"] == 1 and r["sessions"] == 1
