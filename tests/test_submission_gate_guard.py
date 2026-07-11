"""Tests for submission_gate_guard.py hook."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from submission_gate_guard import (
    GATE_MESSAGE,
    _is_prompt_triggered,
    _is_submission_shaped_path,
)

HOOK_PATH = Path(__file__).parent.parent / "hooks" / "submission_gate_guard.py"


class TestIsPromptTriggered:
    def test_triggered_by_verb_and_noun_ru(self):
        assert _is_prompt_triggered("готово отправить статью рецензенту")

    def test_triggered_by_verb_and_noun_en(self):
        assert _is_prompt_triggered("I'm ready to submit the manuscript")

    def test_not_triggered_by_verb_only(self):
        # "publish" with no claim-noun -- e.g. npm publish, not a submission.
        assert not _is_prompt_triggered("ready to publish the npm package")

    def test_not_triggered_by_noun_only(self):
        assert not _is_prompt_triggered("let's re-read the paper section again")

    def test_not_triggered_by_generic_dev_talk(self):
        assert not _is_prompt_triggered("ready to commit this fix")

    def test_not_triggered_by_empty(self):
        assert not _is_prompt_triggered("")

    def test_triggered_by_doctor_noun(self):
        assert _is_prompt_triggered("отправляю письмо доктору с результатами")

    def test_not_triggered_by_already_substring_of_ready(self):
        # Regression: "already" contains "ready" as a raw substring -- must
        # not false-positive via naive `in` matching.
        assert not _is_prompt_triggered("I already fixed the bug, saw it in today's newspaper")

    def test_not_triggered_by_incomplete_substring_of_complete(self):
        # Regression: "incomplete" contains "complete" as a raw substring.
        assert not _is_prompt_triggered(
            "the analysis is incomplete, need more data on the paper's methodology"
        )

    def test_still_triggered_by_completely_containing_verb(self):
        # "completely" contains the whole word "complete"? No -- \b requires
        # a word boundary right after "complete", but "completely" continues
        # with "ly" so it must NOT match either (same substring-safety check,
        # opposite direction: don't let \b give a false sense of security).
        assert not _is_prompt_triggered("the manuscript is completely done")


class TestIsSubmissionShapedPath:
    def test_matches_manuscript_prefix(self):
        assert _is_submission_shaped_path("docs/manuscript_v2.md")

    def test_matches_docx_extension(self):
        assert _is_submission_shaped_path("output/report.docx")

    def test_matches_paper_prefix(self):
        assert _is_submission_shaped_path("paper_draft.tex")

    def test_matches_cover_letter(self):
        assert _is_submission_shaped_path("cover_letter_v3.md")

    def test_matches_submission_prefix(self):
        assert _is_submission_shaped_path("submission_final.pdf")

    def test_does_not_match_unrelated_file(self):
        assert not _is_submission_shaped_path("hooks/utils.py")

    def test_does_not_match_readme(self):
        assert not _is_submission_shaped_path("README.md")

    def test_matches_case_insensitively(self):
        assert _is_submission_shaped_path("Manuscript_Final.DOCX")


def _run_hook(payload: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    import os

    full_env = os.environ.copy()
    full_env.pop("CLAUDE_INVOKED_BY", None)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=full_env,
        timeout=10,
    )


class TestMainUserPromptSubmit:
    def test_fires_on_submission_prompt(self):
        result = _run_hook({"prompt": "готово отправить статью рецензенту"})
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "Submission Gate" in out["hookSpecificOutput"]["additionalContext"]

    def test_silent_on_generic_prompt(self):
        result = _run_hook({"prompt": "fix the bug in auth.py"})
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_silent_on_empty_payload(self):
        result = _run_hook({})
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestMainPostToolUse:
    def test_fires_on_manuscript_write(self):
        result = _run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "docs/manuscript_v3.md"},
            }
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert GATE_MESSAGE == out["hookSpecificOutput"]["additionalContext"]

    def test_silent_on_unrelated_write(self):
        result = _run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "hooks/some_hook.py"},
            }
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_silent_on_non_write_edit_tool(self):
        result = _run_hook(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "cat manuscript.md"},
            }
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestRecursionGuard:
    def test_silent_when_invoked_by_claude(self):
        result = _run_hook(
            {"prompt": "готово отправить статью рецензенту"},
            env={"CLAUDE_INVOKED_BY": "1"},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""
