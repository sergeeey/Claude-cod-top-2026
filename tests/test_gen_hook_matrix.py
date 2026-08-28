"""Tests for scripts/gen_hook_matrix.py — hooks/registry.yaml wiring-status generator.

WHY: no coverage existed before this file, despite the generator's own docstring
documenting two prior hand-derivation bugs it was built to prevent. A third,
subtler bug slipped past that generator itself (2026-08-27): classify_wiring()
trusted `class: dormant`/`class: library` unconditionally instead of
cross-checking against the actual wired set, so file_auto_parser,
hook_observability, and smart_model_router kept reporting as dormant in
docs/hook-control-matrix.md for the whole window after PR #272 actually wired
them -- caught only by a later, unrelated live-machine wiring-gap audit. These
tests pin the fix (the new "mismatch" bucket) so this exact drift can't recur
silently a second time.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import gen_hook_matrix
from gen_hook_matrix import build_matrix, classify_capability, classify_wiring, main, parse_wired

# ---------------------------------------------------------------------------
# classify_wiring
# ---------------------------------------------------------------------------


class TestClassifyWiring:
    def test_dormant_and_not_wired_stays_dormant(self):
        assert classify_wiring("foo", {"class": "dormant"}, wired=set()) == "dormant"

    def test_dormant_but_actually_wired_is_mismatch(self):
        # The exact 2026-08-27 bug: class says dormant, hooks/settings.json
        # disagrees. Must be flagged, not silently reported as dormant.
        assert classify_wiring("foo", {"class": "dormant"}, wired={"foo"}) == "mismatch"

    def test_library_and_not_wired_stays_library(self):
        assert classify_wiring("foo", {"class": "library"}, wired=set()) == "library"

    def test_library_but_actually_wired_is_mismatch(self):
        assert classify_wiring("foo", {"class": "library"}, wired={"foo"}) == "mismatch"

    def test_other_class_and_wired_is_wired(self):
        assert classify_wiring("foo", {"class": "quality"}, wired={"foo"}) == "wired"

    def test_other_class_and_not_wired_is_orphaned(self):
        assert classify_wiring("foo", {"class": "quality"}, wired=set()) == "orphaned"

    def test_missing_class_field_and_not_wired_is_orphaned(self):
        assert classify_wiring("foo", {}, wired=set()) == "orphaned"


# ---------------------------------------------------------------------------
# classify_capability
# ---------------------------------------------------------------------------


class TestClassifyCapability:
    def test_mismatch_is_not_applicable(self):
        assert (
            classify_capability({"event": "PreToolUse", "escalation": "block"}, "mismatch") == "N/A"
        )

    def test_dormant_is_not_applicable(self):
        assert classify_capability({}, "dormant") == "N/A"

    def test_wired_pretooluse_block_is_prevent(self):
        assert (
            classify_capability({"event": "PreToolUse", "escalation": "block"}, "wired")
            == "PREVENT"
        )

    def test_wired_non_pretooluse_block_is_mislabeled_warn(self):
        result = classify_capability({"event": "PostToolUse", "escalation": "block"}, "wired")
        assert result == "WARN (mislabeled block)"

    def test_wired_info_is_observe(self):
        assert (
            classify_capability({"event": "PostToolUse", "escalation": "info"}, "wired")
            == "OBSERVE"
        )


# ---------------------------------------------------------------------------
# parse_wired
# ---------------------------------------------------------------------------


class TestParseWired:
    def test_extracts_all_names_from_wrapped_command(self):
        # WHY this exact shape (2026-08-27): a sibling ad-hoc audit script this
        # same session used re.search (first match only) instead of findall,
        # and silently miscounted every hook wrapped via async_wrapper.py.
        # parse_wired already uses findall correctly -- this test pins that.
        text = '"command": "python async_wrapper.py python pattern_extractor.py"'
        assert parse_wired(text) == {"async_wrapper", "pattern_extractor"}


# ---------------------------------------------------------------------------
# build_matrix / main --check (integration, via monkeypatched module paths)
# ---------------------------------------------------------------------------

REGISTRY_TEXT = """\
  wired_hook:
    class: quality
    event: PreToolUse
    escalation: block

  stale_dormant_hook:
    class: dormant
    description: >
      Actually wired below, class field never updated.

  real_dormant_hook:
    class: dormant
    description: >
      Genuinely not registered anywhere.
"""

SETTINGS_TEXT = """\
{"hooks": {"PreToolUse": [{"hooks": [
  {"command": "python hooks/wired_hook.py"},
  {"command": "python hooks/stale_dormant_hook.py"}
]}]}}
"""


class TestBuildMatrix:
    def test_build_matrix_with_monkeypatched_files(self, tmp_path, monkeypatch):
        registry = tmp_path / "registry.yaml"
        settings = tmp_path / "settings.json"
        registry.write_text(REGISTRY_TEXT, encoding="utf-8")
        settings.write_text(SETTINGS_TEXT, encoding="utf-8")
        monkeypatch.setattr(gen_hook_matrix, "REGISTRY", registry)
        monkeypatch.setattr(gen_hook_matrix, "SETTINGS", settings)

        content, counts = build_matrix()

        assert counts["mismatch"] == 1
        assert counts["dormant"] == 1
        assert counts["wired"] == 1
        assert "MISMATCH" in content
        assert "stale_dormant_hook" in content


class TestMainCheckMode:
    def test_check_fails_on_mismatch_even_if_doc_is_up_to_date(self, tmp_path, monkeypatch, capsys):
        registry = tmp_path / "registry.yaml"
        settings = tmp_path / "settings.json"
        output = tmp_path / "hook-control-matrix.md"
        registry.write_text(REGISTRY_TEXT, encoding="utf-8")
        settings.write_text(SETTINGS_TEXT, encoding="utf-8")
        monkeypatch.setattr(gen_hook_matrix, "REGISTRY", registry)
        monkeypatch.setattr(gen_hook_matrix, "SETTINGS", settings)
        monkeypatch.setattr(gen_hook_matrix, "OUTPUT", output)

        # First write the doc so it's "up to date" by the staleness check alone.
        monkeypatch.setattr(sys, "argv", ["gen_hook_matrix.py"])
        assert main() == 0
        assert output.exists()

        # --check must still fail: the doc matches the generator, but the
        # generator itself is reporting a real registry.yaml bug.
        monkeypatch.setattr(sys, "argv", ["gen_hook_matrix.py", "--check"])
        assert main() == 1
        assert "MISMATCH" in capsys.readouterr().err

    def test_check_passes_with_no_mismatch(self, tmp_path, monkeypatch):
        registry = tmp_path / "registry.yaml"
        settings = tmp_path / "settings.json"
        output = tmp_path / "hook-control-matrix.md"
        registry.write_text(
            "  wired_hook:\n    class: quality\n    event: PreToolUse\n    escalation: block\n",
            encoding="utf-8",
        )
        settings.write_text('{"command": "python hooks/wired_hook.py"}', encoding="utf-8")
        monkeypatch.setattr(gen_hook_matrix, "REGISTRY", registry)
        monkeypatch.setattr(gen_hook_matrix, "SETTINGS", settings)
        monkeypatch.setattr(gen_hook_matrix, "OUTPUT", output)
        # WHY a real stub hooks/ dir (Gate 12a, 2026-08-28): wired_hook classifies
        # as PREVENT (PreToolUse + escalation: block) -- without this, the test
        # would pass Gate 12a only by accident (no hooks/wired_hook.py exists in
        # the REAL repo either, so the check would silently skip either way).
        # Pointing HOOKS_DIR at a real stub proves the full pipeline (mismatch +
        # Gate 12a + staleness) actually passes end-to-end, not by omission.
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "wired_hook.py").write_text(
            'if __name__ == "__main__":\n    hook_main(main, fail_closed=True)\n',
            encoding="utf-8",
        )

        monkeypatch.setattr(sys, "argv", ["gen_hook_matrix.py"])
        assert main() == 0

        monkeypatch.setattr(sys, "argv", ["gen_hook_matrix.py", "--check"])
        assert main() == 0

    def test_check_fails_on_prevent_hook_missing_explicit_fail_closed(
        self, tmp_path, monkeypatch, capsys
    ):
        registry = tmp_path / "registry.yaml"
        settings = tmp_path / "settings.json"
        output = tmp_path / "hook-control-matrix.md"
        registry.write_text(
            "  wired_hook:\n    class: quality\n    event: PreToolUse\n    escalation: block\n",
            encoding="utf-8",
        )
        settings.write_text('{"command": "python hooks/wired_hook.py"}', encoding="utf-8")
        monkeypatch.setattr(gen_hook_matrix, "REGISTRY", registry)
        monkeypatch.setattr(gen_hook_matrix, "SETTINGS", settings)
        monkeypatch.setattr(gen_hook_matrix, "OUTPUT", output)
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        # The exact live bug this gate was designed to catch (iteration_guard.py,
        # promotion_gate_guard.py before this same PR): bare main(), no wrapper.
        (tmp_path / "wired_hook.py").write_text(
            'if __name__ == "__main__":\n    main()\n', encoding="utf-8"
        )

        monkeypatch.setattr(sys, "argv", ["gen_hook_matrix.py", "--check"])
        assert main() == 1
        err = capsys.readouterr().err
        assert "Gate 12a" in err
        assert "wired_hook" in err
        assert "no hook_main() wrapper" in err


# ---------------------------------------------------------------------------
# check_prevent_hooks_explicit_fail_closed (Gate 12a) -- unit level
# ---------------------------------------------------------------------------


def _prevent_entry(event: str = "PreToolUse", escalation: str = "block") -> dict:
    return {"guard": {"event": event, "escalation": escalation, "class": "security"}}


class TestCheckPreventHooksExplicitFailClosed:
    def test_bare_main_is_flagged(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "guard.py").write_text(
            'if __name__ == "__main__":\n    main()\n', encoding="utf-8"
        )
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(), wired={"guard"}
        )
        assert len(errors) == 1
        assert "no hook_main() wrapper" in errors[0]

    def test_hook_main_without_fail_closed_is_flagged(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "guard.py").write_text(
            'if __name__ == "__main__":\n    hook_main(main)\n', encoding="utf-8"
        )
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(), wired={"guard"}
        )
        assert len(errors) == 1
        assert "without an explicit fail_closed=" in errors[0]

    def test_explicit_fail_closed_true_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "guard.py").write_text(
            'if __name__ == "__main__":\n    hook_main(main, fail_closed=True)\n',
            encoding="utf-8",
        )
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(), wired={"guard"}
        )
        assert errors == []

    def test_explicit_fail_closed_false_is_not_flagged(self, tmp_path, monkeypatch):
        # WHY this test exists: regression lock against the naive "fail_mode:
        # closed => fail_closed=True" 1:1 design rejected during Gate 12a's own
        # design (2026-08-28) -- agent_tool_scope_guard.py deliberately uses
        # fail_closed=False (a narrow additive check, safer to fall back to
        # pre-hook behavior on crash) and must never be flagged for it. The
        # gate checks that a decision was made explicitly, not what it is.
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "guard.py").write_text(
            'if __name__ == "__main__":\n'
            "    # WHY fail_closed=False: narrow additive check, see agent_tool_scope_guard.py\n"
            "    hook_main(main, fail_closed=False)\n",
            encoding="utf-8",
        )
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(), wired={"guard"}
        )
        assert errors == []

    def test_non_prevent_hook_with_bare_main_is_exempt(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "guard.py").write_text(
            'if __name__ == "__main__":\n    main()\n', encoding="utf-8"
        )
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(event="PostToolUse", escalation="warn"), wired={"guard"}
        )
        assert errors == []

    def test_fail_closed_substring_above_entrypoint_does_not_fool_the_scan(
        self, tmp_path, monkeypatch
    ):
        # Adversarial: fail_closed= appears only in a comment ABOVE the real
        # entrypoint block, whose actual entrypoint calls main() bare. The
        # scan window must be scoped to the LAST "if __name__" occurrence
        # onward, not the whole file -- else this would false-negative.
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "guard.py").write_text(
            "# fail_closed=True is fine here, unrelated note\n\n"
            'if __name__ == "__main__":\n'
            "    main()\n",
            encoding="utf-8",
        )
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(), wired={"guard"}
        )
        assert len(errors) == 1
        assert "no hook_main() wrapper" in errors[0]

    def test_fail_closed_comment_inside_block_does_not_fool_the_scan(self, tmp_path, monkeypatch):
        # Adversarial, found by self-review during Gate 12a's own review
        # (2026-08-28), BEFORE this fix landed: an earlier substring-scan
        # version of this check (raw text "fail_closed=" anywhere in the
        # if-__main__ block) false-negatived on exactly this shape -- a
        # comment mentioning "fail_closed=" sits INSIDE the block, but the
        # real call has no such keyword argument. AST-based checking (the
        # fix) looks at the real Call node's keywords, which a comment cannot
        # influence -- this test pins that fix and would fail against the
        # old substring-scan implementation.
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "guard.py").write_text(
            'if __name__ == "__main__":\n'
            "    # NOTE: fail_closed= should probably be True here but isn't yet\n"
            "    hook_main(main)\n",
            encoding="utf-8",
        )
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(), wired={"guard"}
        )
        assert len(errors) == 1
        assert "without an explicit fail_closed=" in errors[0]

    def test_multiline_hook_main_call_is_parsed_correctly(self, tmp_path, monkeypatch):
        # A linter-wrapped long call is realistic (this file's own ruff config
        # caps line length) -- the AST approach must handle args spread across
        # lines, unlike a same-line substring/regex heuristic would.
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "guard.py").write_text(
            'if __name__ == "__main__":\n'
            "    hook_main(\n"
            "        main,\n"
            "        fail_closed=True,\n"
            "    )\n",
            encoding="utf-8",
        )
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(), wired={"guard"}
        )
        assert errors == []

    def test_syntax_error_source_is_skipped_not_flagged(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        (tmp_path / "guard.py").write_text("def broken(:\n", encoding="utf-8")
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(), wired={"guard"}
        )
        assert errors == []

    def test_missing_source_file_is_skipped_not_flagged(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gen_hook_matrix, "HOOKS_DIR", tmp_path)
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(
            _prevent_entry(), wired={"guard"}
        )
        assert errors == []

    def test_real_repo_prevent_hooks_pass(self):
        # WHY no monkeypatch: this is the actual CI-equivalent assertion against
        # the real repo -- exercises the fix bundled with Gate 12a's own PR
        # (iteration_guard.py, promotion_gate_guard.py) directly, not a
        # synthetic stand-in. Fails before that fix, passes after -- pins it.
        entries = gen_hook_matrix.parse_registry(
            gen_hook_matrix.REGISTRY.read_text(encoding="utf-8")
        )
        wired = gen_hook_matrix.parse_wired(gen_hook_matrix.SETTINGS.read_text(encoding="utf-8"))
        errors = gen_hook_matrix.check_prevent_hooks_explicit_fail_closed(entries, wired)
        assert errors == []
