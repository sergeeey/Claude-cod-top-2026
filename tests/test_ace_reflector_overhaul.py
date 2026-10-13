"""Tests for ace_reflector.py's _classify_approach() — construct-validity fix.

WHY this file appears now: a skeptic pass (2026-09-19, invoked via
/boyko-capability-audit to check a claim about harness value) found that
_classify_approach used first-match-wins over a fixed-order keyword list,
with "test-driven" checked before "search-first". Any turn whose message
mentioned both search and test keywords was ALWAYS classified "test-driven",
never "search-first" — regardless of what the turn actually did. Verified
empirically on 1223 real assistant messages from a live session transcript:
100% of the 5 messages containing both keyword categories were diverted to
test-driven, 0% ever reached search-first. Zero tests existed for this
module before this file (verified: no test_ace_reflector.py anywhere under
~/.claude, live or in the hooks_disabled_20260915_202140 backup) — this is
the first coverage, not a rewrite of an existing suite.

Each test below is named for the specific failure mode it guards against,
per this stack's own convention (see hooks_disabled_20260915_202140/tests/
test_ceiling_gate_guard.py's docstring for the same discipline applied
there).
"""

import io
import json
import os
import sys
import time

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

import ace_reflector  # noqa: E402
from ace_reflector import _classify_approach  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    return io.StringIO(json.dumps(data))


def test_single_keyword_match_returns_single_item_list():
    """A message matching exactly one approach still returns a list (API
    changed from str to list[str]), with exactly that one entry."""
    result = _classify_approach("Let me grep for the definition first.")
    assert result == ["search-first"]


def test_no_keyword_match_falls_back_to_general():
    result = _classify_approach("The weather today is nice.")
    assert result == ["general"]


def test_search_and_test_keywords_both_credited_regression():
    """THE regression test for the found bug. Before the fix, a message
    mentioning both search and test-driven keywords was classified ONLY
    "test-driven" because it is checked first in _APPROACH_KEYWORDS. After
    the fix, both approaches the turn actually exhibited are credited."""
    message = "I'll grep for the existing implementation, then assert correctness in a test_ file."
    result = _classify_approach(message)
    assert "search-first" in result, (
        "search-first must not be silently stolen by test-driven's earlier position "
        "in _APPROACH_KEYWORDS — this is exactly the construct-validity bug found 2026-09-19"
    )
    assert "test-driven" in result


def test_message_word_order_does_not_affect_which_approaches_are_returned():
    """Matching is plain substring containment, independent of where a
    keyword appears in the message text -- this was never at risk even in
    the old buggy code (that bug lived in _APPROACH_KEYWORDS's own list
    order, not the message's word order; see the next test for that axis).
    Kept as a basic sanity check on message-text handling, correctly named
    this time (reviewer P2, 2026-09-19: the original docstring claimed this
    exercised the actual bug's axis, and it did not)."""
    msg_test_first = "assert the test_ output matches, now let me grep for related code."
    msg_search_first = "grep for related code, now assert the test_ output matches."
    result_a = set(_classify_approach(msg_test_first))
    result_b = set(_classify_approach(msg_search_first))
    assert result_a == result_b == {"search-first", "test-driven"}


def test_approach_keywords_list_order_does_not_affect_result_regression():
    """THE actual order axis the original bug lived on (reviewer P2,
    2026-09-19): _APPROACH_KEYWORDS's own fixed iteration order used to
    determine which single approach won via first-match-wins. Reversing
    that list must not change the SET of approaches a fixed message
    matches -- if a future edit reintroduces an early `return`/`break`
    inside the loop, THIS test (not the message-word-order one above) is
    the one that catches it."""
    message = "grep for related code, then assert the test_ output matches."
    forward = set(_classify_approach(message))

    original = ace_reflector._APPROACH_KEYWORDS
    try:
        ace_reflector._APPROACH_KEYWORDS = list(reversed(original))
        reversed_order = set(_classify_approach(message))
    finally:
        ace_reflector._APPROACH_KEYWORDS = original

    assert forward == reversed_order == {"search-first", "test-driven"}


def test_three_way_overlap_credits_all_matched_approaches():
    message = (
        "Read the file to understand context, then grep for callers, "
        "then assert correctness in a test_ file."
    )
    result = _classify_approach(message)
    assert set(result) == {"explore-first", "search-first", "test-driven"}


def test_direct_implementation_alone_is_unaffected():
    """Non-overlapping case: fix must not change behavior for messages that
    only ever matched one approach anyway."""
    result = _classify_approach("I'll implement the new function and add it to the module.")
    assert result == ["direct-implementation"]


# --- main() integration tests (reviewer P1, 2026-09-19) ----------------------
# WHY these are needed: all tests above exercise _classify_approach() in
# isolation. The higher-risk half of the fix is main()'s two loops that
# actually WRITE to playbook.md / the pending queue for every matched
# approach -- untested until now.


def _seed_turn(session: str, turn_start: float) -> None:
    state = ace_reflector.HookState(ace_reflector._TURN_STATE_NAME)
    state[session] = turn_start
    state.save()


def _seed_commit_test_gate(last_test: float, last_edit: float) -> None:
    state = ace_reflector.commit_test_gate_state()
    state["last_test"] = last_test
    state["last_edit"] = last_edit
    state.save()


def _make_agent_transcript(
    tmp_path, monkeypatch, session: str, agent_id: str, start: float
) -> None:
    """Per-agent start comes from the agent's own transcript (first-line timestamp)."""
    from datetime import UTC, datetime

    monkeypatch.setattr(ace_reflector, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(ace_reflector, "AGENT_START_CACHE", tmp_path / "no_cache")
    d = tmp_path / "projects" / "proj" / session / "subagents"
    d.mkdir(parents=True)
    stamp = datetime.fromtimestamp(start, UTC).isoformat().replace("+00:00", "Z")
    line = json.dumps({"timestamp": stamp}) + chr(10)
    (d / f"agent-{agent_id}.jsonl").write_text(line, encoding="utf-8")


def _run_main(monkeypatch, payload: dict) -> None:
    monkeypatch.setattr(sys, "stdin", make_stdin(payload))
    try:
        ace_reflector.main()
    except SystemExit:
        pass


def test_main_credits_all_matched_approaches_as_helpful_integration(tmp_path, monkeypatch):
    """A verified test pass happened after turn_start (outcome=helpful) on a
    multi-match message -- main() must record helpful+1 in BOTH matched
    approach buckets, not just one."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")

    session = "test-session-helpful"
    turn_start = time.time() - 100
    _seed_turn(session, turn_start)
    _make_agent_transcript(tmp_path, monkeypatch, session, "agent1", turn_start)
    _seed_commit_test_gate(last_test=time.time() - 50, last_edit=0)

    payload = {
        "session_id": session,
        "agent_type": "explorer",
        "agent_id": "agent1",
        "last_assistant_message": (
            "I grepped for the existing code, then wrote an assert in a test_ file to confirm it."
        ),
    }
    monkeypatch.setattr(sys, "stdin", make_stdin(payload))

    try:
        ace_reflector.main()
    except SystemExit:
        pass

    entries = ace_reflector._load_playbook()
    assert entries.get("search-first", {}).get("helpful") == 1, entries
    assert entries.get("test-driven", {}).get("helpful") == 1, entries


def test_main_pending_queue_gets_one_entry_per_matched_approach_integration(tmp_path, monkeypatch):
    """An edit happened after turn_start with NO verified test pass
    (outcome=harmful, deferred to the pending queue) on a multi-match
    message -- main() must append one pending entry PER matched approach,
    not collapse them into a single entry (Q3 in the review brief: does
    this create a MAX_PENDING growth problem -- it grows faster per-turn,
    flagged by reviewer as an accepted, untested edge case, not fixed here)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")

    session = "test-session-harmful"
    turn_start = time.time() - 100
    _seed_turn(session, turn_start)
    _make_agent_transcript(tmp_path, monkeypatch, session, "agent1", turn_start)
    _seed_commit_test_gate(last_test=0, last_edit=time.time() - 50)

    payload = {
        "session_id": session,
        "agent_type": "explorer",
        "agent_id": "agent1",
        "last_assistant_message": (
            "I grepped for the existing code, then wrote an assert in a test_ file to confirm it."
        ),
    }
    monkeypatch.setattr(sys, "stdin", make_stdin(payload))

    try:
        ace_reflector.main()
    except SystemExit:
        pass

    pending = ace_reflector._load_pending()
    this_session_entries = [e for e in pending if e["session"] == session]
    assert {e["approach"] for e in this_session_entries} == {"search-first", "test-driven"}
    assert len(this_session_entries) == 2


# --- 2026-09-28: typeless-event filter + per-agent outcome window ------------------


def test_typeless_subagent_stop_records_nothing_regression(tmp_path, monkeypatch):
    """73% of real SubagentStop events had an empty agent_type (internal forks:
    prompt suggestions, compaction). They must not touch playbook or pending."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")
    session = "sess-typeless"
    _seed_turn(session, time.time() - 100)
    _seed_commit_test_gate(last_test=time.time() - 50, last_edit=0)
    _make_agent_transcript(tmp_path, monkeypatch, session, "fork1", time.time() - 100)

    for blank in ("", "   ", None):
        payload = {
            "session_id": session,
            "agent_id": "fork1",
            "last_assistant_message": "закоммить и запушь",
        }
        if blank is not None:
            payload["agent_type"] = blank
        _run_main(monkeypatch, payload)

    assert not (tmp_path / "playbook.md").exists()
    assert ace_reflector._load_pending() == []


def test_outcome_window_starts_at_agent_start_not_session_stamp_regression(tmp_path, monkeypatch):
    """A test pass BEFORE this agent started but AFTER the session's last Agent launch
    used to be credited to this agent. With the per-agent window it must not be."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")
    session = "sess-window"
    now = time.time()
    _seed_turn(session, now - 3600)  # stale session-wide stamp: 1h ago
    _seed_commit_test_gate(last_test=now - 1800, last_edit=0)  # pass 30 min ago
    # agent started 1 min ago
    _make_agent_transcript(tmp_path, monkeypatch, session, "agentW", now - 60)

    _run_main(
        monkeypatch,
        {
            "session_id": session,
            "agent_type": "Explore",
            "agent_id": "agentW",
            "last_assistant_message": "I grepped the tree for callers, none outstanding.",
        },
    )
    assert not (tmp_path / "playbook.md").exists(), "pre-start test pass must not credit this agent"


def test_agent_without_resolvable_start_records_nothing(tmp_path, monkeypatch):
    """No transcript and no start cache -> no window -> no outcome (no silent fallback
    to the unbounded session-wide stamp)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")
    monkeypatch.setattr(ace_reflector, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(ace_reflector, "AGENT_START_CACHE", tmp_path / "no_cache")
    session = "sess-nostart"
    _seed_turn(session, time.time() - 100)
    _seed_commit_test_gate(last_test=time.time() - 50, last_edit=0)

    _run_main(
        monkeypatch,
        {
            "session_id": session,
            "agent_type": "reviewer",
            "agent_id": "ghost",
            "last_assistant_message": "I grepped the tree for callers, none outstanding.",
        },
    )
    assert not (tmp_path / "playbook.md").exists()


def test_stop_agent_type_blank_and_missing_are_none():
    assert ace_reflector._stop_agent_type({}) is None
    assert ace_reflector._stop_agent_type({"agent_type": ""}) is None
    assert ace_reflector._stop_agent_type({"agent_type": "  "}) is None
    assert ace_reflector._stop_agent_type({"agent_type": "skeptic"}) == "skeptic"


# --- 2026-09-28 recommendation 3: timestamped event log ----------------------


def _read_events(path):
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_typeless_event_is_logged_with_skipped_decision(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")
    session = "sess-log-typeless"
    _seed_turn(session, time.time() - 100)
    _make_agent_transcript(tmp_path, monkeypatch, session, "fork2", time.time() - 100)

    _run_main(
        monkeypatch,
        {"session_id": session, "agent_id": "fork2", "last_assistant_message": "оформляй"},
    )

    events = _read_events(tmp_path / "ace_events.jsonl")
    assert len(events) == 1
    assert events[0]["decision"] == "skipped_typeless"
    assert events[0]["msg_head"] == "оформляй"


def test_recorded_event_carries_window_and_pending_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")
    session = "sess-log-recorded"
    turn_start = time.time() - 100
    _seed_turn(session, turn_start)
    _seed_commit_test_gate(last_test=time.time() - 50, last_edit=0)
    _make_agent_transcript(tmp_path, monkeypatch, session, "agentL", turn_start)

    _run_main(
        monkeypatch,
        {
            "session_id": session,
            "agent_type": "tester",
            "agent_id": "agentL",
            "last_assistant_message": "grep for code, assert in a test_ file.",
        },
    )

    events = _read_events(tmp_path / "ace_events.jsonl")
    assert len(events) == 1
    e = events[0]
    assert e["decision"] == "recorded"
    assert e["outcome"] == "helpful"
    assert set(e["approaches"]) == {"search-first", "test-driven"}
    assert e["playbook_written"] is True
    assert e["window_s"] >= 0
    assert e["start_epoch"] is not None


def test_no_start_event_has_null_window_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")
    monkeypatch.setattr(ace_reflector, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(ace_reflector, "AGENT_START_CACHE", tmp_path / "no_cache")
    session = "sess-log-nostart"
    _seed_turn(session, time.time() - 100)

    _run_main(
        monkeypatch,
        {
            "session_id": session,
            "agent_type": "reviewer",
            "agent_id": "ghost2",
            "last_assistant_message": "grep for code, assert in a test_ file.",
        },
    )

    events = _read_events(tmp_path / "ace_events.jsonl")
    assert len(events) == 1
    assert events[0]["decision"] == "no_start"
    assert events[0]["outcome"] is None
    assert events[0]["start_epoch"] is None
    assert events[0]["window_s"] is None


def test_log_event_never_raises_on_write_failure(monkeypatch, tmp_path):
    """A directory in place of the log file must not turn telemetry into a hook crash."""
    bad_path = tmp_path / "not_a_file"
    bad_path.mkdir()
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", bad_path)  # open() on a dir raises
    ace_reflector._log_event("recorded", {"session_id": "s", "agent_id": "a"})  # must not raise


# --- 2026-09-28 recommendation 5: classify from ACTUAL tool calls, not message text ---


def _transcript_with_tools(tmp_path, monkeypatch, session, agent_id, start, tool_uses):
    """Like _make_agent_transcript, but appends assistant lines carrying tool_use blocks.
    `tool_uses` is a list of (tool_name, input_dict) tuples."""
    _make_agent_transcript(tmp_path, monkeypatch, session, agent_id, start)
    path = tmp_path / "projects" / "proj" / session / "subagents" / f"agent-{agent_id}.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        for name, inp in tool_uses:
            block = {"type": "tool_use", "name": name, "input": inp}
            line = {"type": "assistant", "message": {"role": "assistant", "content": [block]}}
            fh.write(json.dumps(line) + chr(10))


def test_grep_and_glob_tool_calls_classify_as_search_first(tmp_path, monkeypatch):
    _transcript_with_tools(
        tmp_path,
        monkeypatch,
        "s1",
        "a1",
        time.time() - 10,
        [("Grep", {"pattern": "foo"}), ("Glob", {"pattern": "*.py"})],
    )
    assert ace_reflector._classify_from_tool_calls("s1", "a1") == ["search-first"]


def test_bash_pytest_classifies_as_test_driven(tmp_path, monkeypatch):
    _transcript_with_tools(
        tmp_path,
        monkeypatch,
        "s2",
        "a2",
        time.time() - 10,
        [("Bash", {"command": "python -m pytest tests/ -q"})],
    )
    assert ace_reflector._classify_from_tool_calls("s2", "a2") == ["test-driven"]


def test_mixed_tool_calls_credit_every_matched_approach(tmp_path, monkeypatch):
    _transcript_with_tools(
        tmp_path,
        monkeypatch,
        "s3",
        "a3",
        time.time() - 10,
        [("Grep", {"pattern": "x"}), ("Read", {"file_path": "f"}), ("Edit", {"file_path": "g"})],
    )
    got = ace_reflector._classify_from_tool_calls("s3", "a3")
    assert got == ["direct-implementation", "explore-first", "search-first"]


def test_no_transcript_returns_none_for_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(ace_reflector, "PROJECTS_DIR", tmp_path / "empty")
    assert ace_reflector._classify_from_tool_calls("s4", "ghost") is None


def test_transcript_without_recognized_tools_returns_none(tmp_path, monkeypatch):
    _transcript_with_tools(
        tmp_path, monkeypatch, "s5", "a5", time.time() - 10, [("SomeUnknownTool", {})]
    )
    assert ace_reflector._classify_from_tool_calls("s5", "a5") is None


def test_main_uses_tool_calls_over_misleading_message_text(tmp_path, monkeypatch):
    """The agent's closing message mentions NOTHING about searching, but its transcript
    shows a real Grep call -- tool-call classification must win over text keywords."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")
    session = "sess-toolcls"
    start = time.time() - 100
    _seed_turn(session, start)
    _seed_commit_test_gate(last_test=time.time() - 50, last_edit=0)
    _transcript_with_tools(
        tmp_path, monkeypatch, session, "agentT", start, [("Grep", {"pattern": "needle"})]
    )

    _run_main(
        monkeypatch,
        {
            "session_id": session,
            "agent_type": "Explore",
            "agent_id": "agentT",
            "last_assistant_message": "Done. Nothing to report beyond the summary above.",
        },
    )

    entries = ace_reflector._load_playbook()
    assert entries.get("search-first", {}).get("helpful") == 1, entries
    assert "general" not in entries, "text fallback must not fire when tool calls classified it"


def _bash_label(tmp_path, monkeypatch, tag, cmd):
    _transcript_with_tools(
        tmp_path, monkeypatch, "s" + tag, "a" + tag, time.time() - 10, [("Bash", {"command": cmd})]
    )
    return ace_reflector._classify_from_tool_calls("s" + tag, "a" + tag)


def test_bash_heuristics_true_positives(tmp_path, monkeypatch):
    cases = {
        "python -m pytest tests/ -q": ["test-driven"],
        "python -m unittest": ["test-driven"],
        "npm test": ["test-driven"],
        "cargo test --release": ["test-driven"],
        "python test_foo.py": ["test-driven"],
        "grep -rn foo src": ["search-first"],
        "cat x | grep y": ["search-first"],
        "git grep needle": ["search-first"],
        "find . -name '*.py'": ["search-first"],
    }
    for i, (cmd, want) in enumerate(cases.items()):
        assert _bash_label(tmp_path, monkeypatch, f"p{i}", cmd) == want, cmd


def test_bash_heuristics_false_positives_regression(tmp_path, monkeypatch):
    """Reviewer 2026-09-29 reproduced each of these as a wrong label. Also guards a dead
    regex: an earlier word-boundary patch wrote a literal backspace instead of backslash-b."""
    for i, cmd in enumerate(
        [
            "git log --oneline latest",
            "cat contest.txt",
            "echo attestation",
            "cat tests/test_a.py",
            "ls tests",
            "git commit -m 'add test'",
            "jq --arg x 1 .",
            "cargo build --org x",
        ]
    ):
        assert _bash_label(tmp_path, monkeypatch, f"n{i}", cmd) is None, cmd


def test_non_dict_json_lines_and_string_input_do_not_crash(tmp_path, monkeypatch):
    """Reviewer P2: [1,2] / "str" / null lines and a string tool input raised
    AttributeError out of main()."""
    _make_agent_transcript(tmp_path, monkeypatch, "sj", "aj", time.time() - 10)
    path = tmp_path / "projects" / "proj" / "sj" / "subagents" / "agent-aj.jsonl"
    good = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Grep"}]}}
    bad_input = {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": "Bash", "input": "str"}]},
    }
    with open(path, "a", encoding="utf-8") as fh:
        for line in ("[1, 2]", '"str"', "null", json.dumps(bad_input), json.dumps(good)):
            fh.write(line + chr(10))
    assert ace_reflector._classify_from_tool_calls("sj", "aj") == ["search-first"]

    only_list = tmp_path / "projects" / "proj" / "sk" / "subagents"
    only_list.mkdir(parents=True)
    (only_list / "agent-ak.jsonl").write_text("[1]" + chr(10), encoding="utf-8")
    assert ace_reflector._agent_start_ts("sk", "ak") is None


def test_legacy_pending_entries_without_a_window_are_dropped_uncounted():
    """Reviewer P2 (reproduced): turn_start=None became 0 and was credited helpful by any
    later test pass; a missing stamped_at never expired."""
    playbook: dict = {}
    pending = [
        {"approach": "general", "turn_start": None, "stamped_at": 1.0},
        {"approach": "general", "turn_start": 5.0},
        {"approach": "test-driven", "turn_start": 5.0, "stamped_at": 10.0, "example": "x"},
    ]
    left = ace_reflector._resolve_pending(pending, playbook, now=20.0, last_test=100.0)
    assert left == []
    assert "general" not in playbook, playbook
    assert playbook["test-driven"]["helpful"] == 1


def test_null_last_assistant_message_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ace_reflector, "PLAYBOOK_PATH", tmp_path / "playbook.md")
    monkeypatch.setattr(ace_reflector, "EVENT_LOG", tmp_path / "ace_events.jsonl")
    session = "sess-null-msg"
    _seed_turn(session, time.time() - 100)
    _make_agent_transcript(tmp_path, monkeypatch, session, "agentN", time.time() - 100)
    _run_main(
        monkeypatch,
        {
            "session_id": session,
            "agent_type": "Explore",
            "agent_id": "agentN",
            "last_assistant_message": None,
        },
    )
    events = _read_events(tmp_path / "ace_events.jsonl")
    assert len(events) == 1 and events[0]["decision"] in {"recorded", "no_start"}
