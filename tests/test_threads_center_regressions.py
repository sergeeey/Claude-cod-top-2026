"""Regression tests for the defects an independent adversarial review found in threads_center.py.

Every defect here was REPRODUCED against the code before it was fixed (not accepted from the
reviewer's report), and each test pins the behaviour that fixes it. Numbers in the class names are
the reviewer's finding numbers.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import threads_center as tc  # noqa: E402

TODAY = date(2026, 10, 2)


@pytest.fixture(autouse=True)
def _never_touch_the_real_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "_home")


HDR = (
    "| date | source | observation | falsifiable_prediction | impact_score | trigger_condition "
    "| next_check | status |\n|---|---|---|---|---|---|---|---|\n"
)


def make_ctx(tmp_path: Path, **kw) -> tc.Context:
    vault = kw.pop("vault", tmp_path / "vault")
    return tc.Context(
        today=TODAY,
        repo=kw.pop("repo", None),
        vault=vault,
        pearl_registries=kw.pop("pearl_registries", []),
        threads_file=kw.pop("threads_file", vault / "t.md"),
        log_dir=kw.pop("log_dir", tmp_path / "logs"),
        runner=kw.pop("runner", None),
        is_windows=True,
        **kw,
    )


def reg_with(tmp_path: Path, *rows: str) -> Path:
    reg = tmp_path / "rules" / "pearl_registry" / "INDEX.md"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(HDR + "".join(rows), encoding="utf-8")
    return reg


def prow(obs: str, nxt: str, status: str) -> str:
    return f"| 2026-07-05 | src | {obs} | pred | 3 | trig | {nxt} | {status} |\n"


# --------------------------------------------------------------------------- 1: closed status
class TestClosedByLeadingWordOnly:
    def overdue(self, tmp_path, status):
        reg = reg_with(tmp_path, prow("the obs", "2026-08-04", status))
        items = tc.collect_pearls(make_ctx(tmp_path, pearl_registries=[reg]))
        return [i for i in items if i.section == "overdue"]

    @pytest.mark.parametrize(
        "status",
        [
            "pending [REJECTED-AS-DESIGNED — if revived]",
            "pending [PEARL_ONLY -- not implemented until the owner says so]",
            "pending, not fixed yet",
            "pending; unresolved",
            "**lapsed 2026-08-04, not re-checked**",
            "REVIEWED 2026-09-16 — trigger unmet, status unchanged. KEEP PEARL_ONLY",
        ],
    )
    def test_a_closed_word_inside_the_text_does_not_close_the_row(self, tmp_path, status):
        assert len(self.overdue(tmp_path, status)) == 1

    @pytest.mark.parametrize(
        "status",
        [
            "FIXED 2026-09-12",
            "**FIXED 2026-09-19** [... do not mark this row closed until that verdict lands]",
            "KILLED",
            "dropped",
            "superseded",
            "merged",
            "закрыто",
        ],
    )
    def test_a_leading_closed_word_closes_the_row(self, tmp_path, status):
        assert self.overdue(tmp_path, status) == []

    def test_the_bracket_tag_is_shown_so_the_owner_can_decide(self, tmp_path):
        got = self.overdue(tmp_path, "pending [REJECTED-AS-DESIGNED — if revived]")
        assert "REJECTED-AS-DESIGNED" in got[0].detail


# --------------------------------------------------------------------------- pearl row shape
class TestPearlRowShape:
    def test_a_row_with_the_wrong_cell_count_is_reported_not_guessed(self, tmp_path):
        bad = "| 2026-09-18 | src | obs with a stray | pipe | pred | 3 | trig | event | status |\n"
        reg = reg_with(tmp_path, bad)
        items = tc.collect_pearls(make_ctx(tmp_path, pearl_registries=[reg]))
        assert len(items) == 1
        assert items[0].section == "open" and "ненадёжно" in items[0].title
        assert "9 ячеек вместо 8" in items[0].detail

    def test_only_a_date_at_the_start_of_next_check_is_a_deadline(self, tmp_path):
        reg = reg_with(
            tmp_path,
            prow("a", "2026-08-04 -> 2026-12-01", "pending"),
            prow("b", "after 2026-08-04 when X happens", "pending"),
            prow("c", "2026-13-01", "pending"),
            prow("d", "**2026-12-31**", "pending"),
        )
        got = {
            i.title: i.section
            for i in tc.collect_pearls(make_ctx(tmp_path, pearl_registries=[reg]))
        }
        assert got == {"a": "overdue", "b": "waiting", "c": "open"}  # d is in the future: silent

    def test_a_missing_second_registry_is_a_partial_warning_not_silence(self, tmp_path):
        reg = reg_with(tmp_path, prow("a", "2026-08-04", "pending"))
        ctx = make_ctx(tmp_path, pearl_registries=[reg, tmp_path / "gone.md"])
        tc.collect_pearls(ctx)
        assert any("gone.md" in w for w in ctx.cache["warnings"])

    def test_real_registry_shape_columns_are_read_by_name(self, tmp_path):
        reg = reg_with(tmp_path, prow("named", "2026-08-04", "pending"))
        rows, bad = tc._parse_pearls(reg)
        assert (
            bad == []
            and rows[0]["observation"] == "named"
            and rows[0]["next_check"] == "2026-08-04"
        )


# --------------------------------------------------------------------------- 3, 4, 7, 8: store
class TestStoreSafety:
    def test_hand_edited_rows_and_prose_survive_add_and_close(self, tmp_path):
        store = tmp_path / "s.md"
        tc.add_thread(store, "first", TODAY)
        text = store.read_text(encoding="utf-8")
        manual = "| T-x | 2026-10-01 | my thread | chat | next |\n\n## заметки\nvery important paragraph\n"
        store.write_text(text + manual, encoding="utf-8")
        tid = tc.add_thread(store, "second", TODAY)
        tc.close_thread(store, "T-20261002-01")
        after = store.read_text(encoding="utf-8")
        assert "my thread" in after and "very important paragraph" in after
        assert tid == "T-20261002-02"
        assert after.count("| open |") == 1 and after.count("| done |") == 1

    def test_close_changes_only_the_status_cell_of_its_own_row(self, tmp_path):
        store = tmp_path / "s.md"
        tc.add_thread(store, r"a \ b | c", TODAY, nxt="step")
        before = store.read_text(encoding="utf-8").splitlines()
        tc.close_thread(store, "T-20261002-01", "dropped")
        after = store.read_text(encoding="utf-8").splitlines()
        diff = [(x, y) for x, y in zip(before, after, strict=True) if x != y]
        assert len(diff) == 1 and diff[0][1] == diff[0][0].removesuffix("open |") + "dropped |"

    @pytest.mark.parametrize(
        "text",
        [r"grep 'a\|b' logs", r"C:\Users\x\y", "a\\\\b", "ends with backslash\\", "a | b | c"],
    )
    def test_text_round_trips_exactly_including_backslashes_and_pipes(self, tmp_path, text):
        store = tmp_path / "s.md"
        tc.add_thread(store, text, TODAY)
        rows = tc._read_store(store)
        assert len(rows) == 1 and rows[0]["thread"] == tc.clean(text, 400)
        assert rows[0]["status"] == "open"

    def test_a_row_with_the_wrong_cell_count_is_flagged_by_the_collector(self, tmp_path):
        store = tmp_path / "s.md"
        tc.add_thread(store, "ok", TODAY)
        with store.open("a", encoding="utf-8") as fh:
            fh.write("| T-20261001-01 | 2026-10-01 | a | b | chat | | | open |\n")  # 8 cells
        items = tc.collect_threads(make_ctx(tmp_path, threads_file=store))
        flagged = [i for i in items if "не разобрана" in i.title]
        assert len(flagged) == 1 and "8 ячеек вместо 7" in flagged[0].detail

    def test_a_duplicate_id_is_refused_not_closed_blindly(self, tmp_path):
        store = tmp_path / "s.md"
        tc.add_thread(store, "one", TODAY)
        line = next(ln for ln in store.read_text(encoding="utf-8").splitlines() if "T-2026" in ln)
        with store.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        with pytest.raises(ValueError, match="встречается 2"):
            tc.close_thread(store, "T-20261002-01")

    def test_ids_never_repeat_after_a_manual_delete(self, tmp_path):
        store = tmp_path / "s.md"
        ids = [tc.add_thread(store, f"t{n}", TODAY) for n in range(3)]
        lines = [ln for ln in store.read_text(encoding="utf-8").splitlines() if ids[1] not in ln]
        store.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert tc.add_thread(store, "again", TODAY) == "T-20261002-04"

    def test_concurrent_adds_get_distinct_ids_and_lose_no_rows(self, tmp_path):
        store = tmp_path / "s.md"
        got: list[str] = []
        lock = threading.Lock()

        def worker(n: int) -> None:
            tid = tc.add_thread(store, f"thread {n}", TODAY)
            with lock:
                got.append(tid)

        ts = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert len(set(got)) == 8 and len(tc._read_store(store)) == 8
        assert not list(tmp_path.glob("*.lock")) and not list(tmp_path.glob("*.tmp"))

    def test_a_held_lock_blocks_then_errors_and_a_stale_one_is_taken_over(
        self, tmp_path, monkeypatch
    ):
        store = tmp_path / "s.md"
        lock = tmp_path / "s.md.lock"
        lock.write_text("x", encoding="utf-8")
        monkeypatch.setattr(tc, "LOCK_WAIT_S", 0.15)
        with pytest.raises(OSError, match="занят"):
            tc.add_thread(store, "x", TODAY)
        old = time.time() - 120
        os.utime(lock, (old, old))
        assert tc.add_thread(store, "x", TODAY).startswith("T-")

    @pytest.mark.parametrize(
        "trigger",
        [
            "date:01.11.2026",
            "date 2026-11-01",
            "date:2026-11-1",
            "date:2026-13-01",
            "soon",
            "event:  ",
        ],
    )
    def test_a_malformed_trigger_is_rejected_at_add_time(self, tmp_path, trigger):
        with pytest.raises(ValueError):
            tc.add_thread(tmp_path / "s.md", "x", TODAY, trigger=trigger)

    def test_a_hand_written_bad_trigger_is_flagged_not_silently_open(self, tmp_path):
        store = tmp_path / "s.md"
        tc.add_thread(store, "x", date(2026, 9, 1))
        text = store.read_text(encoding="utf-8").replace(
            "|  | open |", "| date:01.11.2026 | open |"
        )
        store.write_text(text, encoding="utf-8")
        items = tc.collect_threads(make_ctx(tmp_path, threads_file=store))
        assert items[0].section == "open" and "триггер не разобран" in items[0].detail

    def test_valid_triggers_are_normalised(self, tmp_path):
        store = tmp_path / "s.md"
        tc.add_thread(store, "x", TODAY, trigger="DATE:2026-11-01")
        assert tc._read_store(store)[0]["trigger"] == "date:2026-11-01"


# --------------------------------------------------------------------------- 9: text safety
class TestTextSafetyMore:
    @pytest.mark.parametrize(
        "sample",
        [
            "github_pat_11ABCDEFG0123456789_abcdefghijklmnop",
            "https://user:hunter2pass@host.example/x",
            # fixtures are assembled from halves so no secret-shaped literal sits in the source
            # (the repo's secrets-scan flags them otherwise)
            "AK" + "IAABCDEFGHIJKLMNOP",
            "xox" + "b-1234567890-abcdefghij",
            "AIza" + "A" * 35,
            "ANTHROPIC_API_" + "KEY=aaaa1111bbbb",
            "Bearer: abcdef1234567890",
            "sk-\x00ant-api03-abcdefghijkl",
        ],
    )
    def test_realistic_secret_shapes_are_masked(self, sample):
        out = tc.clean(sample)
        assert "<masked>" in out
        for leak in (
            "hunter2pass",
            "abcdefghijklmnop",
            "aaaa1111bbbb",
            "abcdef1234567890",
            "api03",
        ):
            assert leak not in out

    def test_obsidian_comment_markers_and_raw_html_are_neutralised(self):
        out = tc.md_cell("50%% done <img src=https://x/p.png> and [[Note]]")
        assert "%%" not in out and "<" not in out and "[[" not in out

    def test_bidi_and_zero_width_controls_are_removed(self):
        assert tc.clean("a\u202eb\u200bc\u2066d") == "abcd"

    def test_backslash_before_pipe_cannot_reopen_a_column(self):
        for text in (r"a\|b", r"a\\|b", "a\\\\\\|b", "end\\"):
            out = tc.md_cell(text)
            assert len(tc._split_raw("| " + out + " |") or []) == 1, (text, out)


# --------------------------------------------------------------------------- 10: PRs
class TestPrsMore:
    def test_in_progress_ci_is_not_green(self):
        assert (
            tc._ci_state({"statusCheckRollup": [{"conclusion": "", "status": "IN_PROGRESS"}]})
            == "unknown"
        )
        assert (
            tc._ci_state({"statusCheckRollup": [{"conclusion": "", "status": "QUEUED"}]})
            == "unknown"
        )
        done = {"conclusion": "SUCCESS", "status": "COMPLETED"}
        assert tc._ci_state({"statusCheckRollup": [done]}) == "green"
        assert (
            tc._ci_state({"statusCheckRollup": [done, {"conclusion": "", "status": "IN_PROGRESS"}]})
            == "unknown"
        )

    @pytest.mark.parametrize("c", ["STARTUP_FAILURE", "ACTION_REQUIRED", "TIMED_OUT"])
    def test_more_failure_states_are_red(self, c):
        assert tc._ci_state({"statusCheckRollup": [{"conclusion": c}]}) == "red"

    def test_a_human_pr_that_mentions_focusos_is_not_swallowed(self):
        assert not tc._is_automated({"title": "fix: focusos hook bug", "headRefName": "fix/x"})
        assert tc._is_automated({"title": "chore [automated]", "headRefName": "x"})
        assert tc._is_automated({"title": "t", "headRefName": "focusos/evening-1"})

    def test_gh_is_pinned_to_the_inspected_repo_with_dash_r(self, tmp_path):
        seen: list[list[str]] = []

        def run(cmd, timeout=60):
            seen.append(cmd)
            if cmd[0] == "git" and "remote" in cmd:
                return 0, "git@github.com:owner/name.git\n"
            return 0, "[]"

        ctx = make_ctx(tmp_path, repo=tmp_path, runner=run)
        tc.collect_prs(ctx)
        gh = next(c for c in seen if c[0] == "gh")
        assert gh[-2:] == ["-R", "owner/name"]

    def test_without_a_remote_gh_runs_unpinned_and_says_so(self, tmp_path):
        def run(cmd, timeout=60):
            return (128, "") if cmd[0] == "git" else (0, "[]")

        ctx = make_ctx(tmp_path, repo=tmp_path, runner=run)
        tc.collect_prs(ctx)
        assert any("без -R" in w for w in ctx.cache["warnings"])

    def test_a_truncated_pr_list_is_flagged(self, tmp_path):
        prs = [
            {"number": n, "title": "t", "createdAt": "2026-10-01T00:00:00Z", "headRefName": "h",
             "url": "u", "statusCheckRollup": [{"conclusion": "SUCCESS"}]}
            for n in range(100)
        ]  # fmt: skip

        def run(cmd, timeout=60):
            return (128, "") if cmd[0] == "git" else (0, json.dumps(prs))

        ctx = make_ctx(tmp_path, repo=tmp_path, runner=run)
        tc.collect_prs(ctx)
        assert any("усечён" in w for w in ctx.cache["warnings"])


# --------------------------------------------------------------------------- 5: git + partial
class TestGitPartialFailures:
    def porcelain(self, tmp_path):
        return f"worktree {tmp_path / 'wt'}\nHEAD 1\ndetached\n"

    def test_a_dirty_detached_worktree_is_visible(self, tmp_path):
        def run(cmd, timeout=60):
            j = " ".join(cmd)
            if "worktree list" in j:
                return 0, self.porcelain(tmp_path)
            if "status" in j:
                return 0, " M f.py\n"
            return 1, ""

        items = tc.collect_git(make_ctx(tmp_path, repo=tmp_path, runner=run))
        assert any("detached HEAD" in i.title for i in items)

    def test_a_failed_git_status_is_a_warning_not_a_clean_worktree(self, tmp_path):
        def run(cmd, timeout=60):
            j = " ".join(cmd)
            if "worktree list" in j:
                return 0, self.porcelain(tmp_path)
            if "status" in j:
                return 128, ""
            return 1, ""

        ctx = make_ctx(tmp_path, repo=tmp_path, runner=run)
        assert tc.collect_git(ctx) == []
        assert any("чистота worktree неизвестна" in w for w in ctx.cache["warnings"])

    def test_a_failed_gh_is_a_warning(self, tmp_path):
        def run(cmd, timeout=60):
            j = " ".join(cmd)
            if "worktree list" in j:
                return 0, f"worktree {tmp_path}\nHEAD 1\nbranch refs/heads/main\n"
            return (0, "") if "status" in j else (1, "")

        ctx = make_ctx(tmp_path, repo=tmp_path, runner=run)
        tc.collect_git(ctx)
        assert any("проверка закрытых PR пропущена" in w for w in ctx.cache["warnings"])

    def test_warnings_reach_the_snapshot_headline_and_are_not_counted_as_unchecked(self, tmp_path):
        def partial(ctx):
            tc._warn(ctx, "half of the source was unreadable")
            return []

        snap = tc.build_snapshot(make_ctx(tmp_path), (("src", partial),))
        assert snap["collectors_ran"] == {"src": 0}
        assert any("src: ЧАСТИЧНО" in e for e in snap["collector_errors"])
        head = tc._headline(snap)
        assert "ЧАСТИЧНО: 1" in head and "НЕ ПРОВЕРЕНО" not in head
        assert tc._unchecked(snap) == 0

    def test_warnings_do_not_leak_into_the_next_collector(self, tmp_path):
        def noisy(ctx):
            tc._warn(ctx, "only mine")
            return []

        def quiet(ctx):
            return []

        snap = tc.build_snapshot(make_ctx(tmp_path), (("a", noisy), ("b", quiet)))
        assert sum("ЧАСТИЧНО" in e for e in snap["collector_errors"]) == 1


# --------------------------------------------------------------------------- 6: scheduler
class TestSchedulerNullSafety:
    def test_powershell_never_calls_a_method_on_a_null_time(self):
        assert "if ($i.NextRunTime)" in tc._PS_TASKS and "if ($i.LastRunTime)" in tc._PS_TASKS
        assert "$i.NextRunTime.ToString" in tc._PS_TASKS  # only inside the guarded branch
        before_guard = tc._PS_TASKS.split("if ($i.NextRunTime)")[0]
        assert "NextRunTime.ToString" not in before_guard

    def run(self, tmp_path, rows):
        ctx = make_ctx(
            tmp_path, runner=lambda cmd, t=60: (0, json.dumps(rows)), log_dir=tmp_path / "logs"
        )
        return tc.collect_automations(ctx)

    def test_a_disabled_task_with_no_next_run_is_listed_not_dropped(self, tmp_path):
        rows = [{"Task": "Claude-Off", "State": "Disabled", "Last": "2026-08-01T07:00:00+05:00",
                 "Result": 0, "Next": "", "Missed": 0}]  # fmt: skip
        items = self.run(tmp_path, rows)
        assert len(items) == 1 and items[0].section == "open" and "отключена" in items[0].title

    def test_a_never_scheduled_task_with_empty_last_does_not_crash(self, tmp_path):
        rows = [{"Task": "Claude-New", "State": "Ready", "Last": "", "Result": 267011,
                 "Next": "", "Missed": 0}]  # fmt: skip
        assert self.run(tmp_path, rows)[0].section == "open"

    def test_a_disabled_task_that_also_failed_is_still_overdue(self, tmp_path):
        rows = [{"Task": "Claude-Off", "State": "Disabled", "Last": "2026-09-01T07:00:00+05:00",
                 "Result": 1, "Next": "", "Missed": 0}]  # fmt: skip
        assert self.run(tmp_path, rows)[0].section == "overdue"


# --------------------------------------------------------------------------- 2: unknown != zero
class TestUnknownIsNotZero:
    def test_waiting_needs_at_least_one_real_source(self, tmp_path):
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_waiting(make_ctx(tmp_path, repo=tmp_path))
        (tmp_path / "parked").mkdir()
        (tmp_path / "parked" / "INDEX.md").write_text("# empty\n", encoding="utf-8")
        assert tc.collect_waiting(make_ctx(tmp_path, repo=tmp_path)) == []

    def test_threads_with_no_vault_and_no_folder_is_unavailable(self, tmp_path):
        ctx = make_ctx(
            tmp_path, vault=tmp_path / "nope", threads_file=tmp_path / "nope" / "deep" / "t.md"
        )
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_threads(ctx)

    def test_threads_in_an_existing_vault_without_a_store_yet_means_none(self, tmp_path):
        (tmp_path / "vault").mkdir()
        assert tc.collect_threads(make_ctx(tmp_path)) == []

    def test_alert_exit_codes_separate_overdue_unchecked_and_all_clear(self, tmp_path, monkeypatch):
        args = [
            "summary", "--alert", "--vault", str(tmp_path / "v"), "--repo", str(tmp_path),
            "--threads-file", str(tmp_path / "t.md"), "--log-dir", str(tmp_path),
        ]  # fmt: skip

        def run(items, errors=()):
            def collector(ctx):
                return items

            fns = [("ok", collector)] + [
                (f"e{n}", lambda c: (_ for _ in ()).throw(tc.CollectorUnavailable("x")))
                for n, _ in enumerate(errors)
            ]
            monkeypatch.setattr(tc, "COLLECTORS", tuple(fns))
            return tc.main(args)

        assert run([]) == 0  # nothing overdue, everything checked
        assert run([], errors=("x",)) == 2  # nothing overdue BUT a source was not checked
        assert run([tc.Item("overdue", "pr", "late")], errors=("x",)) == 1  # overdue wins
        assert run([tc.Item("overdue", "pr", "late")]) == 1


# --------------------------------------------------------------------------- 11, 12: vault/html
class TestVaultAndHtmlMore:
    def test_escaped_pipe_alias_inside_a_table_is_not_a_broken_link(self, tmp_path):
        v = tmp_path / "v"
        v.mkdir()
        (v / "exists.md").write_text("x", encoding="utf-8")
        rel, base, _ = tc._vault_index(v)
        assert tc.broken_links(r"| [[exists\|E]] | [[exists|E]] |", rel, base) == 0
        assert tc.broken_links(r"| [[nope\|N]] |", rel, base) == 1

    def test_links_inside_code_are_examples_not_links(self, tmp_path):
        v = tmp_path / "v"
        v.mkdir()
        (v / "exists.md").write_text("x", encoding="utf-8")
        rel, base, _ = tc._vault_index(v)
        text = "```\n[[ghost]]\n```\nand `[[also-ghost]]` and [[exists]]"
        assert tc.broken_links(text, rel, base) == 0

    def test_a_hub_that_uses_markdown_links_is_not_called_isolated(self, tmp_path):
        v = tmp_path / "vault"
        v.mkdir()
        (v / "MEMORY.md").write_text(
            "- [Note](note.md) - hook\n- [Web](https://x.test/a.md)\n", encoding="utf-8"
        )
        (v / "note.md").write_text("x", encoding="utf-8")
        ctx = make_ctx(tmp_path)
        tc.collect_vault(ctx)
        row = next(r for r in ctx.cache["vault_hubs"] if r["hub"] == "MEMORY.md")
        assert row["wikilinks"] == 1  # the external https link is not counted

    @pytest.mark.parametrize(
        ("text", "claimed"),
        [
            ("1, 2, 3552 markdown файлов", "3552"),
            ("12 345 .md files", "12 345"),
            ("8,386 markdown файлов", "8,386"),
            ("3552 .md file", "3552"),
        ],
    )
    def test_file_count_claim_is_read_without_gluing_a_list_together(self, text, claimed):
        m = tc._FILECOUNT_CLAIM.search(text)
        assert m is not None and m.group(1) == claimed

    def test_html_says_how_many_items_are_not_shown(self, tmp_path):
        items = [tc.Item("open", "thread", f"t{n}") for n in range(tc.LIST_CAP + 15)]
        snap = tc.build_snapshot(make_ctx(tmp_path), (("x", lambda c: list(items)),))
        html_out = tc.render_html(snap)
        assert "и ещё 15 не показано" in html_out
        assert html_out.count("<li>") + html_out.count("<li ") >= tc.LIST_CAP

    def test_install_hint_pins_the_working_dir_and_catches_up_missed_starts(self, capsys):
        assert tc.main(["install-hint"]) == 0
        out = capsys.readouterr().out
        assert "-WorkingDirectory" in out and "-StartWhenAvailable" in out
        assert "Register-ScheduledTask" in out and "-Settings $s" in out

    def test_today_is_the_local_calendar_date(self):
        ts = time.mktime((2026, 10, 2, 0, 30, 0, 0, 0, -1))  # 00:30 local time
        assert tc._local_date(ts) == date(2026, 10, 2)


# --------------------------------------------------------------------------- found on REAL data
class TestFoundOnRealData:
    """Defects the synthetic fixtures could not show: the repo's own registry spells its header
    differently from the global one, and a parser that does not recognise a header must not report
    '0 rows'."""

    def test_header_spelled_with_spaces_and_capitals_is_recognised(self, tmp_path):
        reg = tmp_path / "pearl_registry" / "INDEX.md"
        reg.parent.mkdir()
        reg.write_text(
            "| Date | Source Experiment | Observation | Falsifiable Prediction | Impact "
            "| Trigger Condition | Next Check | Status |\n|---|---|---|---|---|---|---|---|\n"
            "| 2026-07-28 | exp | project row | p | 5 | t | 2026-08-15 | pending |\n",
            encoding="utf-8",
        )
        items = tc.collect_pearls(make_ctx(tmp_path, pearl_registries=[reg]))
        assert [(i.section, i.title) for i in items] == [("overdue", "project row")]

    def test_a_registry_with_data_but_no_recognised_header_is_not_zero_rows(self, tmp_path):
        reg = tmp_path / "pearl_registry" / "INDEX.md"
        reg.parent.mkdir()
        reg.write_text(
            "| when | what | deadline |\n|---|---|---|\n| 2026-07-28 | x | 2026-08-15 |\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="заголовок"):
            tc._parse_pearls(reg)
        with pytest.raises(tc.CollectorUnavailable):
            tc.collect_pearls(make_ctx(tmp_path, pearl_registries=[reg]))

    def test_one_unreadable_registry_is_a_warning_when_another_is_readable(self, tmp_path):
        good = reg_with(tmp_path, prow("fine", "2026-08-04", "pending"))
        bad = tmp_path / "other" / "pearl_registry" / "INDEX.md"
        bad.parent.mkdir(parents=True)
        bad.write_text("| when | what |\n|---|---|\n| 2026-07-28 | x |\n", encoding="utf-8")
        ctx = make_ctx(tmp_path, pearl_registries=[good, bad])
        items = tc.collect_pearls(ctx)
        assert [i.title for i in items] == ["fine"]
        assert any("заголовок" in w for w in ctx.cache["warnings"])

    def test_an_empty_registry_without_data_rows_is_just_empty(self, tmp_path):
        reg = tmp_path / "pearl_registry" / "INDEX.md"
        reg.parent.mkdir()
        reg.write_text("# no table yet\n", encoding="utf-8")
        assert tc.collect_pearls(make_ctx(tmp_path, pearl_registries=[reg])) == []

    @pytest.mark.parametrize(
        ("status", "listed"),
        [
            ("**confirmed same-day, fixed same-day.** the guard", False),
            ("**partially confirmed 2026-08-31, n=2**: seventh run", True),
            ("pending [SPECULATIVE]", True),
        ],
    )
    def test_confirmed_closes_a_row_but_partially_confirmed_does_not(
        self, tmp_path, status, listed
    ):
        reg = reg_with(tmp_path, prow("obs", "2026-08-04", status))
        items = tc.collect_pearls(make_ctx(tmp_path, pearl_registries=[reg]))
        assert bool(items) is listed

    @pytest.mark.parametrize(
        ("title", "head", "automated"),
        [
            ("chore: FocusOS evening SNR score 2026-07-31", "chore/x", True),
            ("chore: focusos morning triage [automated]", "chore/y", True),
            ("anything", "focusos/evening-1", True),
            ("fix: focusos hook bug", "fix/focusos-hook", False),
            ("feat: FocusOS integration docs", "docs/focusos", False),
        ],
    )
    def test_automated_prs_are_recognised_by_origin_not_by_the_bare_word(
        self, title, head, automated
    ):
        assert tc._is_automated({"title": title, "headRefName": head}) is automated
