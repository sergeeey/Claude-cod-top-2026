"""Tests for lib.runtime.strip_non_user_content — the user-text filter for UserPromptSubmit
keyword hooks (routing_floor_classifier, resource_router, submission_gate_guard).

Origin: Y-17 pilot (2026-09-06) — 4 of 9 NOISE firings were on harness-injected
<system-reminder>/<task-notification> text, not on anything the user typed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from lib.runtime import strip_non_user_content  # noqa: E402

NOTIFICATION = (
    "<system-reminder>\n[SYSTEM NOTIFICATION - NOT USER INPUT]\nThis is an automated event.\n"
    '<task-notification>\n<summary>Agent "Falsify H-B1-1a hypothesis" finished</summary>\n'
    "<result>The experiment is ready; the paper claim was falsified.</result>\n"
    "</task-notification>\n</system-reminder>"
)


def test_pure_notification_becomes_empty():
    assert strip_non_user_content(NOTIFICATION) == ""


def test_user_text_survives_with_trailing_reminder():
    prompt = "rename this variable to foo\n<system-reminder>hypothesis experiment</system-reminder>"
    assert strip_non_user_content(prompt) == "rename this variable to foo"


def test_user_text_survives_with_leading_reminder():
    prompt = "<system-reminder>ready to submit the paper</system-reminder>\nfix the typo in README"
    assert strip_non_user_content(prompt) == "fix the typo in README"


def test_unwrapped_marker_truncates_from_marker_onward():
    prompt = "please format the table\n[SYSTEM NOTIFICATION - NOT USER INPUT] hypothesis causal"
    assert strip_non_user_content(prompt) == "please format the table"


def test_plain_user_prompt_unchanged():
    assert strip_non_user_content("test the hypothesis that X causes Y") == (
        "test the hypothesis that X causes Y"
    )


def test_empty_and_none_safe():
    assert strip_non_user_content("") == ""
    assert strip_non_user_content(None) == ""  # type: ignore[arg-type]


def test_case_insensitive_tags_and_multiline():
    prompt = "<SYSTEM-REMINDER>line1\nline2 falsif</SYSTEM-REMINDER>drop nothing here"
    assert strip_non_user_content(prompt) == "drop nothing here"
