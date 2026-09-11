#!/usr/bin/env python3
"""Tests for hooks/routing_floor_classifier.py — the deterministic task-tier safety-floor
classifier that makes the routing floor code-enforced instead of LLM-discretionary.

Key properties:
- deterministic detection of SECURITY / DESTRUCTIVE / RESEARCH task signals (bilingual);
- NO false injection on benign prompts (over-injecting would be noise);
- injects context only, never blocks (a shadow-safe enforcement of the CLASSIFICATION).
"""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HOOK = ROOT / "hooks" / "routing_floor_classifier.py"

# WHY a fake HOME for every subprocess invocation (fixed 2026-09-12, found live):
# this hook's classify() now calls lib.state.log_route_decision(), which resolves
# its log path from Path.home() at import time INSIDE THE SUBPROCESS -- a
# monkeypatch in the parent pytest process has no effect on a child process's own
# environment. Without this, every one of this file's ~50 subprocess-based test
# invocations appended a real line to this machine's actual
# ~/.claude/logs/routing_events.jsonl, mixing hundreds of synthetic test prompts
# into genuine usage telemetry (found by inspecting that file directly: 722 lines,
# many carrying this file's own literal test prompts, session_id="test"). Overriding
# HOME/USERPROFILE redirects Path.home() for the subprocess only, isolating every
# test run from the real machine's logs the same way tmp_log() already isolates
# in-process calls in tests/test_hook_triggers_telemetry.py.
_FAKE_HOME = tempfile.mkdtemp(prefix="routing_floor_test_home_")
atexit.register(shutil.rmtree, _FAKE_HOME, ignore_errors=True)


def _run(prompt: str) -> str:
    """Run the hook with a prompt, return its stdout (the injected context, if any)."""
    payload = json.dumps({"prompt": prompt, "session_id": "test"})
    env = {
        "CLAUDE_INVOKED_BY": "",  # bypass recursion guard is NOT wanted; empty = proceed
        "HOME": _FAKE_HOME,
        "USERPROFILE": _FAKE_HOME,  # Path.home() on Windows reads this, not HOME
    }

    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        cwd=str(ROOT),
    )
    assert r.returncode == 0, f"hook must never crash / block (exit {r.returncode}): {r.stderr}"
    return r.stdout


@pytest.mark.parametrize(
    "prompt,tier",
    [
        ("add oauth token refresh to the auth flow", "SECURITY"),
        ("store the api_key in the config", "SECURITY"),
        ("переделай платёжный модуль", "SECURITY"),
        ("drop table users and migrate the schema", "DESTRUCTIVE"),
        ("run rm -rf on the cache dir", "DESTRUCTIVE"),
        ("снести миграцию и пересоздать таблицу", "DESTRUCTIVE"),
        ("test the hypothesis that X causes Y", "RESEARCH"),
        ("проверить гипотезу о причинной связи", "RESEARCH"),
    ],
)
def test_detects_tier(prompt, tier):
    out = _run(prompt)
    assert f"[routing-floor] {tier}" in out, f"expected {tier} tier for: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "rename this variable to foo",
        "add a docstring to the function",
        "what does this regex match",
        "format the readme table",
    ],
)
def test_benign_prompt_injects_nothing(prompt):
    """A benign prompt must NOT trigger a floor injection -- over-injecting is noise that
    would train the reader to ignore the signal."""
    out = _run(prompt).strip()
    assert "[routing-floor]" not in out, f"false injection on benign prompt {prompt!r}: {out!r}"


def test_empty_prompt_is_silent():
    assert "[routing-floor]" not in _run("")


@pytest.mark.parametrize(
    "prompt",
    [
        # pure agent-completion notification carrying RESEARCH signal words — not a user task
        "<system-reminder>\n[SYSTEM NOTIFICATION - NOT USER INPUT]\n<task-notification>"
        '<summary>Agent "Falsify H-B1-1a hypothesis" finished</summary>'
        "<result>experiment falsified the causal claim</result></task-notification>"
        "</system-reminder>",
        # benign user text + a trailing harness block that contains a SECURITY word
        "rename this variable to foo\n<system-reminder>hooks: password rotation reminder"
        "</system-reminder>",
    ],
)
def test_harness_injected_text_is_ignored(prompt):
    """Regression (Y-17 pilot 2026-09-06): 2 of 3 NOISE firings of this hook were on
    <task-notification> text from finished subagents, not on anything the user typed."""
    out = _run(prompt).strip()
    assert "[routing-floor]" not in out, f"fired on harness text: {out!r}"


def test_user_text_still_classified_when_reminder_attached():
    out = _run("test the hypothesis that X causes Y\n<system-reminder>ctx</system-reminder>")
    assert "[routing-floor] RESEARCH" in out


@pytest.mark.parametrize(
    "prompt",
    [
        "this response cost about 150 tokens",
        "сколько токенов осталось в контексте",
        "the context window holds 200k tokens",
        "у нас ушло ~2000 токенов на этот ответ",
    ],
)
def test_bare_llm_token_mention_does_not_fire_security(prompt):
    """Regression (audit, 2026-09-06, live-found in this exact session): bare
    "token"/"токен" is a genuine homograph -- an auth/API token and an
    LLM/context token -- and the SECURITY tier previously fired on ordinary
    LLM-cost discussion with zero actual security content. Real auth-token
    prompts still fire via the other words already in the pattern (auth,
    credential, secret, api key, oauth, jwt) -- see test_detects_tier above."""
    out = _run(prompt).strip()
    assert "[routing-floor] SECURITY" not in out, (
        f"false SECURITY fire on: {prompt!r}\ngot: {out!r}"
    )


@pytest.mark.parametrize(
    "prompt,tier",
    [
        ("refresh the oauth token before it expires", "SECURITY"),
        ("the api token needs rotation, check the credential store", "SECURITY"),
        ("обнови токен авторизации в конфиге", "SECURITY"),
    ],
)
def test_token_mention_with_auth_context_still_fires_security(prompt, tier):
    """The fix removes the STANDALONE token/токен alternative, not security
    coverage overall -- a real auth-token prompt still fires via the other
    words already in the pattern (auth, credential, oauth, авторизац)."""
    out = _run(prompt)
    assert f"[routing-floor] {tier}" in out, f"expected {tier} tier for: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        # Windows path pasted verbatim -- ".env" is part of a file path, not a mention.
        "[env] Loaded 33 keys from C:\\Users\\serge\\.env",
        # git branch names pasted verbatim -- the words are slug fragments, not prose.
        "git branch -D refactor/migrate-utils-facade-call-sites",
        "git log fix/backport-hypothesis-router-fixes",
    ],
)
def test_slug_or_path_embedded_word_does_not_fire(prompt):
    """Regression (audit, 2026-09-07, live-found in this exact session): pasting a
    PowerShell transcript containing a Windows path and a list of git branch names
    fired SECURITY on ".env" (part of "C:\\Users\\serge\\.env"), DESTRUCTIVE on
    "migrate" (part of "refactor/migrate-utils-facade-call-sites"), and RESEARCH on
    "hypothesis" (part of "fix/backport-hypothesis-router-fixes") -- three literal
    substring matches inside path/identifier tokens, none of them an actual mention
    of the concept in natural language. See test_detects_tier and
    test_env_migrate_hypothesis_prose_still_fires for the coverage this must not lose."""
    out = _run(prompt).strip()
    assert "[routing-floor]" not in out, f"false fire on slug/path text: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt,tier",
    [
        ("check the .env file for leaked secrets", "SECURITY"),
        ("don't commit your .env to git", "SECURITY"),
        ("we need to migrate the database this weekend", "DESTRUCTIVE"),
        ("plan the migration of user data", "DESTRUCTIVE"),
        ("I have two hypotheses to compare", "RESEARCH"),
    ],
)
def test_env_migrate_hypothesis_prose_still_fires(prompt, tier):
    """The fix only excludes hyphen/path-adjacent slug embedding -- real natural-language
    mentions of .env, migrate/migration, and hypothesis/hypotheses (including plural)
    must still fire exactly as before."""
    out = _run(prompt)
    assert f"[routing-floor] {tier}" in out, f"expected {tier} tier for: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt,tier",
    [
        ("store wearable health data and biometric readings", "SECURITY"),
        ("need HIPAA compliance for this health app", "SECURITY"),
        ("import patient data from the medical record system", "SECURITY"),
        ("track the user's mental health over time", "SECURITY"),
        ("psychiatric evaluation notes go in this table", "SECURITY"),
        (
            "помогать людям отслеживать своё психоэмоциональное состояние и данные о здоровье",
            "SECURITY",
        ),
        ("нужна биометрическая аутентификация по отпечатку пальца", "SECURITY"),
        ("выгрузи медицинские данные пациента в отчёт", "SECURITY"),
    ],
)
def test_health_biometric_data_fires_security(prompt, tier):
    """Health/biometric data is special-category PII (GDPR Art.9) and was previously
    entirely unmatched by this tier — added 2026-09-08 after a live gap was found:
    a real mental-health-tracking app idea produced zero floor injection."""
    out = _run(prompt)
    assert f"[routing-floor] {tier}" in out, f"expected {tier} tier for: {prompt!r}\ngot: {out!r}"


@pytest.mark.parametrize(
    "prompt",
    [
        "run vault-health skill to audit the obsidian vault",
        "какие узкие места, покажи project health check проекта",
        "the research_health_loop.py hook fired at session start, system healthy",
        "add a healthcheck endpoint to the API",
        "как здоровье архитектуры проекта после рефакторинга",
    ],
)
def test_bare_health_mention_does_not_fire_security(prompt):
    """Regression guard for the new health/biometric alternative: this repo's own
    catalog uses bare "health"/"здоровье" heavily for architecture/CI meaning
    (vault-health skill, research_health_loop.py, "project health check", "System
    healthy" in pattern_escalation_review.py) — the new alternative is deliberately
    scoped to compound health-DATA phrases, not the bare word, to avoid repeating
    the exact false-positive class the "token" removal above already fixed once."""
    out = _run(prompt).strip()
    assert "[routing-floor] SECURITY" not in out, (
        f"false SECURITY fire on: {prompt!r}\ngot: {out!r}"
    )


# === quoted-content suppression (added 2026-09-12) ===
#
# WHY end-to-end tests here too, not just in test_classification_signals.py's
# unit tests for is_likely_quoted_occurrence: this hook's main() re-checks the
# trailing window against the SAME matcher before honoring suppression --
# that composition is only exercised by running the actual hook.

# WHY varied section text, not one block repeated N times: an earlier draft
# repeated a single "credential"-containing block to reach length, which put
# a SECOND occurrence of the same word inside the suppression check's own
# trailing re-scan window purely from the repeat cadence -- a fixture
# artifact, not the real incident shape, and it defeated the very regression
# test it was meant to support (found live: replaced repetition with varied
# section text and the false failure disappeared). Real pasted analyses
# don't repeat a paragraph; each section here is distinct so the buried
# SECURITY word occurs exactly once, nowhere near the tail.
_PASTED_DOC = (
    "# Architecture comparison\n\n"
    "## Section 1 — Overview\n\n"
    "This section lays out the general shape of the third-party system under "
    "discussion, its major components, and how they relate to one another in "
    "broad strokes before any detailed comparison begins. ([Some Source][1])\n\n"
    "## Section 2 — Deep dive\n\n"
    "Here the analysis goes further into specifics: how each subsystem "
    "communicates, what assumptions it makes about its environment, and where "
    "the credential handling in that other system fits into the larger flow. "
    "([Some Source][2])\n\n"
    "## Section 3 — Prior art\n\n"
    "A survey of related approaches from other projects, comparing tradeoffs "
    "across several dimensions and citing the sources each claim rests on. "
    "([Some Source][3])\n\n"
    "## Section 4 — Open questions\n\n"
    "Several open questions remain about how well this generalizes, what the "
    "failure modes look like under load, and whether the same design would "
    "hold up outside its original context. ([Some Source][4])\n\n"
    "## Section 5 — Summary table\n\n"
    "| Aspect | This system | Alternative |\n|---|---|---|\n"
    "| Latency | low | medium |\n| Complexity | medium | high |\n"
    "| Maturity | new | established |\n\n"
    "## Section 6 — Closing thoughts\n\n"
    "Taken together, the comparison suggests a mixed picture: some ideas "
    "transfer cleanly, others depend heavily on assumptions that may not hold "
    "in a different setting, and a few remain genuinely open. ([Some Source][5])\n\n"
    "## Section 7 — Recommendations\n\n"
    "Given everything above, the most defensible next step is a small, "
    "reversible experiment rather than a wholesale adoption of the compared "
    "design, since the evidence so far only supports a narrow claim about "
    "where the two systems actually differ in practice. ([Some Source][6])\n\n"
)
assert len(_PASTED_DOC) > 1500  # must clear the quoted-content length threshold


def test_keyword_buried_in_long_pasted_document_does_not_fire():
    """The real incident this session hit four times: a tier keyword sitting
    deep inside a long pasted analysis, followed by an unrelated short live
    instruction. Must not inject the SECURITY floor."""
    prompt = _PASTED_DOC + "оцень внимательно изучи и сравни с нашей реализацией"
    out = _run(prompt).strip()
    assert "[routing-floor] SECURITY" not in out, f"false fire on pasted-document tail: {out!r}"


def test_live_security_ask_after_a_long_paste_still_fires():
    """The regression this heuristic must never cause: a genuine live security
    ask that happens to follow a long paste must still inject the floor."""
    prompt = _PASTED_DOC + "now go check the credential store for this repo"
    out = _run(prompt)
    assert "[routing-floor] SECURITY" in out, f"suppressed a genuine live ask: {out!r}"


def test_live_ask_followed_by_more_pasted_content_is_a_documented_limitation():
    """This asserts the CURRENT, intentional behavior (Design 3, see
    routing_floor_classifier.py's classify() for the full design history),
    not a bug -- it is a documented, accepted limitation, not something this
    test is trying to force to pass artificially. A live directive followed
    by STILL MORE pasted content after it (a stack trace, another paste) IS
    currently suppressed. This shape has never been observed in real usage;
    Design 2 briefly fixed it but broke a more realistic, actually-observed
    shape the same night (see test_topic_restated_in_later_section_still_
    suppressed below) -- reverted in favor of the realistic case. Revisit
    this test (change the assertion to require the floor fires) only if this
    shape is ever genuinely observed."""
    prompt = (
        "# Section 1\n\n"
        "The hypothesis testing methodology of the third-party paper is discussed here. "
        + ("Long analysis text repeated for padding purposes. " * 40)
        + "\n\nplease analyze the causal experiment on our production data now.\n\n"
        "# Section 2\n\n" + ("Table row with number 42 and more filler text here. " * 20)
    )
    assert len(prompt) > 1500
    out = _run(prompt).strip()
    assert "[routing-floor] RESEARCH" not in out, (
        f"expected the documented limitation (suppressed); code behavior changed -- "
        f"update this test's assertion deliberately if that was intentional: {out!r}"
    )


def test_topic_restated_in_later_section_still_suppressed():
    """Real-task-eval finding (2026-09-12): a realistic postmortem-shaped
    document that restates its own topic in a LATER, separate section (a
    normal thing for a real document to do) must still be suppressed when
    followed by a benign trailing question -- Design 2 (re-check from the
    match's own paragraph break onward) wrongly treated the later section's
    restatement as an independent live signal. Design 3 (re-check only the
    prompt's own last paragraph) fixes this."""
    doc = (
        "# Postmortem: Vendor X outage, 2026-08-14\n\n"
        "## Timeline\n\n"
        "At 03:12 UTC the vendor's edge fleet began rejecting a growing share "
        "of requests with 503s. On-call there paged within four minutes, but "
        "root cause wasn't isolated until nearly an hour later. "
        "([Vendor status page][1])\n\n"
        "## Root cause\n\n"
        "A configuration push rotated an internal service credential earlier "
        "than the consumers expected, and several downstream services kept "
        "retrying with the stale value instead of failing fast, which "
        "amplified load on the auth layer until it fell over entirely. "
        "([Internal writeup][2])\n\n"
        "## Contributing factors\n\n"
        "No canary stage existed for this particular config path, and the "
        "rollback tooling assumed a single global config version rather than "
        "per-region staggering, so the fix took longer to fully propagate "
        "than it should have. ([Engineering blog][3])\n\n"
        "## What they changed afterward\n\n"
        "A staged rollout requirement for any change touching credential "
        "rotation, plus an explicit fail-fast policy for auth-layer retries "
        "instead of exponential backoff against a dead dependency.\n\n"
        "## Customer impact\n\n"
        "Roughly forty minutes of degraded service for the affected region, "
        "with a long tail of retried requests visible in downstream metrics "
        "for another two hours after the underlying issue was resolved. "
        "([Status history][4])\n\n"
        "## Open questions for our own systems\n\n"
        "It's worth checking whether any of our own services have the same "
        "unbounded-retry-against-a-dead-dependency shape, independent of "
        "whether we ever touch credential rotation the same way this vendor "
        "does.\n\n"
    )
    assert len(doc) > 1500
    prompt = doc + "what would you estimate the blast radius was in dollar terms?"
    out = _run(prompt).strip()
    assert "[routing-floor] SECURITY" not in out, (
        f"false fire on topic restated in a later document section: {out!r}"
    )


def test_live_ask_after_topic_restated_in_later_section_still_fires():
    """The regression this MUST never cause: a genuine live SECURITY ask
    trailing the same restated-topic document must still fire."""
    doc = (
        "# Postmortem: Vendor X outage, 2026-08-14\n\n"
        "## Root cause\n\n"
        "A configuration push rotated an internal service credential earlier "
        "than expected. ([Internal writeup][1])\n\n"
        "## Open questions for our own systems\n\n"
        "It's worth checking whether we have the same credential rotation "
        "exposure ourselves. ([Notes][2])\n\n"
        + ("More surrounding discussion padding this document out further. " * 30)
        + "\n\n"
    )
    assert len(doc) > 1500, len(doc)
    prompt = (
        doc
        + "now go check whether we have the same missing canary stage "
        + "for our own credential rotation path"
    )
    out = _run(prompt)
    assert "[routing-floor] SECURITY" in out, f"suppressed a genuine live ask: {out!r}"


def test_crlf_pasted_document_with_benign_tail_still_suppressed():
    """Skeptic-found bug (2026-09-12, confirmed by direct execution before
    fixing): Design 3's first cut used `prompt.rfind("\\n\\n")`, which finds
    nothing in a CRLF-formatted document ("\\r\\n\\r\\n" paragraph breaks
    contain no bare "\\n\\n" substring) and fell back to the WHOLE prompt --
    which made the independent-signal re-check collapse to the same call
    that already matched, silently disabling suppression for ANY prompt
    without a bare "\\n\\n". Fixed by matching `\\r?\\n` paragraph breaks and
    falling back to an EMPTY tail region (not the whole prompt) when none
    exist at all."""
    doc = (
        "# Doc\r\n\r\n"
        "## Section 1\r\n\r\n"
        "Some long analysis text here discussing a third-party system in "
        "detail. ([Src][1])\r\n\r\n"
        "## Section 2\r\n\r\n"
        "credential handling discussed here at length in prose, many words "
        "to pad this out. ([Src][2])\r\n\r\n"
        "## Section 3\r\n\r\n"
        + ("More unrelated padding text repeated many times over. " * 30)
        + "\r\n\r\n"
    )
    assert len(doc) > 1500, len(doc)
    prompt = doc + "what would you estimate the blast radius was in dollar terms?"
    out = _run(prompt).strip()
    assert "[routing-floor] SECURITY" not in out, (
        f"false fire on CRLF-formatted pasted document: {out!r}"
    )


def test_crlf_pasted_document_with_live_ask_still_fires():
    """The regression the CRLF fix MUST never cause: a genuine live SECURITY
    ask trailing a CRLF-formatted document must still fire."""
    doc = (
        "# Doc\r\n\r\n"
        "## Section 1\r\n\r\n"
        "Some long analysis text here discussing a third-party system in "
        "detail. ([Src][1])\r\n\r\n"
        "## Section 2\r\n\r\n"
        "credential handling discussed here at length in prose, many words "
        "to pad this out. ([Src][2])\r\n\r\n"
        "## Section 3\r\n\r\n"
        + ("More unrelated padding text repeated many times over. " * 30)
        + "\r\n\r\n"
    )
    assert len(doc) > 1500, len(doc)
    prompt = (
        doc + "now go check whether we have the same missing canary stage "
        "for our credential rotation path"
    )
    out = _run(prompt)
    assert "[routing-floor] SECURITY" in out, f"suppressed a genuine live ask: {out!r}"


def test_document_shaped_prompt_with_no_paragraph_breaks_still_suppressed():
    """Safe-fallback regression pin: a long, document-shaped prompt (markdown
    header, length >=1500) that has NO paragraph break anywhere at all must
    still be suppressed (empty tail region, per this file's own
    asymmetric-cost convention -- "can't find a last paragraph" biases
    toward suppression, not toward silently disabling the check)."""
    prompt = (
        "# Doc\n"
        + ("word " * 200)
        + "credential "
        + ("word " * 200)
        + "what would you estimate the blast radius"
    )
    assert len(prompt) > 1500, len(prompt)
    assert "\n\n" not in prompt
    assert "\r\n\r\n" not in prompt
    out = _run(prompt).strip()
    assert "[routing-floor] SECURITY" not in out, (
        f"false fire on a no-paragraph-break document-shaped prompt: {out!r}"
    )


def test_same_paragraph_synonym_repeat_still_suppressed():
    """The other side of the same fix: a single buried paragraph that restates
    the same tier concept with a synonym ("hypotheses ... causal ... experiment"
    all in one sentence) must NOT be treated as an independent live signal just
    because the regex matches again a few words later in the SAME paragraph."""
    prompt = (
        "# Section 1\n\n"
        "Some long analysis text here discussing a third-party system in detail, "
        "paragraph after paragraph of description. ([Some Source][1])\n\n"
        "## Section 2\n\n"
        "Here the analysis goes further into specifics, testing several hypotheses "
        "about causal mechanisms along the way as part of one experiment after "
        "another. ([Some Source][2])\n\n"
        "## Section 3\n\n"
        + ("More unrelated discussion padding out this document further. " * 20)
        + "\n\nоцень внимательно изучи и сравни с нашей реализацией"
    )
    assert len(prompt) > 1500
    out = _run(prompt).strip()
    assert "[routing-floor] RESEARCH" not in out, (
        f"false fire on same-paragraph synonym repeat: {out!r}"
    )


def test_never_blocks_even_on_security_prompt():
    """Non-blocking is the safety property: this hook injects, it must never deny/exit(1)."""
    # covered by the exit-0 assertion in _run, but assert explicitly for the security case
    payload = json.dumps({"prompt": "delete the auth secret from the database", "session_id": "t"})

    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CLAUDE_INVOKED_BY": "",
            "HOME": _FAKE_HOME,
            "USERPROFILE": _FAKE_HOME,
        },
        cwd=str(ROOT),
    )
    assert r.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
