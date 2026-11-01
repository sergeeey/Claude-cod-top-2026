"""Tests for the weekly archive, the 'listed for N days' history and the computed kill criterion."""

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


def ctx_for(tmp_path: Path, today: date = D0, seen: bool = True) -> tc.Context:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    return tc.Context(
        today=today,
        repo=None,
        vault=vault,
        pearl_registries=[],
        threads_file=vault / "t.md",
        log_dir=tmp_path / "logs",
        seen_file=tmp_path / "seen.json" if seen else None,
        is_windows=True,
    )


def collector(items):
    return lambda ctx: list(items)


def snap_for(ctx, items, name="automations"):
    return tc.build_snapshot(ctx, ((name, collector(items)),))


TASK = tc.Item("overdue", "automation", "задача X падает", "код 1", 3, ref="X")
PEARL = tc.Item(
    "overdue", "pearl", "an old pearl", "next_check 2026-08-04", 59, ref="rules/pearl_registry"
)


class TestItemKey:
    def test_counters_inside_titles_do_not_change_identity(self):
        a = tc._item_key("pr", "", "14 автоматических PR (FocusOS и т.п.) не рассмотрены")
        b = tc._item_key("pr", "", "13 автоматических PR (FocusOS и т.п.) не рассмотрены")
        assert a == b
        v1 = tc._item_key("vault", "", "Obsidian: 17 из 18 хабов устарели")
        v2 = tc._item_key("vault", "", "Obsidian: 16 из 18 хабов устарели")
        assert v1 == v2

    def test_a_real_pr_number_is_part_of_identity(self):
        assert tc._item_key("pr", "", "PR #1: x") != tc._item_key("pr", "", "PR #2: x")

    def test_ref_distinguishes_automations_and_threads_only(self):
        assert tc._item_key("automation", "A", "t") != tc._item_key("automation", "B", "t")
        assert tc._item_key("pearl", "reg1", "t") == tc._item_key("pearl", "reg2", "t")


class TestSeenStore:
    def test_first_render_marks_everything_new_and_later_renders_age_it(self, tmp_path):
        ctx = ctx_for(tmp_path)
        snap = snap_for(ctx, [TASK])
        assert snap["items"][0]["listed_days"] == 0 and snap["seen_tracked"] is True
        tc.update_seen(ctx.seen_file, snap, D0)
        later = ctx_for(tmp_path, D0 + timedelta(days=9))
        snap2 = snap_for(later, [TASK])
        assert snap2["items"][0]["listed_days"] == 9
        assert snap2["items"][0]["first_seen"] == D0.isoformat()

    def test_dry_run_style_snapshot_never_writes_the_store(self, tmp_path):
        ctx = ctx_for(tmp_path)
        snap_for(ctx, [TASK])
        assert not ctx.seen_file.exists()

    def test_no_seen_file_means_no_history_columns(self, tmp_path):
        snap = snap_for(ctx_for(tmp_path, seen=False), [TASK])
        assert snap["seen_tracked"] is False and "listed_days" not in snap["items"][0]
        assert "в списке" not in tc.render_markdown(snap)

    def test_a_row_that_leaves_a_cleanly_checked_source_is_marked_gone(self, tmp_path):
        ctx = ctx_for(tmp_path)
        tc.update_seen(
            ctx.seen_file, snap_for(ctx, [TASK, PEARL], "mixed"), D0
        )  # unknown collector
        # use real collector names so the kind -> collector trust map applies
        tc.update_seen(
            ctx.seen_file,
            tc.build_snapshot(
                ctx, (("automations", collector([TASK])), ("pearls", collector([PEARL])))
            ),
            D0,
        )
        nxt = D0 + timedelta(days=7)
        c2 = ctx_for(tmp_path, nxt)
        snap = tc.build_snapshot(
            c2, (("automations", collector([])), ("pearls", collector([PEARL])))
        )
        tc.update_seen(c2.seen_file, snap, nxt)
        data = json.loads(c2.seen_file.read_text(encoding="utf-8"))
        gone = {e["kind"]: e.get("gone") for e in data["items"].values()}
        assert gone["automation"] == nxt.isoformat() and gone["pearl"] is None

    def test_unknown_is_not_resolved_a_failed_or_partial_collector_marks_nothing_gone(
        self, tmp_path
    ):
        ctx = ctx_for(tmp_path)
        tc.update_seen(
            ctx.seen_file,
            tc.build_snapshot(
                ctx, (("automations", collector([TASK])), ("pearls", collector([PEARL])))
            ),
            D0,
        )
        nxt = D0 + timedelta(days=7)
        c2 = ctx_for(tmp_path, nxt)

        def down(_):
            raise tc.CollectorUnavailable("scheduler offline")

        def partial(c):
            tc._warn(c, "half readable")
            return []

        snap = tc.build_snapshot(c2, (("automations", down), ("pearls", partial)))
        tc.update_seen(c2.seen_file, snap, nxt)
        data = json.loads(c2.seen_file.read_text(encoding="utf-8"))
        assert all(not e.get("gone") for e in data["items"].values())

    def test_a_row_that_comes_back_is_new_again(self, tmp_path):
        ctx = ctx_for(tmp_path)
        tc.update_seen(
            ctx.seen_file, tc.build_snapshot(ctx, (("automations", collector([TASK])),)), D0
        )
        d1 = D0 + timedelta(days=7)
        c1 = ctx_for(tmp_path, d1)
        tc.update_seen(c1.seen_file, tc.build_snapshot(c1, (("automations", collector([])),)), d1)
        d2 = D0 + timedelta(days=14)
        c2 = ctx_for(tmp_path, d2)
        snap = tc.build_snapshot(c2, (("automations", collector([TASK])),))
        assert snap["items"][0]["listed_days"] == 0

    def test_a_damaged_store_is_reported_not_trusted(self, tmp_path):
        ctx = ctx_for(tmp_path)
        ctx.seen_file.write_text("{not json", encoding="utf-8")
        snap = snap_for(ctx, [TASK])
        assert snap["seen_tracked"] is False
        assert any("история" in e and "повреждён" in e for e in snap["collector_errors"])
        ctx.seen_file.write_text("[1, 2]", encoding="utf-8")
        assert any("неожиданного формата" in e for e in snap_for(ctx, [TASK])["collector_errors"])

    def test_old_gone_rows_are_forgotten(self, tmp_path):
        ctx = ctx_for(tmp_path)
        tc.update_seen(
            ctx.seen_file, tc.build_snapshot(ctx, (("automations", collector([TASK])),)), D0
        )
        c1 = ctx_for(tmp_path, D0 + timedelta(days=1))
        tc.update_seen(
            c1.seen_file, tc.build_snapshot(c1, (("automations", collector([])),)), c1.today
        )
        far = D0 + timedelta(days=tc.SEEN_KEEP_DAYS + 5)
        c2 = ctx_for(tmp_path, far)
        tc.update_seen(c2.seen_file, tc.build_snapshot(c2, (("automations", collector([])),)), far)
        assert json.loads(c2.seen_file.read_text(encoding="utf-8"))["items"] == {}

    def test_renders_are_recorded_once_per_day(self, tmp_path):
        ctx = ctx_for(tmp_path)
        snap = snap_for(ctx, [])
        tc.update_seen(ctx.seen_file, snap, D0)
        tc.update_seen(ctx.seen_file, snap, D0)
        assert json.loads(ctx.seen_file.read_text(encoding="utf-8"))["renders"] == [D0.isoformat()]


class TestStats:
    def build(self, tmp_path, days: list[int], resolved: set[str]):
        """Render on the given day offsets; rows listed from day 0, the `resolved` ones leave later."""
        ctx = ctx_for(tmp_path)
        rows = {"a": TASK, "b": PEARL, "c": tc.Item("overdue", "pr", "PR #9: x", "", 20, ref="u")}
        for off in days:
            d = D0 + timedelta(days=off)
            c = ctx_for(tmp_path, d)
            listed = [v for k, v in rows.items() if not (k in resolved and off >= 14)]
            kinds = {"automation": "automations", "pearl": "pearls", "pr": "prs"}
            by: dict[str, list] = {n: [] for n in kinds.values()}
            for it in listed:
                by[kinds[it.kind]].append(it)
            snap = tc.build_snapshot(c, tuple((n, collector(v)) for n, v in by.items()))
            tc.update_seen(c.seen_file, snap, d)
        return ctx

    def test_too_little_history_gives_no_verdict(self, tmp_path):
        ctx = self.build(tmp_path, [0, 7], set())
        st = tc.seen_stats(ctx.seen_file, D0 + timedelta(days=7))
        assert st["verdict"].startswith("НЕДОСТАТОЧНО ИСТОРИИ")

    def test_a_third_or_more_resolved_keeps_the_tool(self, tmp_path):
        ctx = self.build(tmp_path, [0, 7, 14, 21, 28, 35], {"a", "b"})
        st = tc.seen_stats(ctx.seen_file, D0 + timedelta(days=35))
        assert st["judged"] == 3 and st["gone"] == 2
        assert st["verdict"].startswith("ОСТАВИТЬ")

    def test_less_than_a_third_resolved_triggers_the_kill_criterion(self, tmp_path):
        ctx = self.build(tmp_path, [0, 7, 14, 21, 28, 35], set())
        st = tc.seen_stats(ctx.seen_file, D0 + timedelta(days=35))
        assert st["gone"] == 0 and "убрать" in st["verdict"]

    def test_no_store_at_all_is_insufficient_not_a_crash(self, tmp_path):
        st = tc.seen_stats(tmp_path / "none.json", D0)
        assert st["verdict"].startswith("НЕДОСТАТОЧНО ИСТОРИИ") and st["share"] is None

    def test_a_damaged_store_gives_no_data(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text("nope", encoding="utf-8")
        assert tc.seen_stats(p, D0)["verdict"].startswith("НЕТ ДАННЫХ")

    def test_stats_command_prints_and_exits_zero(self, tmp_path, capsys):
        rc = tc.main(
            ["stats", "--vault", str(tmp_path / "v"), "--seen-file", str(tmp_path / "s.json")]
        )
        out = capsys.readouterr().out
        assert rc == 0 and "запусков render: 0" in out and "НЕДОСТАТОЧНО ИСТОРИИ" in out


class TestArchive:
    def test_iso_week_label(self):
        assert tc.iso_week(date(2026, 10, 2)) == "2026-W40"
        assert tc.iso_week(date(2026, 1, 1)) == "2026-W01"
        assert (
            tc.iso_week(date(2027, 1, 1)) == "2026-W53"
        )  # ISO year differs from the calendar year

    def test_history_lists_earlier_weeks_newest_first_and_skips_the_current_one(self, tmp_path):
        folder = tmp_path / tc.ARCHIVE_DIR_REL
        folder.mkdir(parents=True)
        for w in ("2026-W37", "2026-W39", "2026-W40", "2026-W38", "notes", "2026-W9"):
            (folder / f"{w}.md").write_text("x", encoding="utf-8")
        got = tc.archive_history(tmp_path, D0)
        assert got == [
            f"{tc.ARCHIVE_DIR_REL}/2026-W39",
            f"{tc.ARCHIVE_DIR_REL}/2026-W38",
            f"{tc.ARCHIVE_DIR_REL}/2026-W37",
        ]

    def test_history_is_empty_without_an_archive_folder(self, tmp_path):
        assert tc.archive_history(tmp_path, D0) == []

    def test_weekly_note_has_snapshot_frontmatter_and_links_back_to_the_live_note(self, tmp_path):
        snap = snap_for(ctx_for(tmp_path), [TASK])
        md = tc.render_markdown(snap, week="2026-W40")
        assert md.startswith("---\ntype: dashboard-snapshot\nweek: 2026-W40")
        assert "overdue: 1" in md and "# Центр нитей — неделя 2026-W40" in md
        assert f"[[{tc.THREADS_NOTE_REL.removesuffix('.md')}]]" in md

    def test_live_note_links_to_the_previous_weeks(self, tmp_path):
        ctx = ctx_for(tmp_path)
        folder = ctx.vault / tc.ARCHIVE_DIR_REL
        folder.mkdir(parents=True)
        (folder / "2026-W39.md").write_text("x", encoding="utf-8")
        md = tc.render_markdown(snap_for(ctx, [TASK]))
        assert f"[[{tc.ARCHIVE_DIR_REL}/2026-W39]]" in md and "Предыдущие недели" in md

    def test_render_writes_the_archive_once_per_week_and_dry_run_writes_nothing(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(tc, "COLLECTORS", (("automations", collector([TASK])),))
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        base = ["--vault", str(tmp_path / "vault"), "--repo", str(tmp_path)]
        assert tc.main(["render", "--dry-run", *base]) == 0
        assert not (tmp_path / "vault").exists() and not (tmp_path / "home").exists()
        assert tc.main(["render", *base]) == 0
        assert tc.main(["render", *base]) == 0
        folder = tmp_path / "vault" / tc.ARCHIVE_DIR_REL
        assert len(list(folder.glob("*.md"))) == 1

    def test_no_archive_flag(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tc, "COLLECTORS", (("automations", collector([TASK])),))
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        base = ["--vault", str(tmp_path / "vault"), "--repo", str(tmp_path)]
        assert tc.main(["render", "--no-archive", *base]) == 0
        assert not (tmp_path / "vault" / tc.ARCHIVE_DIR_REL).exists()

    def test_summary_and_collect_never_touch_history_or_archive(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tc, "COLLECTORS", (("automations", collector([TASK])),))
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        base = ["--vault", str(tmp_path / "vault"), "--repo", str(tmp_path)]
        tc.main(["summary", *base])
        tc.main(["collect", *base])
        assert not (tmp_path / "home").exists()


class TestLegendAndColumn:
    def test_markdown_has_the_in_list_column_and_a_legend_for_present_kinds_only(self, tmp_path):
        ctx = ctx_for(tmp_path)
        tc.update_seen(ctx.seen_file, snap_for(ctx, [TASK]), D0)
        later = ctx_for(tmp_path, D0 + timedelta(days=5))
        md = tc.render_markdown(snap_for(later, [TASK]))
        assert "| что | подробности | возраст | в списке | источник |" in md
        assert "| 5 дн. | automation |" in md
        assert "## ЧТО ЭТО ЗА СТРОКИ" in md and "**automation**" in md and "**pearl**" not in md
        assert "**в списке**" in md

    def test_a_new_row_says_new(self, tmp_path):
        md = tc.render_markdown(snap_for(ctx_for(tmp_path), [TASK]))
        assert "| новое |" in md

    def test_html_shows_the_listed_days_and_the_legend(self, tmp_path):
        ctx = ctx_for(tmp_path)
        tc.update_seen(ctx.seen_file, snap_for(ctx, [TASK]), D0)
        later = ctx_for(tmp_path, D0 + timedelta(days=5))
        html_out = tc.render_html(snap_for(later, [TASK]))
        assert "в списке 5 дн." in html_out and "ЧТО ЭТО ЗА СТРОКИ" in html_out

    def test_every_kind_the_collectors_emit_has_a_legend_and_a_collector(self):
        for kind in tc.KIND_ORDER:
            assert kind in tc.KIND_LEGEND and kind in tc.KIND_COLLECTOR, kind
        needed = {c for cs in tc.KIND_COLLECTOR.values() for c in cs}
        assert needed <= {n for n, _ in tc.COLLECTORS}

    @pytest.mark.parametrize("n", [0, 1, 7])
    def test_listed_label(self, n):
        assert tc._listed({"listed_days": n}) == ("новое" if n == 0 else f"{n} дн.")
        assert tc._listed({}) == "—"
