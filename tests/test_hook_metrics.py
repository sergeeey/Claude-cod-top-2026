"""Tests for scripts/hook_metrics.py — JSONL aggregation contract.

WHY: this script is the evidence base for any "anti-hallucination works"
claim in marketing material. If aggregation breaks (silently drops entries,
miscounts sessions, mangles timezone parsing), the whole metric chain
becomes [VERIFIED-SYNTHETIC] — exactly what we promised users we'd avoid.
Pinning the contract here.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# WHY: scripts/ isn't a package, so import via sys.path manipulation per
# tests/conftest convention used elsewhere in the project.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from hook_metrics import (  # noqa: E402
    compute_drift,
    compute_metrics,
    filter_by_window,
    load_entries,
    render_markdown,
    render_sparkline,
)


def _make_entry(
    ts: str = "2026-05-03T12:00:00+00:00",
    hook: str = "validation_theater_guard",
    trigger: str = "perfect_score",
    action: str = "warning",
    sample: str = "F1=1.000",
    session_id: str = "s-001",
) -> dict:
    return {
        "ts": ts,
        "hook": hook,
        "trigger": trigger,
        "action": action,
        "sample": sample,
        "session_id": session_id,
    }


class TestLoadEntries:
    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        assert load_entries(tmp_path / "does-not-exist.jsonl") == []

    def test_parses_valid_jsonl(self, tmp_path: Path) -> None:
        log = tmp_path / "log.jsonl"
        log.write_text(
            json.dumps(_make_entry())
            + "\n"
            + json.dumps(_make_entry(hook="evidence_guard"))
            + "\n",
            encoding="utf-8",
        )
        entries = load_entries(log)
        assert len(entries) == 2
        assert entries[0]["hook"] == "validation_theater_guard"
        assert entries[1]["hook"] == "evidence_guard"

    def test_skips_malformed_lines_silently(self, tmp_path: Path) -> None:
        # WHY: telemetry log can be truncated mid-write on sudden process kill.
        # One bad line should NOT block the rest of the report.
        log = tmp_path / "log.jsonl"
        log.write_text(
            json.dumps(_make_entry()) + "\n"
            "{this is not json\n"  # malformed
             + json.dumps(_make_entry(hook="evidence_guard")) + "\n",
            encoding="utf-8",
        )
        entries = load_entries(log)
        assert len(entries) == 2  # malformed dropped, others kept

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        log = tmp_path / "log.jsonl"
        log.write_text(
            "\n\n" + json.dumps(_make_entry()) + "\n\n",
            encoding="utf-8",
        )
        assert len(load_entries(log)) == 1


class TestFilterByWindow:
    def test_keeps_entries_after_cutoff(self) -> None:
        cutoff = datetime(2026, 5, 3, tzinfo=UTC)
        entries = [
            _make_entry(ts="2026-05-01T12:00:00+00:00"),  # before
            _make_entry(ts="2026-05-04T12:00:00+00:00"),  # after
            _make_entry(ts="2026-05-03T00:00:00+00:00"),  # exactly at cutoff (kept)
        ]
        result = filter_by_window(entries, cutoff)
        assert len(result) == 2

    def test_drops_entries_with_unparseable_ts(self) -> None:
        cutoff = datetime(2026, 1, 1, tzinfo=UTC)
        entries = [_make_entry(ts="not-a-date"), _make_entry(ts="")]
        # WHY: bad ts must be skipped, not crash, not silently treated as "now".
        assert filter_by_window(entries, cutoff) == []

    def test_assumes_utc_for_naive_iso(self) -> None:
        cutoff = datetime(2026, 5, 3, tzinfo=UTC)
        entries = [_make_entry(ts="2026-05-04T00:00:00")]  # no offset
        result = filter_by_window(entries, cutoff)
        assert len(result) == 1


class TestComputeMetrics:
    def test_empty_input(self) -> None:
        m = compute_metrics([])
        assert m["total"] == 0
        assert m["sessions"] == 0
        assert m["time_range"] is None
        assert m["per_hook"] == {}
        assert m["top_triggers"] == []

    def test_aggregates_basic_counts(self) -> None:
        entries = [
            _make_entry(hook="vtg", trigger="perfect_score", action="warning"),
            _make_entry(hook="vtg", trigger="perfect_score", action="warning"),
            _make_entry(hook="evidence_guard", trigger="missing_marker", action="warning"),
            _make_entry(hook="input_guard", trigger="prompt_injection", action="block"),
        ]
        m = compute_metrics(entries)
        assert m["total"] == 4
        assert m["per_hook"]["vtg"]["count"] == 2
        assert m["per_hook"]["evidence_guard"]["count"] == 1
        assert m["per_hook"]["input_guard"]["actions"]["block"] == 1

    def test_unique_session_count(self) -> None:
        entries = [
            _make_entry(session_id="s-1"),
            _make_entry(session_id="s-1"),  # duplicate
            _make_entry(session_id="s-2"),
            _make_entry(session_id=""),  # empty must NOT count
        ]
        m = compute_metrics(entries)
        assert m["sessions"] == 2

    def test_top_triggers_capped_at_10(self) -> None:
        entries = [_make_entry(trigger=f"t-{i}", session_id=f"s-{i}") for i in range(15)]
        m = compute_metrics(entries)
        assert len(m["top_triggers"]) == 10

    def test_samples_kept_capped_at_5(self) -> None:
        # WHY: log-explosion guard — keep last 5 samples per hook only.
        entries = [
            _make_entry(hook="vtg", sample=f"sample-{i}", ts=f"2026-05-03T12:0{i}:00+00:00")
            for i in range(10)
        ]
        m = compute_metrics(entries)
        assert len(m["per_hook"]["vtg"]["samples"]) == 5

    def test_per_day_bucketing(self) -> None:
        entries = [
            _make_entry(ts="2026-05-01T10:00:00+00:00"),
            _make_entry(ts="2026-05-01T15:00:00+00:00"),
            _make_entry(ts="2026-05-02T10:00:00+00:00"),
        ]
        m = compute_metrics(entries)
        assert m["per_day"]["2026-05-01"] == 2
        assert m["per_day"]["2026-05-02"] == 1


class TestSparkline:
    def test_empty(self) -> None:
        assert "no data" in render_sparkline({})

    def test_renders_unicode_blocks(self) -> None:
        result = render_sparkline({"2026-05-01": 1, "2026-05-02": 8, "2026-05-03": 4})
        # WHY: sparkline must contain Unicode block characters and a peak label.
        assert "peak=8" in result
        assert "days=3" in result
        assert any(b in result for b in "▁▂▃▄▅▆▇█")


class TestRenderMarkdown:
    def test_empty_window_message(self, tmp_path: Path) -> None:
        # WHY: when there are no triggers, output should explain how to debug,
        # not silently produce a blank report (looks broken to user).
        m = compute_metrics([])
        out = render_markdown(m, datetime(2026, 5, 3, tzinfo=UTC), tmp_path / "log.jsonl")
        assert "No triggers in window" in out
        assert "wc -l" in out  # diagnostic command included

    def test_includes_all_sections_when_data_present(self, tmp_path: Path) -> None:
        entries = [_make_entry(), _make_entry(hook="evidence_guard")]
        m = compute_metrics(entries)
        out = render_markdown(m, datetime(2026, 5, 1, tzinfo=UTC), tmp_path / "log.jsonl")
        # Pin headings — script consumers may grep for these.
        assert "## Summary" in out
        assert "## Per-hook breakdown" in out
        assert "## Top-10 trigger types" in out
        assert "## Recent samples" in out

    def test_table_sorted_by_count_desc(self, tmp_path: Path) -> None:
        entries = (
            [_make_entry(hook="rare")] * 1
            + [_make_entry(hook="common")] * 5
            + [_make_entry(hook="medium")] * 3
        )
        m = compute_metrics(entries)
        out = render_markdown(m, datetime(2026, 5, 1, tzinfo=UTC), tmp_path / "log.jsonl")
        idx_common = out.index("`common`")
        idx_medium = out.index("`medium`")
        idx_rare = out.index("`rare`")
        assert idx_common < idx_medium < idx_rare


class TestEndToEnd:
    """Integration: real JSONL file → loaded → filtered → rendered Markdown."""

    def test_full_pipeline(self, tmp_path: Path) -> None:
        log = tmp_path / "hook_triggers.jsonl"
        now = datetime.now(UTC)
        old = (now - timedelta(days=10)).isoformat()
        recent = (now - timedelta(hours=1)).isoformat()

        log.write_text(
            json.dumps(_make_entry(ts=old, hook="vtg", trigger="old"))
            + "\n"
            + json.dumps(_make_entry(ts=recent, hook="vtg", trigger="perfect_score"))
            + "\n",
            encoding="utf-8",
        )

        # 7-day window must drop the 10-day-old entry.
        entries = load_entries(log)
        in_window = filter_by_window(entries, now - timedelta(days=7))
        assert len(in_window) == 1
        assert in_window[0]["trigger"] == "perfect_score"

        m = compute_metrics(in_window)
        out = render_markdown(m, now - timedelta(days=7), log)
        assert "Total triggers:** 1" in out
        assert "perfect_score" in out
        assert "old" not in out  # confirmed dropped


class TestComputeDrift:
    """Unit tests for compute_drift() block-rate spike detection."""

    def _entry(self, hook: str, day: str, action: str = "log") -> dict:
        return {
            "hook": hook,
            "action": action,
            "trigger": "test",
            "sample": "",
            "ts": f"{day}T12:00:00+00:00",
            "session_id": "sess1",
        }

    def test_no_alerts_when_rate_stable(self) -> None:
        """Stable 50% block rate across two days → no spike → no alerts."""
        entries = [
            self._entry("input_guard", "2026-05-01", "block"),
            self._entry("input_guard", "2026-05-01", "log"),
            self._entry("input_guard", "2026-05-02", "block"),
            self._entry("input_guard", "2026-05-02", "log"),
        ]
        alerts = compute_drift(entries, threshold=0.15)
        assert alerts == []

    def test_alert_on_spike(self) -> None:
        """Block rate jumps 0% → 100% on last day → alert returned."""
        entries = [
            self._entry("input_guard", "2026-05-01", "log"),
            self._entry("input_guard", "2026-05-01", "log"),
            self._entry("input_guard", "2026-05-02", "log"),
            self._entry("input_guard", "2026-05-02", "log"),
            self._entry("input_guard", "2026-05-03", "block"),
            self._entry("input_guard", "2026-05-03", "block"),
        ]
        alerts = compute_drift(entries, threshold=0.15)
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["hook"] == "input_guard"
        assert alert["last_day_rate"] == 1.0
        assert alert["prior_mean_rate"] == 0.0
        assert alert["delta"] == 1.0

    def test_no_alert_below_threshold(self) -> None:
        """Spike of 10% is below 15% threshold → no alert."""
        entries = [
            self._entry("input_guard", "2026-05-01", "log"),
            self._entry("input_guard", "2026-05-01", "log"),
            *[self._entry("input_guard", "2026-05-02", "log") for _ in range(9)],
            self._entry("input_guard", "2026-05-02", "block"),
        ]
        alerts = compute_drift(entries, threshold=0.15)
        assert alerts == []

    def test_single_day_returns_no_alerts(self) -> None:
        """Only one day of data → cannot compute delta → no alerts."""
        entries = [
            self._entry("input_guard", "2026-05-01", "block"),
            self._entry("input_guard", "2026-05-01", "block"),
        ]
        alerts = compute_drift(entries, threshold=0.15)
        assert alerts == []

    def test_empty_entries_returns_no_alerts(self) -> None:
        alerts = compute_drift([], threshold=0.15)
        assert alerts == []

    def test_multiple_hooks_independent(self) -> None:
        """Spike in one hook doesn't affect alert count for the other."""
        entries = [
            self._entry("hook_a", "2026-05-01", "log"),
            self._entry("hook_a", "2026-05-02", "log"),
            self._entry("hook_b", "2026-05-01", "log"),
            self._entry("hook_b", "2026-05-02", "block"),
        ]
        alerts = compute_drift(entries, threshold=0.15)
        assert len(alerts) == 1
        assert alerts[0]["hook"] == "hook_b"

    def test_alerts_sorted_by_delta_descending(self) -> None:
        """Multiple spikes → sorted largest delta first.

        hook_big: 0% prior → 100% last (delta 1.0)
        hook_small: 50% prior → 70% last (delta 0.2)
        """
        entries = [
            # hook_small prior day: 1 block + 1 log = 50% block rate
            self._entry("hook_small", "2026-05-01", "block"),
            self._entry("hook_small", "2026-05-01", "log"),
            # hook_small last day: 7 blocks + 3 logs = 70% block rate → delta 0.2
            *[self._entry("hook_small", "2026-05-02", "block") for _ in range(7)],
            *[self._entry("hook_small", "2026-05-02", "log") for _ in range(3)],
            # hook_big prior day: all log = 0% block rate
            self._entry("hook_big", "2026-05-01", "log"),
            # hook_big last day: all block = 100% → delta 1.0
            self._entry("hook_big", "2026-05-02", "block"),
        ]
        alerts = compute_drift(entries, threshold=0.10)
        assert len(alerts) == 2
        assert alerts[0]["hook"] == "hook_big"  # delta 1.0 comes first
        assert alerts[1]["hook"] == "hook_small"  # delta 0.2
