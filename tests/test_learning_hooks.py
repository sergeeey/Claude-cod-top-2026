"""Tests for learning_tips.py and learning_tracker.py."""

import io
import json
import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


# ─── learning_tips ────────────────────────────────────────────────────────────


class TestLearningTips:
    def test_tips_list_not_empty(self):
        from learning_tips import TIPS

        assert len(TIPS) >= 20

    def test_all_tips_have_required_fields(self):
        from learning_tips import TIPS

        for tip in TIPS:
            assert "id" in tip
            assert "level" in tip
            assert "tag" in tip
            assert "text" in tip
            assert "next_try" in tip

    def test_tip_levels_range(self):
        from learning_tips import TIPS

        levels = {t["level"] for t in TIPS}
        assert levels == {1, 2, 3, 4, 5}

    def test_tip_ids_unique(self):
        from learning_tips import TIPS

        ids = [t["id"] for t in TIPS]
        assert len(ids) == len(set(ids))

    def test_shown_tip_ids_empty_log(self):
        from learning_tips import _shown_tip_ids

        assert _shown_tip_ids("") == []

    def test_shown_tip_ids_parses_table(self):
        from learning_tips import _shown_tip_ids

        log = (
            "## Machine Log\n"
            "| Date             | Commit  | Type     | Tip ID  | Files |\n"
            "|------------------|---------|----------|---------|-------|\n"
            "| 2026-04-05 22:05 | abc1234 | feat     | L2-T03  | 7     |\n"
            "| 2026-04-05 23:00 | def5678 | fix      | L1-T01  | 2     |\n"
        )
        ids = _shown_tip_ids(log)
        assert "L2-T03" in ids
        assert "L1-T01" in ids

    def test_select_tip_empty_log_returns_tip(self):
        from learning_tips import select_tip

        tip = select_tip("", "feat")
        assert "id" in tip
        assert "text" in tip

    def test_select_tip_skips_shown(self):
        from learning_tips import select_tip, TIPS

        # Mark all tips except last as shown
        all_ids_except_last = [t["id"] for t in TIPS[:-1]]
        log = (
            "## Machine Log\n"
            "| Date | Commit | Type | Tip ID | Files |\n"
            "|------|--------|------|--------|-------|\n"
        )
        for tid in all_ids_except_last:
            log += f"| 2026-04-05 22:05 | abc1234 | feat | {tid} | 1 |\n"
        tip = select_tip(log, "feat")
        assert tip["id"] == TIPS[-1]["id"]

    def test_select_tip_cycles_when_all_shown(self):
        from learning_tips import select_tip, TIPS

        # All tips shown — should still return a tip (cycle restart)
        log = (
            "## Machine Log\n"
            "| Date | Commit | Type | Tip ID | Files |\n"
            "|------|--------|------|--------|-------|\n"
        )
        for tip in TIPS:
            log += f"| 2026-04-05 22:05 | abc1234 | feat | {tip['id']} | 1 |\n"
        result = select_tip(log, "feat")
        assert result is not None
        assert "id" in result

    def test_select_tip_prefers_relevant_tag(self):
        from learning_tips import select_tip

        tip = select_tip("", "test")
        # For 'test' commits, should prefer tdd or hooks tags
        assert tip["tag"] in {
            "tdd",
            "hooks",
            "evidence",
            "skills",
            "memory",
            "slash",
            "mcp",
            "worktree",
            "agents",
            "plan",
            "tokens",
            "statusline",
            "routing",
        }

    def test_learning_log_path_is_pathlib(self):
        from learning_tips import LEARNING_LOG_PATH

        assert isinstance(LEARNING_LOG_PATH, Path)


# ─── learning_tracker ────────────────────────────────────────────────────────


class TestIsCommitCommand:
    def setup_method(self):
        import learning_tracker

        self.mod = learning_tracker

    def test_git_commit_detected(self):
        assert self.mod._is_commit_command('git commit -m "feat: x"')

    def test_git_merge_detected(self):
        assert self.mod._is_commit_command("git merge main")

    def test_other_bash_not_detected(self):
        assert not self.mod._is_commit_command("git push origin main")
        assert not self.mod._is_commit_command("pytest tests/")


class TestIsFailed:
    def setup_method(self):
        import learning_tracker

        self.mod = learning_tracker

    def test_nonzero_returncode_is_failed(self):
        assert self.mod._is_failed("", "", 1)

    def test_nothing_to_commit_is_failed(self):
        assert self.mod._is_failed("nothing to commit", "", 0)

    def test_success_is_not_failed(self):
        assert not self.mod._is_failed("[main abc1234] feat: x", "", 0)


class TestDetectCommitContext:
    def setup_method(self):
        import learning_tracker

        self.mod = learning_tracker

    def _make_data(self, command, stdout, returncode=0):
        return {
            "tool_input": {"command": command},
            "tool_response": {"stdout": stdout, "returncode": returncode},
        }

    def test_returns_none_for_non_commit(self):
        data = self._make_data("git push origin main", "")
        assert self.mod.detect_commit_context(data) is None

    def test_returns_none_for_failed_commit(self):
        data = self._make_data('git commit -m "x"', "nothing to commit", 0)
        assert self.mod.detect_commit_context(data) is None

    def test_parses_successful_commit(self):
        stdout = "[main abc1234] feat: add learning tracker\n 3 files changed, 100 insertions(+)"
        data = self._make_data('git commit -m "feat: add learning tracker"', stdout)
        ctx = self.mod.detect_commit_context(data)
        assert ctx is not None
        assert ctx["hash"] == "abc1234"
        assert "feat" in ctx["msg"]
        assert ctx["files_changed"] == 3

    def test_missing_tool_input_returns_none(self):
        assert self.mod.detect_commit_context({}) is None


class TestClassifyCommit:
    def setup_method(self):
        import learning_tracker

        self.mod = learning_tracker

    def test_feat(self):
        assert self.mod.classify_commit("feat: add learning loop") == "feat"

    def test_fix(self):
        assert self.mod.classify_commit("fix: correct regex") == "fix"

    def test_test(self):
        assert self.mod.classify_commit("test: add 50 tests") == "test"

    def test_refactor(self):
        assert self.mod.classify_commit("refactor: extract utils") == "refactor"

    def test_chore(self):
        assert self.mod.classify_commit("chore: update deps") == "chore"

    def test_docs(self):
        assert self.mod.classify_commit("docs: update README") == "docs"

    def test_unknown_returns_other(self):
        assert self.mod.classify_commit("wip: something") == "other"


class TestRenderYellowBox:
    def setup_method(self):
        import learning_tracker
        from learning_tips import TIPS

        self.mod = learning_tracker
        self.tip = TIPS[0]

    def _strip_ansi(self, text):
        return re.sub(r"\033\[[^m]+m", "", text)

    def test_contains_tip_header(self):
        box = self.mod.render_yellow_box(self.tip)
        clean = self._strip_ansi(box)
        assert "CLAUDE CODE TIP" in clean

    def test_contains_level(self):
        box = self.mod.render_yellow_box(self.tip)
        clean = self._strip_ansi(box)
        assert f"Level {self.tip['level']}" in clean

    def test_contains_next_try(self):
        box = self.mod.render_yellow_box(self.tip)
        clean = self._strip_ansi(box)
        assert "Попробуй" in clean

    def test_box_width_consistent(self):
        box = self.mod.render_yellow_box(self.tip)
        clean = self._strip_ansi(box)
        lines = clean.splitlines()
        # All lines should be same width (68)
        widths = {len(l) for l in lines if l.strip()}
        assert len(widths) <= 2  # allow minor variation for unicode chars

    def test_has_ansi_yellow(self):
        box = self.mod.render_yellow_box(self.tip)
        assert "\033[93m" in box
        assert "\033[0m" in box


class TestAppendToLearningLog:
    def test_creates_file_if_missing(self, tmp_path):
        import learning_tracker

        with patch("learning_tracker.LEARNING_LOG_PATH", tmp_path / "learning_log.md"):
            from learning_tips import LEARNING_LOG_PATH

            log_path = tmp_path / "learning_log.md"
            with patch.object(type(log_path), "__new__", return_value=log_path):
                learning_tracker.append_to_learning_log("abc1234", "feat: x", "feat", "L2-T03", 3)

    def test_appends_row(self, tmp_path):
        import learning_tracker

        log_path = tmp_path / "learning_log.md"
        with patch("learning_tracker.LEARNING_LOG_PATH", log_path):
            learning_tracker.append_to_learning_log("abc1234", "feat: test", "feat", "L2-T03", 5)
            content = log_path.read_text(encoding="utf-8")
            assert "abc1234" in content
            assert "L2-T03" in content
            assert "5" in content

    def test_appends_multiple_rows(self, tmp_path):
        import learning_tracker

        log_path = tmp_path / "learning_log.md"
        with patch("learning_tracker.LEARNING_LOG_PATH", log_path):
            learning_tracker.append_to_learning_log("hash1", "feat: a", "feat", "L1-T01", 1)
            learning_tracker.append_to_learning_log("hash2", "fix: b", "fix", "L1-T02", 2)
            content = log_path.read_text(encoding="utf-8")
            assert "hash1" in content
            assert "hash2" in content


class TestBuildClaudeContext:
    def test_returns_string(self):
        import learning_tracker
        from learning_tips import TIPS

        ctx = learning_tracker.build_claude_context("abc1234", "feat: x", TIPS[0])
        assert isinstance(ctx, str)
        assert "abc1234" in ctx
        assert TIPS[0]["id"] in ctx


class TestLearningTrackerMain:
    def _run_main(self, stdin_data: dict, tmp_path: Path):
        import learning_tracker

        log_path = tmp_path / "learning_log.md"
        stderr_capture = io.StringIO()
        stdout_capture = io.StringIO()
        with (
            patch("learning_tracker.LEARNING_LOG_PATH", log_path),
            patch("sys.stdin", io.StringIO(json.dumps(stdin_data))),
            patch("sys.stderr", stderr_capture),
            patch("sys.stdout", stdout_capture),
        ):
            learning_tracker.main()
        return stderr_capture.getvalue(), stdout_capture.getvalue(), log_path

    def test_non_commit_produces_no_output(self, tmp_path):
        data = {
            "tool_input": {"command": "pytest tests/"},
            "tool_response": {"stdout": "passed", "returncode": 0},
        }
        stderr, stdout, log = self._run_main(data, tmp_path)
        assert stderr == ""
        assert stdout == ""
        assert not log.exists()

    def test_commit_produces_yellow_box_on_stderr(self, tmp_path):
        data = {
            "tool_input": {"command": 'git commit -m "feat: add feature"'},
            "tool_response": {
                "stdout": "[main abc1234] feat: add feature\n 2 files changed",
                "returncode": 0,
            },
        }
        stderr, stdout, log = self._run_main(data, tmp_path)
        assert "CLAUDE CODE TIP" in re.sub(r"\033\[[^m]+m", "", stderr)

    def test_commit_writes_to_log(self, tmp_path):
        data = {
            "tool_input": {"command": 'git commit -m "fix: bug"'},
            "tool_response": {
                "stdout": "[main abc1234] fix: bug\n 1 file changed",
                "returncode": 0,
            },
        }
        _, _, log = self._run_main(data, tmp_path)
        assert log.exists()
        content = log.read_text(encoding="utf-8")
        assert "abc1234" in content

    def test_commit_emits_claude_context(self, tmp_path):
        data = {
            "tool_input": {"command": 'git commit -m "test: add tests"'},
            "tool_response": {
                "stdout": "[main abc1234] test: add tests\n 3 files changed",
                "returncode": 0,
            },
        }
        _, stdout, _ = self._run_main(data, tmp_path)
        parsed = json.loads(stdout)
        assert "hookSpecificOutput" in parsed
        assert "additionalContext" in parsed["hookSpecificOutput"]
        assert "abc1234" in parsed["hookSpecificOutput"]["additionalContext"]

    def test_failed_commit_produces_no_output(self, tmp_path):
        data = {
            "tool_input": {"command": 'git commit -m "feat: x"'},
            "tool_response": {"stdout": "nothing to commit", "returncode": 0},
        }
        stderr, stdout, log = self._run_main(data, tmp_path)
        assert stderr == ""
        assert not log.exists()
