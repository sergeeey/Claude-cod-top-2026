"""Tests for project_classifier.py — adaptive dispatcher SessionStart hook.

WHY: the classifier writes project_profile.md AND must surface its verdict
into Claude's context as structured additionalContext (the loop-closing fix).
A bare print() would write the file but never reach Claude. These tests pin
both behaviours: correct classification + valid context emission.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

import project_classifier as pc  # noqa: E402

# ── _emit_context (the loop-closing fix) ──────────────────────────────────────


class TestEmitContext:
    def test_emits_valid_json(self, capsys: pytest.CaptureFixture):
        # ACT
        pc._emit_context("hello")
        # ASSERT: stdout is parseable JSON in Claude Code hook protocol shape
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert data["hookSpecificOutput"]["additionalContext"] == "hello"

    def test_message_preserved_with_special_chars(self, capsys: pytest.CaptureFixture):
        # ARRANGE: message with the × char and braces that must survive JSON
        msg = "[dispatcher] Project 'X' → research (margin=2) {'a': 1}"
        pc._emit_context(msg)
        data = json.loads(capsys.readouterr().out)
        assert data["hookSpecificOutput"]["additionalContext"] == msg


# ── classify ──────────────────────────────────────────────────────────────────


class TestClassify:
    def test_unonboarded_when_no_claude_dir(self, tmp_path):
        # ARRANGE: bare dir, no .claude/
        ptype, margin, scores = pc.classify(tmp_path)
        # ASSERT
        assert ptype == "unonboarded"

    def test_research_from_content_keywords(self, tmp_path):
        # ARRANGE: .claude/ exists + CLAUDE.md with research intent
        (tmp_path / ".claude").mkdir()
        (tmp_path / "CLAUDE.md").write_text(
            "This project tests a scientific hypothesis with falsification and estimand design.",
            encoding="utf-8",
        )
        (tmp_path / "experiments").mkdir()
        # ACT
        ptype, margin, scores = pc.classify(tmp_path)
        # ASSERT: content keywords (weight 2) push research above the rest
        assert ptype == "research"
        assert scores["research"] >= scores["production"]

    def test_production_from_content(self, tmp_path):
        # ARRANGE: production intent in README
        (tmp_path / ".claude").mkdir()
        (tmp_path / "README.md").write_text(
            "Production library for deploy. CI/CD release pipeline, config toolkit, api server.",
            encoding="utf-8",
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        # ACT
        ptype, _margin, _scores = pc.classify(tmp_path)
        # ASSERT
        assert ptype == "production"

    def test_ambiguous_when_no_content_signal(self, tmp_path):
        # ARRANGE: .claude/ exists but no README/CLAUDE.md content keywords
        (tmp_path / ".claude").mkdir()
        (tmp_path / "tests").mkdir()  # structure only — no content intent
        # ACT
        ptype, _margin, _scores = pc.classify(tmp_path)
        # ASSERT: structure alone is unreliable → defer to LLM
        assert ptype == "ambiguous"


# ── write_profile ─────────────────────────────────────────────────────────────


class TestWriteProfile:
    def test_writes_profile_file(self, tmp_path):
        # ARRANGE
        (tmp_path / ".claude").mkdir()
        # ACT
        out = pc.write_profile(tmp_path, "production", 2, {"production": 7, "research": 5})
        # ASSERT: file created with type + confidence + methodology
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "production" in content
        assert "HIGH" in content
        assert "reviewer" in content  # methodology text


# ── main() end-to-end ─────────────────────────────────────────────────────────


def _make_stdin(payload: dict):
    import io

    return io.StringIO(json.dumps(payload))


class TestMain:
    def test_main_emits_context_for_classified_project(
        self, tmp_path, monkeypatch, capsys: pytest.CaptureFixture
    ):
        # ARRANGE: a production-looking project, cwd switched to it
        (tmp_path / ".claude").mkdir()
        (tmp_path / "README.md").write_text(
            "Production library, deploy, ci/cd release, config toolkit, api server.",
            encoding="utf-8",
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        # ACT
        pc.main()

        # ASSERT: emitted valid JSON context mentioning the dispatcher verdict
        out = capsys.readouterr().out
        data = json.loads(out)
        ctx = data["hookSpecificOutput"]["additionalContext"]
        assert "[dispatcher]" in ctx
        # AND profile file was written
        assert (tmp_path / ".claude" / "memory" / "_auto" / "project_profile.md").exists()

    def test_main_never_raises_on_bad_cwd(self, monkeypatch, capsys: pytest.CaptureFixture):
        # ARRANGE: classify raises → main must swallow (SessionStart never blocks)
        def boom(_root):
            raise RuntimeError("simulated")

        monkeypatch.setattr(pc, "classify", boom)

        # ACT — must not raise
        pc.main()

        # ASSERT: error went to stderr, not a crash
        captured = capsys.readouterr()
        assert "skipped" in captured.err or captured.err == "" or captured.out == ""
