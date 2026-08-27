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

        monkeypatch.setattr(sys, "argv", ["gen_hook_matrix.py"])
        assert main() == 0

        monkeypatch.setattr(sys, "argv", ["gen_hook_matrix.py", "--check"])
        assert main() == 0
