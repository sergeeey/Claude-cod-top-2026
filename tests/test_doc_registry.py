"""Tests for hooks/doc_registry.py — document dedup registry.

WHY: no prior test coverage existed for this module at all. Added while
closing a cross-model audit finding: register()/annotate() did a
load-mutate-save sequence with no locking, so concurrent registrations
could silently lose each other's updates (last-writer-wins on the whole
registry, not just the touched key).
"""

import hashlib
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import doc_registry  # noqa: E402


def _make_file(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestRegisterAndAnnotate:
    def test_register_creates_entry(self, tmp_path, monkeypatch):
        registry_path = tmp_path / "doc_registry.json"
        monkeypatch.setattr(doc_registry, "REGISTRY_PATH", registry_path)
        monkeypatch.setattr(doc_registry, "_LOCK_PATH", registry_path.with_suffix(".lock"))

        f = _make_file(tmp_path, "paper.pdf", "content-a")
        entry = doc_registry.register(str(f), parsed_summary="summary")

        assert entry["parsed_summary"] == "summary"
        assert doc_registry.lookup(str(f))["sha256"] == entry["sha256"]

    def test_annotate_updates_existing_entry(self, tmp_path, monkeypatch):
        registry_path = tmp_path / "doc_registry.json"
        monkeypatch.setattr(doc_registry, "REGISTRY_PATH", registry_path)
        monkeypatch.setattr(doc_registry, "_LOCK_PATH", registry_path.with_suffix(".lock"))

        f = _make_file(tmp_path, "paper.pdf", "content-a")
        doc_registry.register(str(f))
        result = doc_registry.annotate(str(f), wiki_path="wiki/paper.md")

        assert result["wiki_path"] == "wiki/paper.md"
        assert result["analyzed"] is True

    def test_annotate_unregistered_file_returns_none(self, tmp_path, monkeypatch):
        registry_path = tmp_path / "doc_registry.json"
        monkeypatch.setattr(doc_registry, "REGISTRY_PATH", registry_path)
        monkeypatch.setattr(doc_registry, "_LOCK_PATH", registry_path.with_suffix(".lock"))

        f = _make_file(tmp_path, "paper.pdf", "content-a")
        assert doc_registry.annotate(str(f), wiki_path="x") is None


class TestConcurrentRegistrationsDoNotLoseUpdates:
    """Regression (MEDIUM, cross-model audit): concurrent register() calls
    for DIFFERENT files previously raced on the same load-mutate-save
    sequence -- both could load the registry before either saved, and the
    later save would silently overwrite the earlier one's new entry."""

    def test_twenty_concurrent_registrations_all_persisted(self, tmp_path, monkeypatch):
        registry_path = tmp_path / "doc_registry.json"
        monkeypatch.setattr(doc_registry, "REGISTRY_PATH", registry_path)
        monkeypatch.setattr(doc_registry, "_LOCK_PATH", registry_path.with_suffix(".lock"))

        files = [_make_file(tmp_path, f"doc_{i}.txt", f"unique-content-{i}") for i in range(20)]

        def register_one(f: Path) -> None:
            doc_registry.register(str(f), parsed_summary=f"summary-{f.name}")

        threads = [threading.Thread(target=register_one, args=(f,)) for f in files]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = doc_registry._load()
        # WHY exactly 20, not "at least 1": without the lock, concurrent
        # threads racing on the same read-modify-write would very likely
        # undercount here -- this is the actual failure mode the fix closes.
        assert len(final) == 20
        for f in files:
            sha = hashlib.sha256(f.read_bytes()).hexdigest()
            assert sha in final
            assert final[sha]["parsed_summary"] == f"summary-{f.name}"

    def test_concurrent_reads_during_writes_do_not_raise(self, tmp_path, monkeypatch):
        """Regression (found by a real failure in the sibling
        expert_registry.py under this exact test shape): lookup()/list_all()
        call _load() WITHOUT the lock by design (read-only callers shouldn't
        serialize behind every write). On Windows, an unlocked read can hit
        a transient PermissionError if it lands mid os.replace() from a
        concurrent locked write. _save()'s retry-on-PermissionError must
        close this without either side raising."""
        registry_path = tmp_path / "doc_registry.json"
        monkeypatch.setattr(doc_registry, "REGISTRY_PATH", registry_path)
        monkeypatch.setattr(doc_registry, "_LOCK_PATH", registry_path.with_suffix(".lock"))

        files = [_make_file(tmp_path, f"doc_{i}.txt", f"unique-content-{i}") for i in range(15)]
        errors: list[BaseException] = []

        def register_one(f: Path) -> None:
            try:
                doc_registry.register(str(f), parsed_summary=f"summary-{f.name}")
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def read_loop() -> None:
            for _ in range(50):
                try:
                    doc_registry.list_all()
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

        threads = [threading.Thread(target=register_one, args=(f,)) for f in files]
        threads += [threading.Thread(target=read_loop) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(doc_registry._load()) == 15
