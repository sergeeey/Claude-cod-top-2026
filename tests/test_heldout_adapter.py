"""Held-out adapter: behaviour only, on synthetic registries. No held-out content is used here."""

import json
from pathlib import Path

import pytest
import regression_oracle as oracle


def test_without_a_registry_only_public_tasks_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(oracle.HELDOUT_ENV, raising=False)
    assert oracle.load_heldout() == {}
    assert all(tid.startswith("C") for tid in oracle.TASKS)


def test_registry_entry_selects_its_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "store"
    store.mkdir()
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "SYN": {
                    "fix": "HEAD",
                    "parent": "HEAD",
                    "repo": str(store),
                    "test": "tests/t.py",
                    "sha": "000000000000",
                    "statement": "synthetic",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(oracle.HELDOUT_ENV, str(registry))
    entries = oracle.load_heldout()
    assert set(entries) == {"SYN"}
    assert oracle._repo_for(entries["SYN"]) == store
    assert oracle._repo_for(oracle.TASKS["C1"]) == oracle.REPO


def test_unreadable_registry_is_insufficient_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv(oracle.HELDOUT_ENV, str(tmp_path / "absent.json"))
    monkeypatch.setattr("sys.argv", ["regression_oracle.py", "selfcheck", "C1"])
    with pytest.raises(oracle.OracleError):
        oracle.load_heldout()
    monkeypatch.setattr(oracle, "selfcheck", lambda *a: pytest.fail("must not run"))
    assert oracle.main() == 4


def test_registry_with_wrong_shape_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = tmp_path / "bad.json"
    registry.write_text(json.dumps({"SYN": "not a task"}), encoding="utf-8")
    monkeypatch.setenv(oracle.HELDOUT_ENV, str(registry))
    with pytest.raises(oracle.OracleError):
        oracle.load_heldout()
