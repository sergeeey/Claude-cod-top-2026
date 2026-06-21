"""Tests for hooks/claim_entropy_tracker.py — Perelman monotone invariant.

WHY: claim_entropy_tracker is the only automated enforcement of the
Perelman monotonicity rule (entropy must decrease per step). If broken,
the invariant becomes advisory-only — the same failure mode as any
unchecked "best practice".
"""

import io
import json
from pathlib import Path
from unittest.mock import patch

from claim_entropy_tracker import is_claim_md, load_state, main, parse_entropy, save_state

# ---------------------------------------------------------------------------
# Sample claim.md content fragments
# ---------------------------------------------------------------------------

CLAIM_MD_ENTROPY_SECTION = """\
## Claim Entropy
_Monotone invariant_

| Component | Count |
|---|---|
| Unsupported HIGH claims | 3 |
| Hidden assumptions | 2 |
| Missing negative controls | 1 |
| Ambiguous definitions | 0 |
| Unresolved blockers | 1 |
| **Total claim_entropy** | 7 |
"""

CLAIM_MD_TOTAL_ONLY = """\
## Claim Entropy

| Component | Count |
|---|---|
| Unsupported HIGH claims | |
| Hidden assumptions | |
| **Total claim_entropy** | 4 |
"""

CLAIM_MD_ROWS_ONLY = """\
## Claim Entropy

| Component | Count |
|---|---|
| Unsupported HIGH claims | 2 |
| Hidden assumptions | 3 |
| Missing negative controls | 1 |
"""

CLAIM_MD_ZERO = """\
## Claim Entropy

| Component | Count |
|---|---|
| Unsupported HIGH claims | 0 |
| Hidden assumptions | 0 |
| Missing negative controls | 0 |
| Ambiguous definitions | 0 |
| Unresolved blockers | 0 |
| **Total claim_entropy** | 0 |
"""

CLAIM_MD_EMPTY_CELLS = """\
## Claim Entropy

| Component | Count |
|---|---|
| Unsupported HIGH claims | |
| Hidden assumptions | |
"""

CLAIM_MD_NO_SECTION = """\
## Falsifiable Claim

Some claim text here.
"""


# ---------------------------------------------------------------------------
# is_claim_md
# ---------------------------------------------------------------------------


class TestIsClaimMd:
    def test_simple_experiments_path(self):
        assert is_claim_md("experiments/20260601-test/claim.md") is True

    def test_nested_experiments_path(self):
        assert is_claim_md("project/experiments/abc/claim.md") is True

    def test_wrong_filename(self):
        assert is_claim_md("experiments/abc/controls.md") is False

    def test_no_experiments_in_path(self):
        assert is_claim_md("some/other/claim.md") is False

    def test_absolute_path_with_experiments(self):
        assert is_claim_md("/home/user/experiments/run1/claim.md") is True

    def test_empty_string(self):
        assert is_claim_md("") is False


# ---------------------------------------------------------------------------
# parse_entropy
# ---------------------------------------------------------------------------


class TestParseEntropy:
    def test_total_row_takes_precedence(self):
        assert parse_entropy(CLAIM_MD_ENTROPY_SECTION) == 7

    def test_total_only_row(self):
        assert parse_entropy(CLAIM_MD_TOTAL_ONLY) == 4

    def test_sum_component_rows_fallback(self):
        assert parse_entropy(CLAIM_MD_ROWS_ONLY) == 6

    def test_zero_entropy(self):
        assert parse_entropy(CLAIM_MD_ZERO) == 0

    def test_empty_cells_returns_none(self):
        assert parse_entropy(CLAIM_MD_EMPTY_CELLS) is None

    def test_no_section_returns_none(self):
        assert parse_entropy(CLAIM_MD_NO_SECTION) is None

    def test_empty_string_returns_none(self):
        assert parse_entropy("") is None

    def test_section_at_end_of_file(self):
        content = "## Other Section\n\nstuff\n\n" + CLAIM_MD_ENTROPY_SECTION
        assert parse_entropy(content) == 7

    def test_section_in_middle_of_file(self):
        content = CLAIM_MD_ENTROPY_SECTION + "\n\n## Next Section\n\nmore stuff"
        assert parse_entropy(content) == 7


# ---------------------------------------------------------------------------
# load_state / save_state
# ---------------------------------------------------------------------------


class TestStateIO:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_state(tmp_path / "nonexistent.json") == {}

    def test_corrupt_file_returns_empty(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("not json")
        assert load_state(p) == {}

    def test_round_trip(self, tmp_path):
        p = tmp_path / "state.json"
        save_state(p, {"entropy": 5})
        assert load_state(p) == {"entropy": 5}

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "deep" / "nested" / "state.json"
        save_state(p, {"entropy": 3})
        assert p.exists()
        assert load_state(p) == {"entropy": 3}

    def test_atomic_write_on_overwrite(self, tmp_path):
        p = tmp_path / "state.json"
        save_state(p, {"entropy": 10})
        save_state(p, {"entropy": 5})
        assert load_state(p)["entropy"] == 5


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------


class TestMain:
    """Run main() with injected stdin and a real temp claim.md."""

    def _make_claim(self, tmp_path: Path, content: str) -> Path:
        exp_dir = tmp_path / "experiments" / "20260101-test"
        exp_dir.mkdir(parents=True)
        p = exp_dir / "claim.md"
        p.write_text(content, encoding="utf-8")
        return p

    def _run(self, monkeypatch, tmp_path: Path, content: str, prev_entropy: int | None = None):
        claim = self._make_claim(tmp_path, content)

        if prev_entropy is not None:
            state_path = claim.parent / ".claim_entropy_state.json"
            save_state(state_path, {"entropy": prev_entropy})

        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(claim)},
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            try:
                main()
            except SystemExit:
                pass
        return buf.getvalue().strip(), claim

    def test_non_matching_tool_exits_silently(self, monkeypatch, tmp_path):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            try:
                main()
            except SystemExit:
                pass
        assert buf.getvalue() == ""

    def test_non_claim_file_exits_silently(self, monkeypatch, tmp_path):
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(tmp_path / "experiments" / "abc" / "controls.md")},
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            try:
                main()
            except SystemExit:
                pass
        assert buf.getvalue() == ""

    def test_empty_entropy_section_exits_silently(self, monkeypatch, tmp_path):
        out, _ = self._run(monkeypatch, tmp_path, CLAIM_MD_EMPTY_CELLS)
        assert out == ""

    def test_baseline_set_on_first_write(self, monkeypatch, tmp_path):
        out, claim = self._run(monkeypatch, tmp_path, CLAIM_MD_ENTROPY_SECTION)
        result = json.loads(out)
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "Baseline" in ctx
        assert "entropy=7" in ctx

    def test_valid_step_decreases_entropy_silently(self, monkeypatch, tmp_path):
        # prev=7, current=5 → valid step, no output
        content_5 = CLAIM_MD_ENTROPY_SECTION.replace(
            "| **Total claim_entropy** | 7 |", "| **Total claim_entropy** | 5 |"
        )
        out, _ = self._run(monkeypatch, tmp_path, content_5, prev_entropy=7)
        assert out == ""

    def test_stagnant_entropy_emits_violation(self, monkeypatch, tmp_path):
        # prev=7, current=7 → violation
        out, _ = self._run(monkeypatch, tmp_path, CLAIM_MD_ENTROPY_SECTION, prev_entropy=7)
        result = json.loads(out)
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "invariant violated" in ctx
        assert "unchanged" in ctx

    def test_increased_entropy_emits_violation(self, monkeypatch, tmp_path):
        # prev=4, current=7 → violation
        out, _ = self._run(monkeypatch, tmp_path, CLAIM_MD_ENTROPY_SECTION, prev_entropy=4)
        result = json.loads(out)
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "invariant violated" in ctx
        assert "7" in ctx

    def test_zero_entropy_emits_promotion_ready(self, monkeypatch, tmp_path):
        out, _ = self._run(monkeypatch, tmp_path, CLAIM_MD_ZERO, prev_entropy=1)
        result = json.loads(out)
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "claim_entropy=0" in ctx
        assert "promotion" in ctx

    def test_state_persisted_after_run(self, monkeypatch, tmp_path):
        _, claim = self._run(monkeypatch, tmp_path, CLAIM_MD_ENTROPY_SECTION)
        state = load_state(claim.parent / ".claim_entropy_state.json")
        assert state["entropy"] == 7

    def test_recursion_guard_exits_silently(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_INVOKED_BY", "1")
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "experiments/abc/claim.md"},
            }
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            try:
                main()
            except SystemExit:
                pass
        assert buf.getvalue() == ""

    def test_no_section_exits_silently(self, monkeypatch, tmp_path):
        out, _ = self._run(monkeypatch, tmp_path, CLAIM_MD_NO_SECTION)
        assert out == ""
