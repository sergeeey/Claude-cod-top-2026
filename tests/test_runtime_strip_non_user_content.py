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


PEER = (
    "Another Claude session sent a message:\n"
    '<agent-message from="abc123">\n[Subagent hand-back] The report follows:\n'
    "  the migration experiment; hypothesis [HYPOTHESIS]; a token and a password mentioned\n"
    "</agent-message>\n\nThat session is an agent working inside this same session."
)


def test_agent_message_block_is_removed():
    out = strip_non_user_content(PEER)
    for word in ("migration", "hypothesis", "token", "password"):
        assert word not in out.lower()


def test_user_text_around_an_agent_message_survives():
    prompt = "please rename foo to bar\n" + PEER
    assert "please rename foo to bar" in strip_non_user_content(prompt)


def test_agent_message_tag_is_case_insensitive_and_multiline():
    prompt = "<AGENT-MESSAGE from='x'>line1\nline2 falsif</AGENT-MESSAGE>keep this"
    assert strip_non_user_content(prompt) == "keep this"


def test_user_text_that_merely_mentions_the_tag_name_is_untouched():
    text = "explain what an agent-message is in our docs"
    assert strip_non_user_content(text) == text


def test_unterminated_agent_message_is_left_alone():
    # No closing tag: nothing is removed (same behaviour as the other wrappers).
    text = '<agent-message from="x"> hypothesis'
    assert strip_non_user_content(text) == text
