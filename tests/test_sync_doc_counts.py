"""Tests for scripts/sync_doc_counts.py — filesystem-authoritative hooks/
agents/skills count generator.

WHY (HS-02 P1 hotspot; 7+ historical "sync count" fix commits; this session's
own manual sync missed the root marketplace.json copy until test_structure.py
caught it): the ~13 anchor patterns are hand-verified against real file
content, not guessed. These tests encode both directions of that
verification: (1) the anchors correctly find-and-fix real drift, (2) they
never touch the 5 known off-target "N agents/hooks/skills"-shaped strings
that are NOT the total count (subset breakdowns, deltas, unrelated examples).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from sync_doc_counts import _ANCHORS, REPO, _apply_anchor, actual_counts


class TestActualCounts:
    def test_returns_hooks_agents_skills_keys(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "hooks").mkdir()
        (tmp_path / "hooks" / "a.py").write_text("", encoding="utf-8")
        (tmp_path / "hooks" / "b.py").write_text("", encoding="utf-8")
        (tmp_path / "hooks" / "utils.py").write_text("", encoding="utf-8")
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents" / "x.md").write_text("", encoding="utf-8")
        (tmp_path / "agents" / "CLAUDE.md").write_text("", encoding="utf-8")
        (tmp_path / "skills" / "core" / "y").mkdir(parents=True)
        (tmp_path / "skills" / "core" / "y" / "SKILL.md").write_text("", encoding="utf-8")
        (tmp_path / "skills" / "extensions" / "z").mkdir(parents=True)
        (tmp_path / "skills" / "extensions" / "z" / "SKILL.md").write_text("", encoding="utf-8")
        (tmp_path / "rules").mkdir()
        (tmp_path / "rules" / "r.md").write_text("", encoding="utf-8")

        import sync_doc_counts

        monkeypatch.setattr(sync_doc_counts, "REPO", tmp_path)
        counts = actual_counts()
        assert counts == {
            "hooks": 2,
            "agents": 1,
            "skills": 2,  # 1 SKILL.md under core + 1 under extensions
            "rules": 1,
            "core_skills": 1,
            "ext_skills": 1,
        }

    def test_excludes_shared_library_files_from_hook_count(self, tmp_path, monkeypatch):
        """utils.py / severity_calibrator.py / hook_state.py are shared libs,
        not hooks -- must match CI's own exclusion list exactly."""
        (tmp_path / "hooks").mkdir()
        for name in ("real_hook.py", "utils.py", "severity_calibrator.py", "hook_state.py"):
            (tmp_path / "hooks" / name).write_text("", encoding="utf-8")
        (tmp_path / "agents").mkdir()
        (tmp_path / "skills" / "core").mkdir(parents=True)
        (tmp_path / "skills" / "extensions").mkdir(parents=True)
        (tmp_path / "rules").mkdir()

        import sync_doc_counts

        monkeypatch.setattr(sync_doc_counts, "REPO", tmp_path)
        counts = actual_counts()
        assert counts["hooks"] == 1


class TestApplyAnchor:
    def test_no_drift_when_already_correct(self):
        text = "Backed by 90 hooks · 13 agents + 3 teams · rest"
        pattern = r"(Backed by )(\d+)( hooks · )(\d+)( agents \+ 3 teams · )"
        kinds = (None, "hooks", None, "agents", None)
        new_text, changed, error = _apply_anchor(text, pattern, kinds, {"hooks": 90, "agents": 13})
        assert error is None
        assert changed is False
        assert new_text == text

    def test_fixes_real_drift(self):
        text = "Backed by 89 hooks · 12 agents + 3 teams · rest"
        pattern = r"(Backed by )(\d+)( hooks · )(\d+)( agents \+ 3 teams · )"
        kinds = (None, "hooks", None, "agents", None)
        new_text, changed, error = _apply_anchor(text, pattern, kinds, {"hooks": 90, "agents": 13})
        assert error is None
        assert changed is True
        assert "90 hooks" in new_text
        assert "13 agents" in new_text

    def test_anchor_not_found_is_reported_as_error_not_silent_noop(self):
        """An anchor that can't find its target text means the SURROUNDING
        prose drifted (e.g. someone reworded the sentence) -- this must
        surface as an error for a human to fix the anchor, never silently
        pass through as 'no drift'."""
        text = "This sentence does not contain the expected phrase at all."
        pattern = r"(Backed by )(\d+)( hooks · )(\d+)( agents \+ 3 teams · )"
        kinds = (None, "hooks", None, "agents", None)
        _new_text, _changed, error = _apply_anchor(
            text, pattern, kinds, {"hooks": 90, "agents": 13}
        )
        assert error is not None
        assert "not found" in error

    def test_kinds_length_mismatch_is_reported_as_error(self):
        """Regression: a 7-group pattern with only 6 kinds entries (a
        template authoring bug, caught live while building this script)
        must fail loudly, not silently corrupt or silently skip."""
        text = "+ 90 hooks + 13 agents + all 125 skills"
        pattern = r"(\+ )(\d+)( hooks \+ )(\d+)( agents \+ all )(\d+)( skills)"  # 7 groups
        kinds = (None, "hooks", None, "agents", None, "skills")  # only 6 -- missing trailing None
        _new_text, _changed, error = _apply_anchor(
            text, pattern, kinds, {"hooks": 90, "agents": 13, "skills": 125}
        )
        assert error is not None
        assert "mismatch" in error

    def test_literal_groups_are_passed_through_unchanged(self):
        text = "Backed by 90 hooks · 13 agents + 3 teams · rest"
        pattern = r"(Backed by )(\d+)( hooks · )(\d+)( agents \+ 3 teams · )"
        kinds = (None, "hooks", None, "agents", None)
        new_text, _changed, _error = _apply_anchor(
            text, pattern, kinds, {"hooks": 90, "agents": 13}
        )
        assert new_text.startswith("Backed by 90 hooks · 13 agents + 3 teams · ")
        assert new_text.endswith("rest")


class TestAnchorPrecisionAgainstKnownOffTargets:
    """The 4 real off-target strings in this repo's actual README.md /
    docs/architecture.md that ci.yml's own check_pattern/check_meta calls do
    NOT gate -- subset counts, a tree-listing delta, and an unrelated
    example -- that a blunt 'any number before hooks/agents/skills' regex
    would wrongly rewrite. (NOTE: "13 core skills" / "112 domain skills"
    were originally listed here too, but a 2026-07-19 reviewer pass found
    ci.yml's check_pattern loop gates them for real, as ACTUAL_CORE_SKILLS /
    ACTUAL_EXT_SKILLS -- they moved to being real anchors, not off-targets.)
    Every anchor in _ANCHORS must NOT match any of these four strings,
    confirmed exhaustively (not just spot-checked), since a false match on
    any anchor would silently corrupt real prose."""

    OFF_TARGETS = [
        "| **Agent memory** | stateless | 4 agents with persistent memory across sessions |",
        "4 agents with **persistent memory** · 2 agents with **worktree isolation**"
        " · Sonnet-first, Opus escalation only",
        "│   └── ...                        39 more hooks",
        "Without Progressive Disclosure all 5 rules + 8 skills would load"
        " immediately = +3000 tokens/message.",
    ]

    def test_no_anchor_matches_any_off_target_string(self):
        import re

        for off_target in self.OFF_TARGETS:
            for _rel_path, pattern, _kinds in _ANCHORS:
                assert re.search(pattern, off_target) is None, (
                    f"Anchor {pattern!r} incorrectly matches off-target "
                    f"string {off_target!r} -- this would corrupt real prose."
                )


class TestPreservesLineEndings:
    """Regression (2026-07-19, found during a pre-push review): a bare
    read_text()/write_text() roundtrip on Windows translates every "\n" in
    the string to os.linesep ("\r\n") on write unless newline="" disables
    that translation -- silently flipping an ENTIRE file from LF to CRLF
    even though .gitattributes mandates `eol=lf` for every file this script
    touches (*.md, *.json). Verified live: a raw roundtrip converted all 594
    LF line endings in README.md to CRLF. Git's attribute-based normalization
    likely fixes the STORED blob on the next add/commit, but depending on
    that instead of writing correct bytes is fragile -- this test exercises
    the actual main() write path end-to-end against LF fixture files."""

    def test_main_write_path_preserves_lf_even_when_rewriting_unchanged_files(
        self, tmp_path, monkeypatch
    ):
        import sync_doc_counts

        # Two files: one with real drift (forces main() past the early
        # "nothing to do" return so the write loop actually runs), one
        # already correct -- main() rewrites BOTH (see main()'s write loop,
        # which iterates every file in by_file unconditionally), so the
        # regression must be checked on the untouched file too, not just
        # the one with real drift.
        drifted = tmp_path / "drifted.md"
        drifted.write_bytes(b"Backed by 89 hooks\ncount here\n")
        already_correct = tmp_path / "correct.md"
        already_correct.write_bytes(b"Backed by 90 hooks\nno drift here\n")

        monkeypatch.setattr(sync_doc_counts, "REPO", tmp_path)
        monkeypatch.setattr(
            sync_doc_counts,
            "_ANCHORS",
            [
                ("drifted.md", r"(Backed by )(\d+)( hooks)", (None, "hooks", None)),
                ("correct.md", r"(Backed by )(\d+)( hooks)", (None, "hooks", None)),
            ],
        )
        monkeypatch.setattr(
            sync_doc_counts,
            "actual_counts",
            lambda: {"hooks": 90, "agents": 13, "skills": 125},
        )
        monkeypatch.setattr("sys.argv", ["sync_doc_counts.py"])  # write mode, not --check

        sync_doc_counts.main()

        for f in (drifted, already_correct):
            data = f.read_bytes()
            assert b"\r\n" not in data, (
                f"{f.name}: write introduced CRLF -- newline=\"\" regression"
            )


class TestAnchorsCoverCIChecks:
    """Regression (2026-07-19, reviewer finding): the first version of this
    generator covered only 13 anchors -- the 3 numbers checked by CI's
    "Verify doc counts match filesystem" step -- and silently missed 5 more
    real total-count occurrences that ci.yml's SEPARATE check_pattern/
    check_meta loop (~17 calls) also gates. A human forgetting to add an
    anchor is exactly the failure mode this whole script exists to remove;
    this test makes that specific class of gap self-defending by parsing
    ci.yml directly (not a hardcoded duplicate list, which could itself
    drift from ci.yml the same way the anchors drifted from it) and proving
    every check_pattern's regex, run against the CURRENT (correct) README.md,
    finds the same value actual_counts() reports -- i.e. CI's own checks and
    this script's filesystem source of truth agree, for every single gated
    location, not just the ones a human remembered to anchor."""

    def test_every_check_pattern_regex_matches_actual_counts_in_readme(self):
        import re

        ci_yml = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        actual = actual_counts()

        # Map each check_pattern call's $ACTUAL_* shell variable to the
        # matching actual_counts() key.
        var_to_kind = {
            "ACTUAL_HOOKS": "hooks",
            "ACTUAL_AGENTS": "agents",
            "ACTUAL_SKILLS": "skills",
            "ACTUAL_RULES": "rules",
            "ACTUAL_CORE_SKILLS": "core_skills",
            "ACTUAL_EXT_SKILLS": "ext_skills",
        }

        # `check_pattern "label" "$VAR" 'sed_expr'` -- sed_expr's own capture
        # group is plain extended-regex, directly usable as a Python regex.
        calls = re.findall(
            r"""check_pattern\s+"([^"]+)"\s+"\$(\w+)"\s+'(.+?)'""",
            ci_yml,
        )
        assert len(calls) >= 15, (
            f"Expected ~17 check_pattern calls in ci.yml, found {len(calls)} -- "
            "the parsing regex above may need updating if ci.yml's shell syntax changed."
        )

        checked_any_for = set()
        for label, var, sed_expr in calls:
            kind = var_to_kind.get(var)
            if kind is None:
                continue  # a check_pattern for a variable this script doesn't track
            # WHY translate [[:space:]] -> \s: this is valid POSIX ERE
            # (what bash's `sed -E` uses), but Python's `re` module does
            # NOT support POSIX bracket-expression classes -- it would
            # silently parse [[:space:]] as a literal (broken) character
            # class instead of raising, so this must be translated, not
            # passed through as-is.
            py_pattern = sed_expr.replace("[[:space:]]", r"\s")
            match = re.search(py_pattern, readme)
            assert match is not None, (
                f"ci.yml check_pattern {label!r} (pattern {sed_expr!r}) does not "
                f"match anything in the current README.md -- either the anchor "
                f"prose changed, or _ANCHORS in sync_doc_counts.py is missing "
                f"coverage for this CI-gated location."
            )
            found = int(match.group(1))
            assert found == actual[kind], (
                f"ci.yml check_pattern {label!r} extracts {found} but "
                f"actual_counts()['{kind}'] is {actual[kind]} -- README has "
                f"drifted from the filesystem at a location _ANCHORS may not cover."
            )
            checked_any_for.add(kind)

        # Sanity: this test should exercise every kind actual_counts() defines,
        # not just a subset -- otherwise a whole NEW kind could go unchecked here.
        assert checked_any_for == set(actual.keys()), (
            f"check_pattern calls only exercised {checked_any_for} but "
            f"actual_counts() defines {set(actual.keys())} -- a kind has no "
            f"corresponding ci.yml check_pattern call for this test to verify."
        )


class TestAnchorsSelfConsistent:
    """Every anchor's group count must match its kinds tuple length -- this
    is what test_kinds_length_mismatch_is_reported_as_error tests for a
    synthetic example; this test checks it holds for the REAL, live anchor
    list, so a future edit to _ANCHORS can't silently reintroduce the same
    class of bug this file was built to catch."""

    def test_every_real_anchor_has_matching_group_and_kinds_count(self):
        import re

        for rel_path, pattern, kinds in _ANCHORS:
            compiled = re.compile(pattern)
            assert compiled.groups == len(kinds), (
                f"{rel_path}: pattern {pattern!r} has {compiled.groups} groups "
                f"but kinds has {len(kinds)} entries"
            )
