"""Regression tests for the three Codex review comments on PR #500 (all reproduced first).

1. sessionless rows were merged as duplicates by the shared empty-string key, although an empty
   id cannot show that two rows came from one session;
2. blocks / sanitizations / info rows were counted in the "continued warnings" ratio;
3. the "Top session" caption named the wrong denominator.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

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


def render(rows):
    return hm.render_markdown(hm.compute_metrics(rows), T0 - timedelta(days=7), Path("log.jsonl"))


# --------------------------------------------------------------------------- 1: sessionless rows
class TestSessionlessRowsAreNeverMerged:
    def test_two_sessionless_rows_close_in_time_stay_two_rows(self):
        r = one([row(sid="", at=0), row(sid="", at=0.5)])
        assert (r["fires"], r["duplicates"], r["distinct"], r["no_session"]) == (2, 0, 2, 2)

    def test_they_are_counted_as_possible_duplicates_not_dropped(self):
        r = one([row(sid="", at=0), row(sid="", at=0.5)])
        assert r["possible_duplicates"] == 1  # the finding about evidence_guard is kept

    def test_concurrent_sessions_without_ids_cannot_be_told_apart_so_they_are_not_merged(self):
        """Two real sessions, same hook/trigger/sample, both with an empty id, within two seconds."""
        r = one([row(sid="", sample="same text", at=0), row(sid="", sample="same text", at=1.0)])
        assert r["distinct"] == 2 and r["duplicates"] == 0

    def test_a_chain_of_close_sessionless_rows_counts_each_follower_once(self):
        r = one([row(sid="", at=0), row(sid="", at=1), row(sid="", at=2), row(sid="", at=10)])
        assert r["possible_duplicates"] == 2 and r["distinct"] == 4

    def test_sessioned_duplicates_are_still_merged_and_confirmed(self):
        r = one([row(sid="S1", at=0), row(sid="S1", at=0.5)])
        assert (r["duplicates"], r["possible_duplicates"], r["distinct"]) == (1, 0, 1)

    def test_a_mix_keeps_the_two_kinds_apart(self):
        rows = [row(sid="S1", at=0), row(sid="S1", at=1), row(sid="", at=0), row(sid="", at=1)]
        r = one(rows)
        assert (r["duplicates"], r["possible_duplicates"], r["fires"], r["distinct"]) == (
            1,
            1,
            4,
            3,
        )

    def test_the_duplicates_cell_shows_the_unconfirmed_ones_with_a_question_mark(self):
        md = render([row(sid="", at=0), row(sid="", at=1), row(sid="", at=2)])
        assert "| 0 (+2?) |" in md

    def test_the_cell_has_no_suffix_when_there_is_nothing_unconfirmed(self):
        md = render([row(sid="S1", at=0), row(sid="S1", at=1)])
        assert "| 1 |" in md and "?)" not in md.split("## Top-10")[0].split("| Hook | Fires")[1]

    def test_the_caption_explains_why_they_are_not_merged(self):
        md = render([row(at=0)])
        assert "cannot be confirmed" in md and "two concurrent sessions" in md


# --------------------------------------------------------------------------- 2: warnings only
class TestContinuedCountsOnlyWarnings:
    @pytest.mark.parametrize("action", ["block", "sanitize", "info", "<unknown>"])
    def test_other_actions_are_never_pairs(self, action):
        r = one([row(sample="x", at=0, action=action), row(sample="x", at=60, action=action)])
        assert (r["pairs"], r["continued"], r["continued_share"]) == (0, 0, None)

    def test_a_blocking_hook_does_not_look_like_it_ignores_its_own_blocks(self):
        rows = [row(hook="input_guard", sample="m", at=60 * n, action="block") for n in range(5)]
        r = one(rows, "input_guard")
        assert r["fires"] == 5 and r["continued"] == 0 and r["continued_share"] is None

    def test_warnings_are_still_counted_next_to_blocks_in_the_same_hook(self):
        rows = [
            row(sample="w", at=0), row(sample="w", at=60),  # a warning that came back
            row(sample="b", at=0, action="block"), row(sample="b", at=60, action="block"),
            row(sample="v", at=0),  # a warning seen once
        ]  # fmt: skip
        r = one(rows)
        assert (r["pairs"], r["continued"], r["continued_share"]) == (2, 1, 0.5)

    def test_a_warning_and_a_block_of_the_same_sample_are_different_events(self):
        r = one([row(sample="x", at=0, action="warning"), row(sample="x", at=0.5, action="block")])
        assert r["duplicates"] == 0 and r["distinct"] == 2

    def test_the_caption_says_warnings_only(self):
        md = render([row(at=0)])
        assert "**warnings**" in md and "never counted" in md


# --------------------------------------------------------------------------- 3: the denominator
class TestTopSessionDenominator:
    def test_the_reviewers_example_60_sessionless_plus_one_in_each_of_two_sessions(self):
        rows = [row(sid="", sample=f"u{n}", at=10 * n) for n in range(60)]
        rows += [row(sid="A", at=1000), row(sid="B", at=2000)]
        r = one(rows)
        assert r["fires"] == 62
        # the busiest KNOWN session holds half of the session-attributed firings, not 1/62
        assert r["top_session_share"] == pytest.approx(0.5)

    def test_confirmed_duplicates_are_not_in_the_denominator(self):
        rows = [row(sid="A", at=0), row(sid="A", at=0.5), row(sid="B", at=100)]
        r = one(rows)
        assert r["fires"] == 3 and r["top_session_share"] == pytest.approx(0.5)  # not 2/3

    def test_the_caption_names_the_real_denominator(self):
        md = render([row(at=0)])
        assert "distinct, session-attributed" in md
        assert "not in the denominator" in md

    def test_the_old_wording_is_gone(self):
        md = render([row(at=0)])
        assert "share of the hook's firings that came from" not in md

    def test_without_any_session_the_share_is_unknown_not_zero(self):
        assert one([row(sid="", at=0)])["top_session_share"] is None
