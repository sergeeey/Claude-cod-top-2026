"""Other text paths of knowledge_librarian must not inject secret values into context.

Found by synthetic checks on 2026-11-27: the index topic heading, the playbook best approach and
the CogniML answer reached the injected context without redaction. Values are synthetic.
"""

from __future__ import annotations

import knowledge_librarian as kl


def test_index_topic_heading_with_secret_is_scrubbed(monkeypatch, tmp_path):
    index = tmp_path / "index.md"
    index.write_text("### api_key=hunter9 (3)\n### research (4)\n", encoding="utf-8")
    monkeypatch.setattr(kl, "WIKI_INDEX", index)
    out = kl._read_index_topics()
    assert "hunter9" not in out
    assert "research(4)" in out


def test_playbook_best_approach_with_secret_is_scrubbed(monkeypatch, tmp_path):
    playbook = tmp_path / "playbook.md"
    playbook.write_text("### token=hunter8 approach\n", encoding="utf-8")
    monkeypatch.setattr(kl, "PLAYBOOK_PATH", playbook)
    out = kl._best_approach()
    assert "hunter8" not in out


def test_playbook_best_approach_without_secret_is_unchanged(monkeypatch, tmp_path):
    playbook = tmp_path / "playbook.md"
    playbook.write_text("### разбивать задачу на шаги\n", encoding="utf-8")
    monkeypatch.setattr(kl, "PLAYBOOK_PATH", playbook)
    assert kl._best_approach() == "разбивать задачу на шаги"


def test_cogniml_answer_with_secret_is_scrubbed_before_injection(monkeypatch):
    captured: dict[str, str] = {}

    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    monkeypatch.setattr(kl, "parse_stdin", lambda: {})
    monkeypatch.setattr(kl, "_read_current_focus", lambda: "тема для поиска")
    monkeypatch.setattr(kl, "_extract_keywords", lambda text: ["тема"])
    monkeypatch.setattr(kl, "_query_wiki_raw_titles", lambda *a, **k: [])
    monkeypatch.setattr(kl, "_classify_and_render_wiki", lambda *a, **k: ([], []))
    monkeypatch.setattr(kl, "_query_patterns", lambda keywords: [])
    monkeypatch.setattr(kl, "_top_avoid_patterns", lambda limit=5: [])
    monkeypatch.setattr(kl, "_best_approach", lambda: "")
    monkeypatch.setattr(kl, "_read_index_topics", lambda: "")
    monkeypatch.setattr(
        kl.cogniml_client,
        "advise",
        lambda query, top_k=2: "для этого используйте password=hunter7 в конфиге",
    )
    monkeypatch.setattr(
        kl, "emit_hook_result", lambda event, context: captured.setdefault("ctx", context)
    )
    try:
        kl.main()
    except SystemExit:
        pass
    ctx = captured.get("ctx", "")
    assert "CogniML insight" in ctx
    assert "hunter7" not in ctx
