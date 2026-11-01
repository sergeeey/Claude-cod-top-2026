"""session_start injects activeContext.md under a cap, keeping the head and marking the cut."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import session_start  # noqa: E402


def _isolate(monkeypatch, mem_dir: Path) -> None:
    # WHY: main() also prints learning tips, lessons and scope fences from the real
    # home directory. Silence those so the test only sees the active-context block.
    for name in (
        "check_first_run",
        "print_learning_tip",
        "print_accumulated_lessons",
        "auto_update_config_repo",
        "print_scope_fence",
    ):
        monkeypatch.setattr(session_start, name, lambda *a, **k: None)
    monkeypatch.setattr(session_start, "check_new_project", lambda: False)
    monkeypatch.setattr(session_start, "find_project_claude_dir", lambda: mem_dir)
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)


def test_long_active_context_is_truncated_with_marker(tmp_path, monkeypatch, capsys):
    head = "# activeContext\n## CURRENT STATE\nTASK: keep this line\n"
    history = "".join(f"## Old session {i}\n" + "history line\n" * 40 for i in range(60))
    (tmp_path / "activeContext.md").write_text(head + history, encoding="utf-8")
    _isolate(monkeypatch, tmp_path)

    session_start.main()
    out = capsys.readouterr().out

    assert "TASK: keep this line" in out
    assert "...(truncated:" in out
    assert "full file:" in out
    assert len(out) < session_start.ACTIVE_CONTEXT_MAX_CHARS + 4000


def test_short_active_context_is_injected_whole(tmp_path, monkeypatch, capsys):
    body = "# activeContext\n## CURRENT STATE\nTASK: short\n"
    (tmp_path / "activeContext.md").write_text(body, encoding="utf-8")
    _isolate(monkeypatch, tmp_path)

    session_start.main()
    out = capsys.readouterr().out

    assert body.strip() in out
    assert "...(truncated:" not in out
