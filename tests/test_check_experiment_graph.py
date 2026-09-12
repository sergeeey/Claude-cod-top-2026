"""Tests for scripts/check_experiment_graph.py.

Covers the verification matrix this whole minimal extension was built against:
schema validity, DAG acyclicity, dangling-reference detection, artifact_refs
existence, and sealed_holdout.yaml structural validity (leakage + consumption).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import check_experiment_graph as ceg


def _write_graph(exp_dir: Path, **fields) -> None:
    exp_dir.mkdir(parents=True, exist_ok=True)
    defaults = {
        "id": exp_dir.name,
        "mode": "EXPLORE",
        "status": "ACTIVE",
    }
    defaults.update(fields)
    lines = []
    for k, v in defaults.items():
        if isinstance(v, list):
            inner = ", ".join(f'"{x}"' for x in v)
            lines.append(f"{k}: [{inner}]")
        elif v is None:
            lines.append(f"{k}: null")
        else:
            lines.append(f'{k}: "{v}"')
    (exp_dir / "graph.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestSchemaValidation:
    def test_valid_minimal_graph_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(
            ceg, "GRAPH_SCHEMA_PATH", Path(ceg.ROOT) / "experiments" / "graph.schema.json"
        )
        _write_graph(tmp_path / "20260101-a")
        errors = ceg.validate_schema_for_all(ceg.discover_graph_files())
        assert errors == []

    def test_invalid_mode_enum_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "20260101-a", mode="NOT_A_REAL_MODE")
        errors = ceg.validate_schema_for_all(ceg.discover_graph_files())
        assert any("not in allowed" in e for e in errors)

    def test_missing_required_field_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        exp_dir = tmp_path / "20260101-a"
        exp_dir.mkdir(parents=True)
        (exp_dir / "graph.yaml").write_text(
            'id: "20260101-a"\n', encoding="utf-8"
        )  # no mode/status
        errors = ceg.validate_schema_for_all(ceg.discover_graph_files())
        assert any("missing required key" in e for e in errors)


class TestAcyclicity:
    def test_no_cycle_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "20260101-a", requires=["20260101-b"])
        _write_graph(tmp_path / "20260101-b")
        errors = ceg.check_acyclic(ceg.discover_graph_files())
        assert errors == []

    def test_direct_cycle_detected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "20260101-a", requires=["20260101-b"])
        _write_graph(tmp_path / "20260101-b", requires=["20260101-a"])
        errors = ceg.check_acyclic(ceg.discover_graph_files())
        assert len(errors) == 1
        assert "cycle" in errors[0]

    def test_blocks_edge_reversed_correctly(self, tmp_path, monkeypatch):
        """A 'blocks' B means B depends on A -- a blocks/requires pair pointing
        the same real direction must NOT be flagged as a cycle."""
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "20260101-a", blocks=["20260101-b"])
        _write_graph(tmp_path / "20260101-b")
        errors = ceg.check_acyclic(ceg.discover_graph_files())
        assert errors == []

    def test_three_node_cycle_detected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "20260101-a", requires=["20260101-b"])
        _write_graph(tmp_path / "20260101-b", requires=["20260101-c"])
        _write_graph(tmp_path / "20260101-c", requires=["20260101-a"])
        errors = ceg.check_acyclic(ceg.discover_graph_files())
        assert len(errors) == 1


class TestDanglingReferences:
    def test_real_target_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(ceg, "ROOT", tmp_path)
        _write_graph(tmp_path / "20260101-a", requires=["20260101-b"])
        _write_graph(tmp_path / "20260101-b")
        errors = ceg.check_dangling_references(ceg.discover_graph_files())
        assert errors == []

    def test_dangling_requires_detected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(ceg, "ROOT", tmp_path)
        _write_graph(tmp_path / "20260101-a", requires=["20260101-does-not-exist"])
        errors = ceg.check_dangling_references(ceg.discover_graph_files())
        assert any("does-not-exist" in e for e in errors)

    def test_evidence_against_resolves_to_null_results(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(ceg, "ROOT", tmp_path)
        (tmp_path / "null_results").mkdir()
        (tmp_path / "null_results" / "20260101-b.md").write_text("x", encoding="utf-8")
        _write_graph(tmp_path / "20260101-a", evidence_against=["20260101-b"])
        errors = ceg.check_dangling_references(ceg.discover_graph_files())
        assert errors == []

    def test_dangling_evidence_against_detected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(ceg, "ROOT", tmp_path)
        _write_graph(tmp_path / "20260101-a", evidence_against=["nothing-like-this-exists"])
        errors = ceg.check_dangling_references(ceg.discover_graph_files())
        assert any("nothing-like-this-exists" in e for e in errors)

    def test_artifact_refs_existence_checked(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(ceg, "ROOT", tmp_path)
        exp_dir = tmp_path / "20260101-a"
        _write_graph(exp_dir, artifact_refs=["missing_file.md"])
        errors = ceg.check_dangling_references(ceg.discover_graph_files())
        assert any("missing_file.md" in e for e in errors)

    def test_artifact_refs_existing_file_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(ceg, "ROOT", tmp_path)
        exp_dir = tmp_path / "20260101-a"
        _write_graph(exp_dir, artifact_refs=["real_file.md"])
        (exp_dir / "real_file.md").write_text("x", encoding="utf-8")
        errors = ceg.check_dangling_references(ceg.discover_graph_files())
        assert errors == []

    def test_id_mismatch_with_folder_name_detected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(ceg, "ROOT", tmp_path)
        _write_graph(tmp_path / "20260101-a", id="20260101-WRONG")
        errors = ceg.check_dangling_references(ceg.discover_graph_files())
        assert any("does not match" in e for e in errors)

    def test_artifact_refs_absolute_path_rejected(self, tmp_path, monkeypatch):
        """Regression (sec-auditor-found, 2026-09-12): (exp_dir / artifact)
        silently escapes exp_dir for an absolute path -- must be rejected
        before the existence check, not resolved as-is."""
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(ceg, "ROOT", tmp_path)
        exp_dir = tmp_path / "20260101-a"
        exp_dir.mkdir(parents=True)
        outside = tmp_path / "outside.md"
        outside.write_text("x", encoding="utf-8")
        # WHY as_posix(): a raw Windows backslash path inside a double-quoted
        # YAML scalar (see _write_graph) would be misparsed as escape
        # sequences -- forward slashes are still an absolute path on Windows
        # and side-step that unrelated YAML-quoting issue.
        _write_graph(exp_dir, artifact_refs=[outside.as_posix()])
        errors = ceg.check_dangling_references(ceg.discover_graph_files())
        assert any("is an absolute path" in e for e in errors)

    def test_artifact_refs_traversal_escape_rejected(self, tmp_path, monkeypatch):
        """Regression (sec-auditor-found, 2026-09-12): a '../../..'-style
        relative escape resolves outside exp_dir and must be rejected by
        the resolved-path containment check, not treated as a normal
        missing/existing file."""
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(ceg, "ROOT", tmp_path)
        exp_dir = tmp_path / "20260101-a"
        exp_dir.mkdir(parents=True)
        outside = tmp_path / "outside.md"
        outside.write_text("x", encoding="utf-8")
        _write_graph(exp_dir, artifact_refs=["../outside.md"])
        errors = ceg.check_dangling_references(ceg.discover_graph_files())
        assert any("resolves outside this experiment" in e for e in errors)


class TestSealedHoldoutValidation:
    def _write_holdout(self, exp_dir: Path, content: str) -> None:
        exp_dir.mkdir(parents=True, exist_ok=True)
        (exp_dir / "sealed_holdout.yaml").write_text(content, encoding="utf-8")

    def test_valid_holdout_passes(self, tmp_path):
        self._write_holdout(
            tmp_path / "20260101-a",
            'holdout_ref: "sha256:abcd1234"\nconsumed: false\nopened_at: null\n',
        )
        errors = ceg.check_sealed_holdouts([tmp_path / "20260101-a" / "sealed_holdout.yaml"])
        assert errors == []

    def test_inlined_data_rejected(self, tmp_path):
        long_blob = "x" * 500
        self._write_holdout(
            tmp_path / "20260101-a",
            f'holdout_ref: "{long_blob}"\nconsumed: false\nopened_at: null\n',
        )
        errors = ceg.check_sealed_holdouts([tmp_path / "20260101-a" / "sealed_holdout.yaml"])
        assert any("looks like inlined data" in e for e in errors)

    def test_consumed_without_opened_at_rejected(self, tmp_path):
        self._write_holdout(
            tmp_path / "20260101-a",
            'holdout_ref: "sha256:abcd"\nconsumed: true\nopened_at: null\n',
        )
        errors = ceg.check_sealed_holdouts([tmp_path / "20260101-a" / "sealed_holdout.yaml"])
        assert any("structurally invalid consumption" in e for e in errors)

    def test_consumed_with_opened_at_passes(self, tmp_path):
        self._write_holdout(
            tmp_path / "20260101-a",
            'holdout_ref: "sha256:abcd"\nconsumed: true\nopened_at: "2026-09-13"\n',
        )
        errors = ceg.check_sealed_holdouts([tmp_path / "20260101-a" / "sealed_holdout.yaml"])
        assert errors == []

    def test_space_containing_ref_rejected_by_shape_even_under_length_cap(self, tmp_path):
        """Regression (sec-auditor-found, 2026-09-12): the length ceiling
        alone cannot tell a real hash/path from a same-length blob with
        embedded whitespace -- _HOLDOUT_REF_SHAPE_RE's positive shape check
        is what actually rejects this, independent of _MAX_HOLDOUT_REF_LEN."""
        self._write_holdout(
            tmp_path / "20260101-a",
            'holdout_ref: "not a real reference at all"\nconsumed: false\nopened_at: null\n',
        )
        errors = ceg.check_sealed_holdouts([tmp_path / "20260101-a" / "sealed_holdout.yaml"])
        assert any("does not look like a reference" in e for e in errors)


class TestDiscoverExcludesTemplate:
    def test_template_dir_excluded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "_template")
        assert ceg.discover_graph_files() == []


class TestRunAllAgainstRealRepo:
    """The historical-replay entries this PR adds must themselves validate
    cleanly against the real, installed check -- not a synthetic fixture."""

    def test_real_repo_graph_files_are_clean(self):
        errors, n_graphs, n_holdouts = ceg.run_all()
        assert errors == []
        assert n_graphs >= 2  # the two historical-replay entries this PR adds
