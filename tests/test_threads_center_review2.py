"""Regression tests for the SECOND adversarial review of threads_center.py.

The theme of most findings: the history could be made to say 'resolved' without evidence, which
biases the kill criterion toward keeping the tool. Each defect was reproduced before it was fixed.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import threads_center as tc  # noqa: E402

D0 = date(2026, 10, 2)


@pytest.fixture(autouse=True)
def _never_touch_the_real_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "_home")


def make_ctx(tmp_path, today=D0, seen=None, vault=None, scope=None, **kw) -> tc.Context:
    v = vault or (tmp_path / "vault")
    v.mkdir(exist_ok=True)
    return tc.Context(
        today=today,
        repo=kw.pop("repo", None),
        vault=v,
        pearl_registries=kw.pop("pearl_registries", []),
        threads_file=v / "t.md",
        log_dir=tmp_path / "logs",
        seen_file=seen,
        scope=scope,
        is_windows=True,
        **kw,
    )


def unavailable(_c):
    raise tc.CollectorUnavailable("source down")


def week(tmp_path, f, off, collectors, scope=None, vault=None):
    d = D0 + timedelta(days=off)
    c = make_ctx(tmp_path, d, f, vault, scope)
    snap = tc.build_snapshot(c, tuple(collectors))
    note = tc.update_seen(f, snap, d, scope)
    return snap, note


# --------------------------------------------------------------------------- 1: zombie counters
class TestCountersInTitlesDoNotChangeIdentity:
    def test_idle_counter_is_not_part_of_the_key(self):
        a = tc._item_key("experiment", "", "эксперимент без вердикта: 20260601-old (123d idle)")
        b = tc._item_key("experiment", "", "эксперимент без вердикта: 20260601-old (130d idle)")
        assert a == b

    def test_two_different_zombies_stay_different(self):
        a = tc._item_key("experiment", "", "эксперимент без вердикта: A (5d idle)")
        b = tc._item_key("experiment", "", "эксперимент без вердикта: B (5d idle)")
        assert a != b

    def test_a_persistent_zombie_never_counts_as_resolved(self, tmp_path):
        f = tmp_path / "s.json"

        def zombie(n):
            t = f"эксперимент без вердикта: 20260601-old ({n}d idle)"
            return lambda _c: [tc.Item("overdue", "experiment", t, "", n)]

        for k in range(6):
            week(tmp_path, f, 7 * k, [("experiments", zombie(123 + 7 * k))])
        st = tc.seen_stats(f, D0 + timedelta(days=35))
        assert st["judged"] == 1 and st["gone"] == 0
        assert "убрать" in st["verdict"]  # nobody acted on it: the criterion must say so


# --------------------------------------------------------------------------- 2: scope of the history
class TestHistoryBelongsToOneSourceSet:
    def test_scope_id_changes_with_every_inspected_source(self, tmp_path):
        r1, r2 = tmp_path / "r1", tmp_path / "r2"
        v1, v2 = tmp_path / "v1", tmp_path / "v2"
        base = tc._scope_id(r1, v1, [tmp_path / "a.md"], v1 / "t.md")
        assert tc._scope_id(r2, v1, [tmp_path / "a.md"], v1 / "t.md") != base
        assert tc._scope_id(r1, v2, [tmp_path / "a.md"], v1 / "t.md") != base
        assert tc._scope_id(r1, v1, [tmp_path / "b.md"], v1 / "t.md") != base
        assert tc._scope_id(r1, v1, [tmp_path / "a.md"], v2 / "t.md") != base
        assert tc._scope_id(r1, v1, [tmp_path / "a.md"], v1 / "t.md") == base

    def test_registry_order_does_not_matter(self, tmp_path):
        a, b = tmp_path / "a.md", tmp_path / "b.md"
        assert tc._scope_id(None, tmp_path, [a, b], tmp_path / "t") == tc._scope_id(
            None, tmp_path, [b, a], tmp_path / "t"
        )

    def test_a_run_against_another_source_set_is_refused_not_merged(self, tmp_path):
        f = tmp_path / "s.json"
        row = tc.Item("waiting", "ledger", "exp1: Entry 1", "x")
        week(tmp_path, f, 0, [("waiting", lambda c: [row])], scope="AAA")
        before = f.read_text(encoding="utf-8")
        with pytest.raises(ValueError, match="другому набору источников"):
            week(tmp_path, f, 1, [("waiting", lambda c: [])], scope="BBB")
        assert f.read_text(encoding="utf-8") == before  # nothing was marked gone

    def test_annotation_is_off_and_reported_for_a_foreign_history(self, tmp_path):
        f = tmp_path / "s.json"
        week(tmp_path, f, 0, [("automations", lambda c: [])], scope="AAA")
        c = make_ctx(tmp_path, D0 + timedelta(days=3), f, scope="BBB")
        snap = tc.build_snapshot(
            c, (("automations", lambda x: [tc.Item("overdue", "automation", "t", "", 1, ref="t")]),)
        )
        assert snap["seen_tracked"] is False and "listed_days" not in snap["items"][0]
        assert any("другому набору источников" in e for e in snap["collector_errors"])

    def test_a_history_without_a_scope_is_adopted_by_the_first_scoped_run(self, tmp_path):
        f = tmp_path / "s.json"
        week(tmp_path, f, 0, [("automations", lambda c: [])], scope=None)
        week(tmp_path, f, 7, [("automations", lambda c: [])], scope="AAA")
        assert json.loads(f.read_text(encoding="utf-8"))["scope"] == "AAA"

    def test_the_default_history_file_is_named_after_the_scope(self, tmp_path, monkeypatch):
        import argparse

        monkeypatch.setattr(Path, "home", lambda: tmp_path / "h")
        ns = lambda repo: argparse.Namespace(  # noqa: E731
            vault=str(tmp_path / "v"), repo=repo, pearl_registry=None, threads_file=None,
            log_dir=None, task_pattern="x", seen_file=None,
        )  # fmt: skip
        c1, c2 = (
            tc.make_context(ns(str(tmp_path / "r1"))),
            tc.make_context(ns(str(tmp_path / "r2"))),
        )
        assert c1.seen_file != c2.seen_file and c1.scope in c1.seen_file.name


# --------------------------------------------------------------------------- 3: criterion judges overdue rows
class TestCriterionJudgesOnlyOverdueRows:
    def test_routine_closures_cannot_rescue_untouched_overdue_rows(self, tmp_path):
        f = tmp_path / "s.json"
        stale = [tc.Item("overdue", "automation", f"t{n}", "", 5, ref=f"t{n}") for n in range(10)]
        routine = [tc.Item("open", "pr", f"PR #{n}: x", "CI: green", 1, ref="u") for n in range(6)]
        for off in (0, 7, 14, 21, 28, 35):
            week(
                tmp_path, f, off,
                [("automations", lambda c: list(stale)), ("prs", lambda c, o=off: routine if o == 0 else [])],
            )  # fmt: skip
        st = tc.seen_stats(f, D0 + timedelta(days=35))
        assert st["judged"] == 10 and st["gone"] == 0
        assert "убрать" in st["verdict"]

    def test_a_row_is_judged_from_the_day_it_became_overdue_not_from_first_sight(self, tmp_path):
        f = tmp_path / "s.json"
        quiet = lambda c: [tc.Item("open", "thread", "x", "", 1, "thread-store", "T-1")]  # noqa: E731
        late = lambda c: [tc.Item("overdue", "thread", "x", "", 1, "thread-store", "T-1")]  # noqa: E731
        week(tmp_path, f, 0, [("threads", quiet)])
        week(tmp_path, f, 14, [("threads", late)])
        data = json.loads(f.read_text(encoding="utf-8"))
        e = next(iter(data["items"].values()))
        assert e["first_seen"] == D0.isoformat()
        assert e["overdue_since"] == (D0 + timedelta(days=14)).isoformat()
        assert tc.seen_stats(f, D0 + timedelta(days=35))["judged"] == 0  # overdue only 21 days

    def test_an_overdue_row_that_is_really_resolved_counts(self, tmp_path):
        f = tmp_path / "s.json"
        a = tc.Item("overdue", "automation", "a", "", 5, ref="a")
        for off in (0, 7, 14, 21, 28):
            week(tmp_path, f, off, [("automations", lambda c: [a])])
        week(tmp_path, f, 35, [("automations", lambda c: [])])
        st = tc.seen_stats(f, D0 + timedelta(days=35))
        assert st["judged"] == 1 and st["gone"] == 1 and st["verdict"].startswith("ОСТАВИТЬ")


# --------------------------------------------------------------------------- 4: claim rows need gh too
class TestHubClaimRowsNeedTheirOwnEvidence:
    def test_the_claim_row_has_its_own_kind_with_both_collectors(self):
        assert tc.KIND_COLLECTOR["vault_claim"] == ("vault", "prs")
        assert "vault_claim" in tc.KIND_LEGEND and "vault_claim" in tc.KIND_ORDER

    def test_a_claim_row_is_not_marked_gone_while_gh_is_down(self, tmp_path):
        v = tmp_path / "vault"
        v.mkdir()
        (v / "MEMORY.md").write_text("now 4 open PRs\n", encoding="utf-8")
        f = tmp_path / "s.json"
        up = [("prs", lambda c: c.cache.update(open_pr_count=18) or []), ("vault", lambda c: [])]
        snap, _ = week(tmp_path, f, 0, up, vault=v)
        assert any(i["kind"] == "vault_claim" for i in snap["items"])
        week(tmp_path, f, 7, [("prs", unavailable), ("vault", lambda c: [])], vault=v)
        data = json.loads(f.read_text(encoding="utf-8"))
        claim = next(e for e in data["items"].values() if e["kind"] == "vault_claim")
        assert not claim.get("gone")

    def test_the_claim_row_is_marked_gone_once_both_sources_agree_again(self, tmp_path):
        v = tmp_path / "vault"
        v.mkdir()
        (v / "MEMORY.md").write_text("now 4 open PRs\n", encoding="utf-8")
        f = tmp_path / "s.json"
        week(
            tmp_path,
            f,
            0,
            [("prs", lambda c: c.cache.update(open_pr_count=18) or []), ("vault", lambda c: [])],
            vault=v,
        )
        (v / "MEMORY.md").write_text("now 18 open PRs\n", encoding="utf-8")
        week(
            tmp_path,
            f,
            7,
            [("prs", lambda c: c.cache.update(open_pr_count=18) or []), ("vault", lambda c: [])],
            vault=v,
        )
        data = json.loads(f.read_text(encoding="utf-8"))
        assert next(e for e in data["items"].values() if e["kind"] == "vault_claim").get("gone")


# --------------------------------------------------------------------------- 5, 12: damaged history
class TestDamagedHistory:
    def test_a_damaged_file_is_set_aside_not_silently_wiped(self, tmp_path):
        f = tmp_path / "s.json"
        f.write_text("{bad", encoding="utf-8")
        _, note = week(
            tmp_path,
            f,
            0,
            [("automations", lambda c: [tc.Item("overdue", "automation", "t", "", 1, ref="t")])],
        )
        aside = list(tmp_path.glob("s.json.corrupt-*"))
        assert len(aside) == 1 and aside[0].read_text(encoding="utf-8") == "{bad"
        assert note is not None and "повреждена" in note
        assert json.loads(f.read_text(encoding="utf-8"))["items"]  # a fresh, valid store

    def test_a_healthy_file_produces_no_note_and_no_aside(self, tmp_path):
        f = tmp_path / "s.json"
        week(tmp_path, f, 0, [("automations", lambda c: [])])
        _, note = week(tmp_path, f, 1, [("automations", lambda c: [])])
        assert note is None and not list(tmp_path.glob("*.corrupt-*"))

    def test_html_does_not_claim_history_when_it_is_damaged(self, tmp_path):
        f = tmp_path / "s.json"
        f.write_text("{bad", encoding="utf-8")
        snap = tc.build_snapshot(
            make_ctx(tmp_path, seen=f),
            (("automations", lambda c: [tc.Item("overdue", "automation", "t", "", 1, ref="t")]),),
        )
        # the words appear once, inside the honest coverage message about the damage itself;
        # what must be absent is the per-row claim ("· в списке N дн." / the column / the legend line)
        assert " · в списке" not in tc.render_html(snap)
        md = tc.render_markdown(snap)
        assert "| в списке |" not in md and "- **в списке**" not in md
        assert any("повреждён" in e for e in snap["collector_errors"])


# --------------------------------------------------------------------------- 6: pearl rows never vanish
class TestPearlRowsNeverVanish:
    HDR = "| date | observation | next_check | status |\n|---|---|---|---|\n"

    def parse(self, tmp_path, *rows):
        reg = tmp_path / "pearl_registry" / "INDEX.md"
        reg.parent.mkdir(exist_ok=True)
        reg.write_text(self.HDR + "".join(rows), encoding="utf-8")
        return tc._parse_pearls(reg)

    @pytest.mark.parametrize("first", ["~~2026-07-05~~", "2026-7-5", "July 5", "P1"])
    def test_an_unrecognised_first_column_is_reported(self, tmp_path, first):
        rows, bad = self.parse(tmp_path, f"| {first} | x | 2026-08-01 | pending |\n")
        assert rows == [] and len(bad) == 1 and "нет даты" in bad[0][3]

    @pytest.mark.parametrize("first", ["2026-07-05", "**2026-07-05**", "`2026-07-05`"])
    def test_plain_or_bold_dates_are_rows(self, tmp_path, first):
        rows, bad = self.parse(tmp_path, f"| {first} | x | 2026-08-01 | pending |\n")
        assert len(rows) == 1 and bad == []

    def test_an_extra_leading_column_is_not_read_as_data(self, tmp_path):
        reg = tmp_path / "r.md"
        reg.write_text(
            "| id | date | observation | next_check | status |\n|---|---|---|---|---|\n"
            "| P1 | 2026-07-05 | x | 2026-08-01 | pending |\n",
            encoding="utf-8",
        )
        rows, bad = tc._parse_pearls(reg)
        assert rows == [] and len(bad) == 1
        items = tc.collect_pearls(make_ctx(tmp_path, pearl_registries=[reg]))
        assert items and items[0].section == "open" and "ненадёжно" in items[0].title

    def test_prose_and_separator_lines_are_not_rows(self, tmp_path):
        reg = tmp_path / "r.md"
        reg.write_text(
            "# title\n\ntext | with a pipe\n"
            + self.HDR
            + "| 2026-07-05 | x | 2026-08-01 | pending |\n",
            encoding="utf-8",
        )
        rows, bad = tc._parse_pearls(reg)
        assert len(rows) == 1 and bad == []


# --------------------------------------------------------------------------- 9: the leading word
class TestLeadingWord:
    @pytest.mark.parametrize(
        "status",
        ["~~FIXED~~ reopened 2026-09-20", "done-ish", "merged? no", "closed-loop test pending",
         "pending [FIXED soon]", "dropped_maybe", "partially confirmed"],
    )  # fmt: skip
    def test_not_closed(self, status):
        assert tc._status_closed(status) is False

    @pytest.mark.parametrize(
        "status",
        [
            "FIXED",
            "Fixed:",
            "**FIXED 2026-09-19** [x]",
            "`done`",
            "(merged) later",
            "confirmed same-day",
        ],
    )
    def test_closed(self, status):
        assert tc._status_closed(status) is True


# --------------------------------------------------------------------------- 7: no index.lock, no pycache
class TestReadOnlyCollectors:
    def test_git_never_takes_optional_locks(self, tmp_path):
        seen: list[list[str]] = []

        def run(cmd, timeout=60):
            seen.append(cmd)
            if "worktree" in cmd:
                return 0, f"worktree {tmp_path}\nHEAD 1\nbranch refs/heads/main\n"
            return 128, ""

        tc.collect_git(make_ctx(tmp_path, repo=tmp_path, runner=run))
        git_cmds = [c for c in seen if c[0] == "git"]
        assert git_cmds and all(c[1] == "--no-optional-locks" for c in git_cmds)

    def test_importing_the_hook_parser_does_not_leave_bytecode_behind(self):
        import sys as _sys

        before = _sys.dont_write_bytecode
        tc._health_loop()
        assert _sys.dont_write_bytecode == before  # restored


# --------------------------------------------------------------------------- 8: warnings per collector
class TestWarningsPerCollector:
    def test_the_no_dash_r_warning_reaches_every_collector_that_calls_gh(self, tmp_path):

        def run(cmd, timeout=60):
            if (
                cmd[0] == "git" and "worktree" in cmd
            ):  # git itself works; only the remote is unknown
                return 0, f"worktree {tmp_path}\nHEAD 1\nbranch refs/heads/feat/x\n"
            return (0, "") if cmd[0] == "git" and "status" in cmd else (128, "")

        ctx = make_ctx(tmp_path, repo=tmp_path, runner=run)
        snap = tc.build_snapshot(ctx, (("prs", tc.collect_prs), ("git", tc.collect_git)))
        flagged = [e for e in snap["collector_errors"] if "без -R" in e]
        assert any(e.startswith("prs:") for e in flagged) and any(
            e.startswith("git:") for e in flagged
        )

    def test_duplicate_warnings_inside_one_collector_are_collapsed(self, tmp_path):
        ctx = make_ctx(tmp_path)
        for _ in range(3):
            tc._warn(ctx, "same thing")
        assert ctx.cache["warnings"] == ["same thing"]


# --------------------------------------------------------------------------- 10: store bytes
class TestStoreKeepsBytesOutsideItsRow:
    def test_crlf_and_bom_survive_add_and_close(self, tmp_path):
        s = tmp_path / "s.md"
        tc.add_thread(s, "first", D0)
        crlf = b"\xef\xbb\xbf" + s.read_bytes().replace(b"\n", b"\r\n")
        s.write_bytes(crlf)
        tc.add_thread(s, "second", D0)
        tc.close_thread(s, "T-20261002-01")
        out = s.read_bytes()
        assert out.startswith(b"\xef\xbb\xbf") and b"\r\n" in out
        assert b"\n" not in out.replace(b"\r\n", b"")  # no bare LF anywhere
        assert len(tc._read_store(s)) == 2

    def test_a_non_utf8_file_is_refused_and_left_untouched(self, tmp_path):
        s = tmp_path / "s.md"
        tc.add_thread(s, "ok", D0)
        raw = s.read_bytes() + "| T-9 | 2026-10-01 | caf\xe9 | a | b | | open |\n".encode("latin-1")
        s.write_bytes(raw)
        with pytest.raises(ValueError, match="не в UTF-8"):
            tc.add_thread(s, "x", D0)
        with pytest.raises(ValueError, match="не в UTF-8"):
            tc.close_thread(s, "T-9")
        assert s.read_bytes() == raw

    def test_an_lf_file_without_bom_stays_that_way(self, tmp_path):
        s = tmp_path / "s.md"
        tc.add_thread(s, "a", D0)
        tc.add_thread(s, "b", D0)
        out = s.read_bytes()
        assert b"\r\n" not in out and not out.startswith(b"\xef\xbb\xbf")


# --------------------------------------------------------------------------- secrets: JSON-quoted
class TestJsonQuotedSecrets:
    @pytest.mark.parametrize(
        "text",
        [
            # assembled from halves so the repo's secrets-scan does not see a literal
            '{"pass' + 'word": "hunter2hunter2"}',
            '{"api' + '_key":"aaaa2222bbbb"}',
            '"Tok' + 'en" : "xyz-12345-abcde"',
        ],
    )
    def test_masked(self, text):
        out = tc.clean(text)
        assert (
            "<masked>" in out
            and "hunter2" not in out
            and "aaaa2222" not in out
            and "xyz-12345" not in out
        )

    def test_an_ordinary_json_field_is_left_alone(self):
        assert tc.clean('{"name": "build-42"}') == '{"name": "build-42"}'
