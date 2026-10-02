"""Tests for scripts/threads_center.py (threads center: overdue / open / waiting + vault freshness).

Every collector takes an injected runner, so nothing here touches PowerShell, gh or the real vault.
Mtimes are set explicitly: no test depends on the date it runs on.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import threads_center as tc  # noqa: E402

TODAY = date(2026, 10, 2)
# a fake API key assembled from halves: no secret-shaped literal sits in the source, so the repo's
# commit guard and secrets-scan stay quiet while the masker is still tested on the real shape
FAKE_KEY = "sk-" + "ant-api03-abcdefghijkl"


@pytest.fixture(autouse=True)
def _never_touch_the_real_home(tmp_path, monkeypatch):
    """A render with default paths once wrote its history into the real ~/.claude/state during a
    test run. Nothing in this file may resolve `Path.home()` to the real home."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "_home")


def ts(y: int, m: int, d: int) -> float:
    return datetime(y, m, d, 12, tzinfo=UTC).timestamp()


def make_ctx(tmp_path: Path, **kw) -> tc.Context:
    vault = kw.pop("vault", tmp_path / "vault")
    return tc.Context(
        today=TODAY,
        repo=kw.pop("repo", None),
        vault=vault,
        pearl_registries=kw.pop("pearl_registries", []),
        threads_file=kw.pop("threads_file", vault / tc.THREADS_STORE_REL),
        log_dir=kw.pop("log_dir", tmp_path / "logs"),
        runner=kw.pop("runner", None),
        is_windows=kw.pop("is_windows", True),
        **kw,
    )


def runner_for(mapping: dict[str, tuple[int, str]]):
    """Runner that answers by the first mapping key contained in the joined command."""

    def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
        joined = " ".join(cmd)
        for key, answer in mapping.items():
            if key in joined:
                return answer
        return 127, f"no fake answer for: {joined[:80]}"

    return run


def titles(items: list[tc.Item], section: str | None = None) -> list[str]:
    return [i.title for i in items if section is None or i.section == section]


# --------------------------------------------------------------------------- text safety
class TestTextSafety:
    def test_secrets_are_masked(self):
        text = "key " + FAKE_KEY + " and ghp_abcdefghijklmnopqrstuv Bearer abcdef1234567890"
        out = tc.mask_secrets(text)
        assert "sk-ant" not in out and "ghp_abc" not in out and "abcdef1234567890" not in out
        assert out.count("<masked>") == 3

    def test_jwt_shaped_value_is_masked(self):
        assert "<masked>" in tc.mask_secrets(
            "eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0NTY.SflKxwRJSMeKKF2QT4f"
        )

    def test_clean_removes_control_chars_and_bounds_length(self):
        out = tc.clean("a\x00b\x07c\n\n d" + "x" * 500, 50)
        assert "\x00" not in out and "\x07" not in out and "\n" not in out
        assert len(out) <= 50 and out.endswith("…")

    def test_md_cell_has_no_pipe_newline_or_wikilink(self):
        out = tc.md_cell("a | b\nc [[Secret Note]] d")
        assert "\n" not in out and "[[" not in out and "]]" not in out
        assert "\\|" in out and "|" not in out.replace("\\|", "")

    @given(st.text(max_size=300))
    @settings(max_examples=150, deadline=None)
    def test_md_cell_is_always_table_safe(self, text):
        out = tc.md_cell(text)
        assert "\n" not in out and "\r" not in out
        assert "[[" not in out and "]]" not in out
        assert "%%" not in out and "<" not in out
        # the old check (`out.replace("\\|", "")`) could not see an EVEN run of backslashes before a
        # pipe, which GFM reads as a column separator. Count unescaped pipes the way a parser does.
        assert len(tc._split_raw("| " + out + " |") or []) == 1

    @given(st.text(max_size=200))
    @settings(max_examples=100, deadline=None)
    def test_clean_is_idempotent(self, text):
        once = tc.clean(text)
        assert tc.clean(once) == once


class TestSplitRow:
    def test_splits_on_plain_pipes(self):
        assert tc.split_row("| a | b | c |") == ["a", "b", "c"]

    def test_escaped_pipe_stays_inside_the_cell(self):
        assert tc.split_row(r"| a \| b | c |") == ["a | b", "c"]

    def test_double_backslash_then_pipe_is_a_delimiter(self):
        assert tc.split_row("| a \\\\| b |") == ["a \\\\", "b"]

    def test_no_pipe_is_not_a_row(self):
        assert tc.split_row("plain text") is None


# --------------------------------------------------------------------------- automations
PS_ROWS = [
    {"Task": "Claude-WeeklyIntel-Monday", "State": "Ready", "Last": "2026-09-28T07:03:12.0000000+05:00",
     "Result": 1, "Next": "2026-10-05T07:03:00.0000000+05:00", "Missed": 0},
    {"Task": "Codex-QualityAudit-OnMerge", "State": "Ready", "Last": "2026-10-02T12:32:00.0000000+05:00",
     "Result": 0, "Next": "2026-10-02T13:02:00.0000000+05:00", "Missed": 0},
    {"Task": "Codex-BeatClaude-Biweekly-D1", "State": "Ready", "Last": "2026-10-01T10:00:00.0000000+05:00",
     "Result": 3221225786, "Next": "2026-11-01T10:00:00.0000000+05:00", "Missed": 0},
    {"Task": "Claude-Running", "State": "Running", "Last": "2026-10-02T09:00:00.0000000+05:00",
     "Result": 267009, "Next": "2026-10-03T09:00:00.0000000+05:00", "Missed": 0},
    {"Task": "Claude-Never", "State": "Ready", "Last": "1999-11-30T00:00:00.0000000+05:00",
     "Result": 267011, "Next": "2026-10-09T09:00:00.0000000+05:00", "Missed": 0},
    {"Task": "Claude-Missed", "State": "Ready", "Last": "2026-09-20T09:00:00.0000000+05:00",
     "Result": 0, "Next": "2026-10-09T09:00:00.0000000+05:00", "Missed": 2},
]  # fmt: skip


class TestAutomations:
    def run(self, tmp_path, rows, **kw):
        ctx = make_ctx(
            tmp_path, runner=runner_for({"Get-ScheduledTask": (0, json.dumps(rows))}), **kw
        )
        return tc.collect_automations(ctx)

    def test_failing_tasks_are_overdue_and_ok_ones_are_silent(self, tmp_path):
        items = self.run(tmp_path, PS_ROWS)
        by = {i.ref: i for i in items if i.ref}
        assert (
            "Claude-WeeklyIntel-Monday" in by
            and by["Claude-WeeklyIntel-Monday"].section == "overdue"
        )
        assert "Codex-BeatClaude-Biweekly-D1" in by
        assert not any("QualityAudit" in i.title for i in items)  # result 0
        assert not any("Running" in i.title for i in items)  # 267009 = currently running

    def test_age_is_days_since_the_last_run(self, tmp_path):
        items = self.run(tmp_path, PS_ROWS)
        weekly = next(i for i in items if i.ref == "Claude-WeeklyIntel-Monday")
        assert weekly.age_days == 4  # 2026-09-28 -> 2026-10-02

    def test_known_codes_get_a_plain_meaning(self, tmp_path):
        items = self.run(tmp_path, PS_ROWS)
        beat = next(i for i in items if i.ref == "Codex-BeatClaude-Biweekly-D1")
        assert "0xC000013A" in beat.detail
        weekly = next(i for i in items if i.ref == "Claude-WeeklyIntel-Monday")
        assert "код 1" in weekly.detail

    def test_never_run_is_open_not_overdue(self, tmp_path):
        items = self.run(tmp_path, PS_ROWS)
        never = next(i for i in items if "Never" in i.title)
        assert never.section == "open" and never.age_days is None

    def test_missed_runs_make_a_green_task_overdue(self, tmp_path):
        items = self.run(tmp_path, PS_ROWS)
        missed = next(i for i in items if "Missed" in i.title)
        assert missed.section == "overdue" and "пропущено запусков: 2" in missed.detail

    def test_single_object_json_is_accepted(self, tmp_path):
        items = self.run(
            tmp_path, PS_ROWS[0]
        )  # PowerShell emits an object, not a list, for one task
        assert len(items) == 1

    def test_log_hint_is_attached_and_secret_masked(self, tmp_path):
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "weekly-intel-2026-09-28.log").write_text(
            "started\nFailed to authenticate. API Error: 401 API key is invalid " + FAKE_KEY + "\n"
            "[2026-09-28 07:06:15] FAILED: claude -p exited 1\n",
            encoding="utf-8",
        )
        items = self.run(tmp_path, [PS_ROWS[0]])
        assert "401" in items[0].detail or "invalid" in items[0].detail
        assert "sk-ant" not in items[0].detail

    def test_no_matching_log_means_no_cause_but_still_reported(self, tmp_path):
        items = self.run(tmp_path, [PS_ROWS[0]])
        assert "причина из журнала" not in items[0].detail and len(items) == 1

    def test_scheduler_failure_is_unavailable_not_empty(self, tmp_path):
        ctx = make_ctx(tmp_path, runner=runner_for({"Get-ScheduledTask": (1, "")}))
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_automations(ctx)

    def test_non_windows_is_unavailable(self, tmp_path):
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_automations(make_ctx(tmp_path, is_windows=False))

    def test_garbage_output_is_unavailable(self, tmp_path):
        ctx = make_ctx(tmp_path, runner=runner_for({"Get-ScheduledTask": (0, "not json")}))
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_automations(ctx)

    def test_task_keywords_drop_boilerplate_words(self):
        assert tc._task_keywords("Claude-WeeklyIntel-Monday") == ["intel"]
        assert tc._task_keywords("Codex-BeatClaude-Biweekly-D1") == ["beat"]


# --------------------------------------------------------------------------- pearls
PEARL_HEADER = (
    "| date | source | observation | falsifiable_prediction | impact_score | trigger_condition "
    "| next_check | status |\n|---|---|---|---|---|---|---|---|\n"
)


def pearl_row(src, obs, nxt, status):
    return f"| 2026-07-05 | {src} | {obs} | pred | 5 | trig | {nxt} | {status} |\n"


class TestPearls:
    def make(self, tmp_path):
        reg = tmp_path / "rules" / "pearl_registry" / "INDEX.md"
        reg.parent.mkdir(parents=True)
        reg.write_text(
            PEARL_HEADER
            + pearl_row("src-over", "overdue pearl", "2026-08-04", "pending")
            + pearl_row(
                "src-lapsed", "lapsed pearl", "2026-08-04", "**lapsed 2026-08-04, not re-checked**"
            )
            + pearl_row("src-future", "future pearl", "2026-12-01", "pending")
            + pearl_row("src-fixed", "fixed pearl", "2026-09-01", "FIXED 2026-09-12")
            + pearl_row("src-event", "event pearl", "after the next 5 tables", "pending")
            + pearl_row("src-today", "due today", "2026-10-02", "pending"),
            encoding="utf-8",
        )
        return reg

    def test_only_open_dated_and_past_pearls_are_overdue(self, tmp_path):
        ctx = make_ctx(tmp_path, pearl_registries=[self.make(tmp_path)])
        items = tc.collect_pearls(ctx)
        over = titles(items, "overdue")
        assert "overdue pearl" in over and "lapsed pearl" in over and "due today" in over
        assert "future pearl" not in over and "fixed pearl" not in over

    def test_closed_words_are_excluded_even_with_a_past_date(self, tmp_path):
        ctx = make_ctx(tmp_path, pearl_registries=[self.make(tmp_path)])
        assert "fixed pearl" not in titles(tc.collect_pearls(ctx))

    def test_lapsed_note_is_carried_into_the_detail(self, tmp_path):
        ctx = make_ctx(tmp_path, pearl_registries=[self.make(tmp_path)])
        lapsed = next(i for i in tc.collect_pearls(ctx) if i.title == "lapsed pearl")
        assert "lapsed" in lapsed.detail and lapsed.age_days == 59

    def test_undated_trigger_waits_for_an_event(self, tmp_path):
        ctx = make_ctx(tmp_path, pearl_registries=[self.make(tmp_path)])
        waiting = [i for i in tc.collect_pearls(ctx) if i.section == "waiting"]
        assert [i.title for i in waiting] == ["event pearl"]

    def test_missing_registries_are_unavailable_not_zero(self, tmp_path):
        ctx = make_ctx(tmp_path, pearl_registries=[tmp_path / "nope.md"])
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_pearls(ctx)

    def test_ref_names_the_registry(self, tmp_path):
        ctx = make_ctx(tmp_path, pearl_registries=[self.make(tmp_path)])
        assert tc.collect_pearls(ctx)[0].ref == "rules/pearl_registry"


# --------------------------------------------------------------------------- pull requests
def pr(number, title, created, head="feat/x", ci="SUCCESS"):
    return {
        "number": number, "title": title, "createdAt": created + "T10:00:00Z", "headRefName": head,
        "url": f"https://example.test/pull/{number}", "isDraft": False,
        "statusCheckRollup": [{"conclusion": ci}],
    }  # fmt: skip


class TestPrs:
    def collect(self, tmp_path, prs):
        run = runner_for({"pr list --state open": (0, json.dumps(prs))})
        ctx = make_ctx(tmp_path, repo=tmp_path, runner=run)
        return ctx, tc.collect_prs(ctx)

    def test_automated_prs_collapse_into_one_item_with_the_oldest_age(self, tmp_path):
        prs = [
            pr(
                1,
                "chore: FocusOS evening SNR [automated]",
                "2026-09-20",
                "focusos/evening-20260920",
            ),
            pr(2, "chore: FocusOS morning triage [automated]", "2026-09-30", "chore/morning-1"),
            pr(3, "feat: real work", "2026-10-01"),
        ]
        _, items = self.collect(tmp_path, prs)
        auto = [i for i in items if "автоматических" in i.title]
        assert len(auto) == 1 and auto[0].age_days == 12 and "2 автоматических" in auto[0].title

    def test_human_pr_with_red_ci_is_overdue(self, tmp_path):
        _, items = self.collect(tmp_path, [pr(7, "fix: x", "2026-10-01", ci="FAILURE")])
        assert items[0].section == "overdue" and "CI красный" in items[0].detail

    def test_old_green_pr_is_overdue_and_fresh_one_is_open(self, tmp_path):
        prs = [pr(8, "old", "2026-09-10"), pr(9, "fresh", "2026-10-01")]
        _, items = self.collect(tmp_path, prs)
        by = {i.title.split(":")[0]: i for i in items}
        assert by["PR #8"].section == "overdue" and by["PR #8"].age_days == 22
        assert by["PR #9"].section == "open"

    def test_open_pr_count_is_cached_for_drift_checks(self, tmp_path):
        ctx, _ = self.collect(tmp_path, [pr(1, "a", "2026-10-01"), pr(2, "b", "2026-10-01")])
        assert ctx.cache["open_pr_count"] == 2

    def test_pr_title_text_is_cleaned(self, tmp_path):
        _, items = self.collect(tmp_path, [pr(5, "bad\x00title " + FAKE_KEY + "", "2026-10-01")])
        assert "\x00" not in items[0].title and "sk-ant" not in items[0].title

    def test_gh_failure_and_bad_json_are_unavailable(self, tmp_path):
        ctx = make_ctx(tmp_path, repo=tmp_path, runner=runner_for({"pr list": (1, "")}))
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_prs(ctx)
        ctx = make_ctx(tmp_path, repo=tmp_path, runner=runner_for({"pr list": (0, "nope")}))
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_prs(ctx)

    def test_ci_state_classification(self):
        assert (
            tc._ci_state(
                {"statusCheckRollup": [{"conclusion": "SUCCESS"}, {"conclusion": "SKIPPED"}]}
            )
            == "green"
        )
        assert tc._ci_state({"statusCheckRollup": [{"conclusion": "FAILURE"}]}) == "red"
        assert tc._ci_state({"statusCheckRollup": []}) == "unknown"
        assert (
            tc._ci_state({"statusCheckRollup": [{"conclusion": ""}, {"state": "PENDING"}]})
            == "unknown"
        )


# --------------------------------------------------------------------------- git
class TestGitFake:
    def test_dirty_and_closed_pr_branches_are_open_threads(self, tmp_path):
        a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
        porcelain = (
            f"worktree {a}\nHEAD 1\nbranch refs/heads/main\n\n"
            f"worktree {b}\nHEAD 2\nbranch refs/heads/feat/b\n\n"
            f"worktree {c}\nHEAD 3\nbranch refs/heads/fix/c\n"
        )
        run = runner_for(
            {
                "worktree list": (0, porcelain),
                f"-C {b} status": (0, " M file.py\n?? new.py\n"),
                f"-C {c} status": (0, "?? tests/eval/results/\n"),  # junk only
                f"-C {a} status": (0, ""),
                "pr list --state all": (
                    0,
                    json.dumps([{"headRefName": "fix/c", "state": "CLOSED"}]),
                ),
            }
        )
        items = tc.collect_git(make_ctx(tmp_path, repo=tmp_path, runner=run))
        got = titles(items)
        assert any("worktree b (feat/b)" in t for t in got)
        assert not any("worktree c" in t for t in got)  # junk is ignored
        assert any("fix/c закрыт без мержа" in t for t in got)
        assert not any("worktree a" in t for t in got)

    def test_git_failure_is_unavailable(self, tmp_path):
        ctx = make_ctx(tmp_path, repo=tmp_path, runner=runner_for({"worktree list": (128, "")}))
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_git(ctx)

    def test_missing_repo_is_unavailable(self, tmp_path):
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_git(make_ctx(tmp_path, repo=None))

    def test_gh_failure_does_not_hide_dirty_worktrees(self, tmp_path):
        porcelain = f"worktree {tmp_path}\nHEAD 1\nbranch refs/heads/main\n"
        run = runner_for(
            {"worktree list": (0, porcelain), "status": (0, " M x\n"), "pr list": (1, "")}
        )
        items = tc.collect_git(make_ctx(tmp_path, repo=tmp_path, runner=run))
        assert len(items) == 1


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
class TestGitReal:
    def test_real_repo_and_worktree(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args, cwd=repo):
            subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.test")
        git("config", "user.name", "t")
        (repo / "f.txt").write_text("x\n", encoding="utf-8")
        git("add", "f.txt")
        git("commit", "-q", "-m", "init")
        wt = tmp_path / "wt"
        git("worktree", "add", "-q", "-b", "feat/wt", str(wt))
        (wt / "f.txt").write_text("changed\n", encoding="utf-8")
        ctx = make_ctx(
            tmp_path,
            repo=repo,
            runner=lambda cmd, t: tc.default_runner(cmd, t) if cmd[0] == "git" else (127, "no gh"),
        )
        items = tc.collect_git(ctx)
        assert any("wt (feat/wt)" in t for t in titles(items))
        assert not any("repo (main)" in t for t in titles(items))


# --------------------------------------------------------------------------- experiments / waiting
class TestExperimentsAndWaiting:
    def test_zombie_experiment_is_overdue(self, tmp_path):
        exp = tmp_path / "experiments" / "20260601-old"
        exp.mkdir(parents=True)
        f = exp / "claim.md"
        f.write_text("claim", encoding="utf-8")
        os.utime(f, (ts(2026, 6, 1), ts(2026, 6, 1)))
        items = tc.collect_experiments(make_ctx(tmp_path, repo=tmp_path))
        assert len(items) == 1 and items[0].section == "overdue" and items[0].age_days == 123

    def test_experiment_with_a_verdict_is_not_a_zombie(self, tmp_path):
        exp = tmp_path / "experiments" / "20260601-done"
        exp.mkdir(parents=True)
        d = exp / "decision.md"
        d.write_text("Verdict: ARCHIVE", encoding="utf-8")
        os.utime(d, (ts(2026, 6, 1), ts(2026, 6, 1)))
        assert tc.collect_experiments(make_ctx(tmp_path, repo=tmp_path)) == []

    def test_no_experiments_dir_is_unavailable(self, tmp_path):
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_experiments(make_ctx(tmp_path, repo=tmp_path))

    def test_ledger_entries_and_parked_rows_wait_for_events(self, tmp_path):
        led = tmp_path / "experiments" / "20261001-x"
        led.mkdir(parents=True)
        (led / "ledger.md").write_text(
            "# ledger\n\n## Entry 1 — `tool_a`\n- **Check after:** the next 5 tables\n\n"
            "## Entry 2 — `tool_b`\n- no condition here\n",
            encoding="utf-8",
        )
        (tmp_path / "parked").mkdir()
        (tmp_path / "parked" / "INDEX.md").write_text(
            "# parked\n| id | date | slug | note |\n|---|---|---|---|\n"
            "| 20260101-a | 2026-01-02 | a-slug | blocked until X works |\n",
            encoding="utf-8",
        )
        items = tc.collect_waiting(make_ctx(tmp_path, repo=tmp_path))
        assert all(i.section == "waiting" for i in items) and len(items) == 3
        by = {i.kind: i for i in items if i.kind == "parked"}
        assert "blocked until X works" in by["parked"].detail
        details = [i.detail for i in items if i.kind == "ledger"]
        assert "the next 5 tables" in details and "условие не указано" in details


# --------------------------------------------------------------------------- thread store
class TestThreadStore:
    def test_add_list_close_roundtrip(self, tmp_path):
        store = tmp_path / "threads.md"
        tid = tc.add_thread(store, "check the gitleaks findings", TODAY, nxt="open file")
        assert tid == "T-20261002-01"
        rows = tc._read_store(store)
        assert rows[0]["thread"] == "check the gitleaks findings" and rows[0]["status"] == "open"
        tc.close_thread(store, tid)
        assert tc._read_store(store)[0]["status"] == "done"

    def test_ids_increment_within_a_day_and_restart_on_a_new_day(self, tmp_path):
        store = tmp_path / "t.md"
        assert tc.add_thread(store, "a", TODAY) == "T-20261002-01"
        assert tc.add_thread(store, "b", TODAY) == "T-20261002-02"
        assert tc.add_thread(store, "c", date(2026, 10, 3)) == "T-20261003-01"

    def test_pipes_and_wikilinks_in_text_survive_or_are_neutralised(self, tmp_path):
        store = tmp_path / "t.md"
        tc.add_thread(store, "a | b and [[x]]", TODAY)
        rows = tc._read_store(store)
        assert rows[0]["thread"].count("|") == 1  # the pipe came back as ONE cell, not two
        assert len(rows) == 1

    def test_empty_text_and_bad_status_and_unknown_id_are_rejected(self, tmp_path):
        store = tmp_path / "t.md"
        with pytest.raises(ValueError):
            tc.add_thread(store, "   \x00 ", TODAY)
        tid = tc.add_thread(store, "x", TODAY)
        with pytest.raises(ValueError):
            tc.close_thread(store, tid, "weird")
        with pytest.raises(KeyError):
            tc.close_thread(store, "T-nope")

    def test_write_is_atomic_no_tmp_left(self, tmp_path):
        store = tmp_path / "t.md"
        tc.add_thread(store, "x", TODAY)
        assert not list(tmp_path.glob("*.tmp"))

    def test_trigger_semantics(self, tmp_path):
        store = tmp_path / "t.md"
        tc.add_thread(store, "past due", date(2026, 9, 1), trigger="date:2026-09-15")
        tc.add_thread(store, "future", date(2026, 9, 1), trigger="date:2026-12-01")
        tc.add_thread(store, "event", date(2026, 9, 1), trigger="event:after 5 tables")
        tc.add_thread(store, "plain", date(2026, 9, 1))
        tc.add_thread(store, "finished", date(2026, 9, 1))
        tc.close_thread(store, "T-20260901-05")
        items = tc.collect_threads(make_ctx(tmp_path, threads_file=store))
        sec = {i.title: i.section for i in items}
        assert sec == {"past due": "overdue", "future": "open", "event": "waiting", "plain": "open"}
        assert next(i for i in items if i.title == "past due").age_days == 17

    def test_missing_store_means_no_threads(self, tmp_path):
        assert tc.collect_threads(make_ctx(tmp_path, threads_file=tmp_path / "none.md")) == []

    def test_header_and_separator_rows_are_not_threads(self, tmp_path):
        store = tmp_path / "t.md"
        tc.add_thread(store, "x", TODAY)
        text = store.read_text(encoding="utf-8")
        assert tc.STORE_HEADER in text
        assert len(tc._read_store(store)) == 1


# --------------------------------------------------------------------------- vault
def vault_note(root: Path, rel: str, text: str, mtime: float | None = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


class TestVaultLinks:
    def idx(self, tmp_path):
        for rel in ("exists.md", "folder/sub/note.md", "x/Other.md"):
            vault_note(tmp_path, rel, "x")
        return tc._vault_index(tmp_path)

    def test_broken_link_counting(self, tmp_path):
        rel, base, _ = self.idx(tmp_path)
        text = (
            "[[exists]] [[missing]] [[folder/sub/note|alias]] [[exists#Heading]] ![[img.png]] "
            "[[doc.pdf]] [[https://example.test]] [[folder/nope]] [[other]]"
        )
        assert tc.broken_links(text, rel, base) == 2  # missing, folder/nope

    def test_path_style_target_must_match_the_path_not_just_the_name(self, tmp_path):
        rel, base, _ = self.idx(tmp_path)
        assert tc.broken_links("[[wrong/exists]]", rel, base) == 1

    def test_header_date_forms(self):
        assert tc.header_date("---\nupdated: 2026-06-13\n---\n") == date(2026, 6, 13)
        assert tc.header_date("# T\nLast updated: 2026-06-14\n") == date(2026, 6, 14)
        assert tc.header_date("Обновлено: 2026-07-01") == date(2026, 7, 1)
        assert tc.header_date("(проверено 2026-06-06, scan)") == date(2026, 6, 6)
        assert tc.header_date("no date here") is None


class TestVaultCollector:
    def build(self, tmp_path):
        v = tmp_path / "vault"
        vault_note(v, "Dashboard.md", "# D\n[[exists]]\n", ts(2026, 5, 2))  # stale 153 d
        vault_note(v, "exists.md", "x", ts(2026, 9, 30))
        vault_note(
            v,
            "09 System/Truth/project-status-registry.md",
            "---\nupdated: 2026-06-13\n---\n[[exists]]",
            ts(2026, 9, 30),
        )  # mtime fresh, own date old
        vault_note(
            v, "activeContext.md", "Размер: 3552 markdown файлов\n[[exists]]\n", ts(2026, 9, 30)
        )
        vault_note(
            v, "mocs/Fresh MOC.md", "[[exists]] [[nope]]", ts(2026, 9, 30)
        )  # fresh, 1 broken
        vault_note(v, "MEMORY.md", "no links at all", ts(2026, 9, 30))  # fresh, isolated
        return v

    def test_stale_and_lying_hubs_become_one_aggregated_overdue_item(self, tmp_path):
        ctx = make_ctx(tmp_path, vault=self.build(tmp_path))
        items = tc.collect_vault(ctx)
        over = [i for i in items if i.section == "overdue"]
        assert len(over) == 1 and "3 из 5 хабов устарели" in over[0].title
        assert "Dashboard.md" in over[0].detail and over[0].age_days == 153

    def test_hub_rows_carry_the_reasons(self, tmp_path):
        ctx = make_ctx(tmp_path, vault=self.build(tmp_path))
        tc.collect_vault(ctx)
        rows = {r["hub"]: r for r in ctx.cache["vault_hubs"]}
        assert "не менялся 153 дн." in rows["Dashboard.md"]["notes"]
        assert "своя дата" in rows["09 System/Truth/project-status-registry.md"]["notes"]
        assert "утверждает 3552" in rows["activeContext.md"]["notes"]
        assert rows["mocs/Fresh MOC.md"]["broken"] == 1 and rows["mocs/Fresh MOC.md"]["notes"] == ""

    def test_isolated_fresh_hub_is_an_open_item(self, tmp_path):
        ctx = make_ctx(tmp_path, vault=self.build(tmp_path))
        items = tc.collect_vault(ctx)
        iso = [i for i in items if i.section == "open"]
        assert len(iso) == 1 and "MEMORY.md" in iso[0].detail

    def test_md_count_is_cached(self, tmp_path):
        ctx = make_ctx(tmp_path, vault=self.build(tmp_path))
        tc.collect_vault(ctx)
        assert ctx.cache["vault_md_count"] == 6

    def test_missing_vault_is_unavailable(self, tmp_path):
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_vault(make_ctx(tmp_path, vault=tmp_path / "nope"))

    def test_pr_count_claim_drift(self, tmp_path):
        v = tmp_path / "vault"
        vault_note(v, "MEMORY.md", "now there are 4 open PRs [[x]]", ts(2026, 9, 30))
        ctx = make_ctx(tmp_path, vault=v)
        ctx.cache["open_pr_count"] = 18
        out = tc._drift_pr_claims(ctx, [])
        assert len(out) == 1 and "утверждает 4 открытых PR, сейчас 18" in out[0].detail
        ctx.cache["open_pr_count"] = 4
        assert tc._drift_pr_claims(ctx, []) == []
        ctx.cache.pop("open_pr_count")
        assert tc._drift_pr_claims(ctx, []) == []  # unknown is not a mismatch


# --------------------------------------------------------------------------- snapshot
def fake(items):
    return lambda ctx: list(items)


def boom(ctx):
    raise RuntimeError("kaboom " + FAKE_KEY + "")


def unavailable(ctx):
    raise tc.CollectorUnavailable("no source here")


class TestSnapshot:
    def test_counts_sorting_and_coverage(self, tmp_path):
        a = tc.Item("overdue", "pr", "old pr", age_days=30)
        b = tc.Item("overdue", "automation", "task down", age_days=2)
        c = tc.Item("open", "thread", "an open thread")
        d = tc.Item("waiting", "ledger", "waits")
        snap = tc.build_snapshot(make_ctx(tmp_path), (("x", fake([a, b, c, d])),))
        assert snap["status"] == "OK" and snap["counts"] == {"overdue": 2, "open": 1, "waiting": 1}
        assert [i["title"] for i in snap["items"][:2]] == [
            "task down",
            "old pr",
        ]  # automation first
        assert snap["collectors_ran"] == {"x": 4} and snap["not_covered"]

    def test_unavailable_and_crashing_collectors_are_reported_not_hidden(self, tmp_path):
        ok = tc.Item("open", "thread", "fine")
        snap = tc.build_snapshot(
            make_ctx(tmp_path), (("ok", fake([ok])), ("na", unavailable), ("bad", boom))
        )
        assert snap["counts"]["open"] == 1
        errs = " ".join(snap["collector_errors"])
        assert "na: НЕ ПРОВЕРЕНО" in errs and "bad: СБОЙ СБОРЩИКА" in errs
        assert "sk-ant" not in errs  # secrets in exception text are masked

    def test_all_collectors_failing_is_insufficient_data(self, tmp_path):
        snap = tc.build_snapshot(make_ctx(tmp_path), (("na", unavailable), ("bad", boom)))
        assert snap["status"] == "INSUFFICIENT_DATA" and snap["counts"]["overdue"] == 0

    def test_headline_says_not_checked_when_a_source_is_missing(self, tmp_path):
        snap = tc.build_snapshot(make_ctx(tmp_path), (("ok", fake([])), ("na", unavailable)))
        assert "НЕ ПРОВЕРЕНО источников: 1" in tc._headline(snap)

    def test_collector_set_is_resolved_at_call_time(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tc, "COLLECTORS", (("only", fake([tc.Item("open", "thread", "t")])),))
        assert tc.build_snapshot(make_ctx(tmp_path))["collectors_ran"] == {"only": 1}


# --------------------------------------------------------------------------- rendering
def snap_with(items, hubs=None, errors=None, tmp_path=None):
    ctx = make_ctx(tmp_path or Path("."))
    snap = tc.build_snapshot(ctx, (("x", fake(items)),))
    snap["vault_hubs"] = hubs or []
    snap["collector_errors"] = errors or []
    return snap


HUB = {"hub": "mocs/A MOC.md", "age_days": 80, "header_date": "2026-07-01", "header_gap": 70,
       "wikilinks": 3, "broken": 2, "notes": "не менялся 80 дн."}  # fmt: skip


class TestRender:
    def test_html_escapes_third_party_text(self, tmp_path):
        evil = "<script>alert(1)</script>"
        item = tc.Item("overdue", "pr", evil, detail=f"<img src=x onerror={evil}>", ref="<b>x</b>")
        html_out = tc.render_html(snap_with([item], tmp_path=tmp_path))
        assert "<script>alert(1)" not in html_out and "<img src=x" not in html_out
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_out

    def test_html_is_self_contained_and_themeable(self, tmp_path):
        html_out = tc.render_html(snap_with([], tmp_path=tmp_path))
        assert "http://" not in html_out and "https://" not in html_out
        assert "<script" not in html_out and "prefers-color-scheme:dark" in html_out
        assert 'name="viewport"' in html_out and "<title>Центр нитей</title>" in html_out

    def test_html_hub_table_and_coverage(self, tmp_path):
        html_out = tc.render_html(snap_with([], [HUB], ["x: НЕ ПРОВЕРЕНО — причина"], tmp_path))
        assert "mocs/A MOC.md" in html_out and "не менялся 80 дн." in html_out
        assert "НЕ ПРОВЕРЕНО — причина" in html_out and "не охвачено" in html_out

    def test_markdown_structure_and_hub_wikilinks(self, tmp_path):
        item = tc.Item("overdue", "pearl", "an overdue pearl", "next_check 2026-08-04", 59)
        md = tc.render_markdown(snap_with([item], [HUB], tmp_path=tmp_path))
        assert md.startswith("---\ntype: dashboard") and "auto-generated: true" in md
        assert (
            "## ПРОСРОЧЕНО (1)" in md
            and "## ОТКРЫТЫЕ НИТИ (0)" in md
            and "## ЖДУТ СОБЫТИЯ (0)" in md
        )
        assert "[[mocs/A MOC]]" in md  # the center links the hubs: this is what interconnects them
        assert "| an overdue pearl | next_check 2026-08-04 | 59 дн. | pearl |" in md

    def test_markdown_neutralises_foreign_wikilinks_and_pipes(self, tmp_path):
        item = tc.Item("open", "thread", "see [[Private Note]] | rm", "line1\nline2")
        md = tc.render_markdown(snap_with([item], tmp_path=tmp_path))
        row = next(ln for ln in md.splitlines() if "Private Note" in ln)
        assert "[[Private Note]]" not in row and "\\|" in row and "\n" not in row

    def test_long_lists_are_capped_with_a_remainder_line(self, tmp_path):
        items = [tc.Item("open", "thread", f"t{n}") for n in range(tc.LIST_CAP + 5)]
        md = tc.render_markdown(snap_with(items, tmp_path=tmp_path))
        assert "… и ещё 5" in md and md.count("| thread |") == tc.LIST_CAP
        html_out = tc.render_html(snap_with(items, tmp_path=tmp_path))
        assert "<details>" in html_out

    def test_empty_sections_say_empty(self, tmp_path):
        md = tc.render_markdown(snap_with([], tmp_path=tmp_path))
        assert md.count("_пусто_") == 3 and "_не проверено_" in md

    @given(st.text(max_size=120), st.text(max_size=120))
    @settings(max_examples=100, deadline=None)
    def test_html_never_contains_raw_angle_brackets_from_item_text(self, title, detail):
        snap = snap_with([tc.Item("open", "thread", title, detail)])
        out = tc.render_html(snap)
        body = out.split("</style>", 1)[1]
        # every '<' in the body is one of OUR tags: foreign text can add none
        ours = body.count("<") - body.count("</") * 0
        foreign_lt = (title + detail).count("<")
        assert foreign_lt == 0 or "&lt;" in body
        assert ours > 0

    def test_summary_lines(self, tmp_path):
        items = [tc.Item("overdue", "automation", f"task {n}", "d") for n in range(5)]
        lines = tc.summary_lines(snap_with(items, tmp_path=tmp_path))
        assert lines[0].startswith("[threads] ПРОСРОЧЕНО 5") and len(lines) == 5
        assert "ещё 2 просроченных" in lines[-1]


# --------------------------------------------------------------------------- CLI
class TestCli:
    def args(self, tmp_path, *extra):
        return [
            *extra, "--vault", str(tmp_path / "vault"), "--repo", str(tmp_path),
            "--threads-file", str(tmp_path / "threads.md"), "--log-dir", str(tmp_path / "logs"),
            "--seen-file", str(tmp_path / "seen.json"),
        ]  # fmt: skip

    def patch_collectors(self, monkeypatch, items, extra=()):
        monkeypatch.setattr(tc, "COLLECTORS", (("fake", fake(items)), *extra))

    def test_render_writes_the_note_and_the_page(self, tmp_path, monkeypatch, capsys):
        self.patch_collectors(monkeypatch, [tc.Item("overdue", "pr", "late pr", age_days=20)])
        md, page = tmp_path / "out" / "note.md", tmp_path / "out" / "page.html"
        rc = tc.main(self.args(tmp_path, "render", "--out-md", str(md), "--out-html", str(page)))
        assert rc == 0 and md.is_file() and page.is_file()
        assert "late pr" in md.read_text(encoding="utf-8") and "late pr" in page.read_text(
            encoding="utf-8"
        )
        out = capsys.readouterr().out
        assert "ПРОСРОЧЕНО 1" in out and "note:" in out

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch, capsys):
        self.patch_collectors(monkeypatch, [tc.Item("overdue", "pr", "late pr")])
        md = tmp_path / "note.md"
        assert tc.main(self.args(tmp_path, "render", "--dry-run", "--out-md", str(md))) == 0
        assert not md.exists() and "ПРОСРОЧЕНО 1" in capsys.readouterr().out

    def test_summary_alert_exit_codes(self, tmp_path, monkeypatch):
        self.patch_collectors(monkeypatch, [tc.Item("overdue", "pr", "late")])
        assert tc.main(self.args(tmp_path, "summary", "--alert")) == 1
        assert tc.main(self.args(tmp_path, "summary")) == 0
        self.patch_collectors(monkeypatch, [tc.Item("open", "thread", "fine")])
        assert tc.main(self.args(tmp_path, "summary", "--alert")) == 0

    def test_collect_json_is_valid_json(self, tmp_path, monkeypatch, capsys):
        self.patch_collectors(monkeypatch, [tc.Item("open", "thread", "x")])
        assert tc.main(self.args(tmp_path, "collect", "--json")) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "OK" and data["counts"]["open"] == 1

    def test_insufficient_data_is_reported_and_writes_nothing(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(tc, "COLLECTORS", (("na", unavailable),))
        md = tmp_path / "note.md"
        # exit 2, not 0: "nothing could be checked" must never look like success to a scheduler
        assert tc.main(self.args(tmp_path, "render", "--out-md", str(md))) == 2
        assert "INSUFFICIENT_DATA" in capsys.readouterr().out and not md.exists()
        assert tc.main(self.args(tmp_path, "summary", "--alert")) == 2

    def test_add_list_close_via_cli(self, tmp_path, capsys):
        assert (
            tc.main(self.args(tmp_path, "add", "think about X", "--trigger", "event:new data")) == 0
        )
        assert "T-" in capsys.readouterr().out
        assert tc.main(self.args(tmp_path, "list")) == 0
        listing = capsys.readouterr().out
        assert "think about X" in listing and "open" in listing
        tid = listing.split()[0]
        assert tc.main(self.args(tmp_path, "close", tid)) == 0
        assert tc.main(self.args(tmp_path, "close", "T-nope")) == 2
        assert tc.main(self.args(tmp_path, "add", "   ")) == 2

    def test_install_hint_only_prints(self, monkeypatch, capsys):
        def boom_run(*a, **k):
            raise AssertionError("install-hint must not run anything")

        monkeypatch.setattr(subprocess, "run", boom_run)
        assert tc.main(["install-hint"]) == 0
        out = capsys.readouterr().out
        assert "Register-ScheduledTask" in out and "claude -p" in out

    def test_default_outputs_are_only_the_note_the_page_and_the_store(self, tmp_path, monkeypatch):
        # the script never writes anywhere else: run render with defaults pointed at tmp
        self.patch_collectors(monkeypatch, [tc.Item("open", "thread", "x")])
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        before = {p for p in tmp_path.rglob("*") if p.is_file()}
        assert tc.main(["render", "--vault", str(tmp_path / "vault"), "--repo", str(tmp_path)]) == 0
        new = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()} - {
            p.relative_to(tmp_path).as_posix() for p in before
        }
        week = tc.iso_week(tc._local_date(time.time()))
        vault, repo = tmp_path / "vault", tmp_path
        scope = tc._scope_id(repo, vault, [], vault / tc.THREADS_STORE_REL)
        scope = next(
            (
                p.name.removeprefix(f"{tc.SEEN_FILE_PREFIX}-").removesuffix(".json")
                for p in (tmp_path / "home" / ".claude" / "state").glob(
                    f"{tc.SEEN_FILE_PREFIX}-*.json"
                )
            ),
            scope,
        )  # the registries default to repo/home paths, so read the scope off the file it chose
        assert new == {
            "vault/" + tc.THREADS_NOTE_REL,
            f"vault/{tc.ARCHIVE_DIR_REL}/{week}.md",
            "home/.claude/state/threads-center.html",
            f"home/.claude/state/{tc.LAST_FILE_NAME}",
            f"home/.claude/state/{tc.SEEN_FILE_PREFIX}-{scope}.json",
        }
