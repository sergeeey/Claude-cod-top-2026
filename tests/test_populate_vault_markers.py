"""Regression tests for scripts/populate_vault.py's "#auto-capture" marker.

WHY this file exists (Codex review, PR #349): mine_git_history() (--git) and
sync_cogniml_skills() (--cogniml) generate the exact low-information,
high-volume content hooks/auto_capture.py already tags "#auto-capture" for
exclusion from retrieval (raw_to_wiki.py's _resolve_para_dir()) -- but before
this fix, neither function tagged its own output that way. A Codex review
correctly caught that an earlier version of this comment in raw_to_wiki.py
claimed "no live writer" for the git-feat-/git-fix-* naming pattern, verified
only against hooks/*.py and missing scripts/*.py entirely -- populate_vault.py
--git is a real, live (if manually-invoked) generator that would have
silently repopulated the exact corpus-dilution noise the auto_capture.py
exclusion was built to remove, on any future re-run.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import populate_vault  # noqa: E402


class TestMineGitHistoryMarker:
    def test_feat_commit_tagged_auto_capture(self, tmp_path, monkeypatch):
        monkeypatch.setattr(populate_vault, "RAW_DIR", tmp_path)
        fake_result = MagicMock()
        fake_result.stdout = (
            "==COMMIT_BOUNDARY==\nabc123def456\n2026-09-04\nfeat: add widget\nsome body text\n"
        )
        monkeypatch.setattr(populate_vault.subprocess, "run", lambda *a, **k: fake_result)

        count = populate_vault.mine_git_history(tmp_path, limit=10)

        assert count == 1
        written = list(tmp_path.glob("git-feat-*.md"))
        assert len(written) == 1
        content = written[0].read_text(encoding="utf-8")
        assert "#auto-capture" in content

    def test_fix_commit_tagged_auto_capture(self, tmp_path, monkeypatch):
        monkeypatch.setattr(populate_vault, "RAW_DIR", tmp_path)
        fake_result = MagicMock()
        fake_result.stdout = (
            "==COMMIT_BOUNDARY==\nfeed00d1234\n2026-09-04\nfix: crash on empty input\n\n"
        )
        monkeypatch.setattr(populate_vault.subprocess, "run", lambda *a, **k: fake_result)

        populate_vault.mine_git_history(tmp_path, limit=10)

        written = list(tmp_path.glob("git-fix-*.md"))
        assert len(written) == 1
        assert "#auto-capture" in written[0].read_text(encoding="utf-8")


class TestSyncCogniMLSkillsMarker:
    def test_skill_tagged_auto_capture_regardless_of_api_tags(self, tmp_path, monkeypatch):
        """WHY: the marker must not depend on whatever CogniML's own API
        happens to return in `tags` -- it must always be present so
        _resolve_para_dir() reliably excludes every mined skill."""
        monkeypatch.setattr(populate_vault, "RAW_DIR", tmp_path)
        fake_response = {
            "skills": [
                {
                    "skill_id": "f8470a39abcd",
                    "title": "Retrospective: smoke-exp-001",
                    "body": "some evidence text",
                    "tags": ["unrelated-tag"],  # deliberately NOT "auto-generated"
                    "domain": "smoke-cv",
                    "evidence_strength": "inferred",
                    "status": "in_review",
                    "confidence": 0.85,
                    "created_at": "2026-04-15T00:00:00Z",
                }
            ]
        }
        monkeypatch.setattr(populate_vault, "_cogniml_get", lambda path: fake_response)

        count = populate_vault.sync_cogniml_skills()

        assert count == 1
        written = list(tmp_path.glob("cogniml-skill-*.md"))
        assert len(written) == 1
        assert "#auto-capture" in written[0].read_text(encoding="utf-8")
