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


class TestStatusConditionalFields:
    """Regression (Codex P2 finding, 2026-09-12): graph.schema.json's own
    field descriptions document kill_reason as required once status=KILLED
    and revival_condition as required once status is KILLED or BLOCKED --
    but the schema's type allows null (correctly, since these are legitimately
    null for ACTIVE/PROMOTED/VERIFIED experiments) and the stdlib-only schema
    validator has no if/then/else support to express that conditional. Without
    a dedicated check, a KILLED experiment with kill_reason: null passed
    validation cleanly."""

    def test_killed_without_kill_reason_flagged(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(
            tmp_path / "20260101-a", status="KILLED", kill_reason=None, revival_condition="x"
        )
        errors = ceg.check_status_conditional_fields(ceg.discover_graph_files())
        assert any("kill_reason" in e for e in errors)

    def test_killed_without_revival_condition_is_NOT_flagged(self, tmp_path, monkeypatch):
        """THE MANDATORY REGRESSION CASE for PR C — this assertion is INVERTED from
        what it was, deliberately.

        The Rescue Review rules say a `killed` formulation's path forward is a NEW
        branch via the Minimal Relaxation Rule, and a `hard_killed` one can only change
        on new theorem-level input. Neither has a meaningful "revival condition". Both
        crosswalk to KILLED.

        Two real records in this repository are of exactly this shape —
        `20260824-elai-hooks-skeptic-pilot` and
        `20260824-permission-policy-skeptic-pilot`, both "claim falsified AND the
        underlying defect fixed", both carrying substantial Kill Analysis and having
        nothing to revive. The earlier version of this check demanded a revival
        condition from them, which could only be satisfied by inventing a fictitious
        resurrection trigger. A fix that makes a checker green by forcing meaningless
        text into real records is worse than the gap it closes.
        """
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(
            tmp_path / "20260101-a",
            status="KILLED",
            kill_reason="claim falsified as worded; the underlying defect was then fixed",
            revival_condition=None,
        )
        errors = ceg.check_status_conditional_fields(ceg.discover_graph_files())
        assert errors == [], (
            "a KILLED record with a real kill_reason and no revival_condition is "
            f"well-formed per the Rescue Review rules, but got: {errors}"
        )

    def test_killed_still_requires_kill_reason(self, tmp_path, monkeypatch):
        """Relaxing the revival_condition demand must NOT relax the kill_reason one.
        Guards against 'fixing' the false positive by gutting the check entirely."""
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(
            tmp_path / "20260101-a", status="KILLED", kill_reason=None, revival_condition=None
        )
        errors = ceg.check_status_conditional_fields(ceg.discover_graph_files())
        assert any("kill_reason" in e for e in errors)

    def test_blocked_without_revival_condition_flagged(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "20260101-a", status="BLOCKED", revival_condition=None)
        errors = ceg.check_status_conditional_fields(ceg.discover_graph_files())
        assert any("revival_condition" in e for e in errors)

    def test_killed_with_both_fields_passes(self, tmp_path, monkeypatch):
        """A KILLED record MAY still carry a revival_condition — it is optional, not
        forbidden. Some killed formulations do have a meaningful trigger."""
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(
            tmp_path / "20260101-a",
            status="KILLED",
            kill_reason="core predicate falsified",
            revival_condition="fix X, retry with n>=10",
        )
        errors = ceg.check_status_conditional_fields(ceg.discover_graph_files())
        assert errors == []

    def test_the_two_real_falsified_then_fixed_records_are_not_flagged(self, tmp_path, monkeypatch):
        """The regression case stated against the ACTUAL corpus shape, not a synthetic
        one: a record whose kill_reason describes a claim retired after its defect was
        fixed, with no revival condition, must pass.

        Fixture text is paraphrased from `20260824-permission-policy-skeptic-pilot`'s
        own Kill Analysis so that a future reader can see which real artifact this
        protects.
        """
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(
            tmp_path / "20260824-permission-policy-like",
            status="KILLED",
            kill_reason=(
                "the original claim (no auto-allow bypass exists) -- false, two distinct "
                "bypass classes found, independently reproduced, and then closed"
            ),
            revival_condition=None,
            next_required_test=None,
        )
        assert ceg.check_status_conditional_fields(ceg.discover_graph_files()) == []

    def test_active_without_either_field_passes(self, tmp_path, monkeypatch):
        """The conditional only fires for KILLED/BLOCKED -- an ACTIVE
        experiment with both fields null (the normal, unremarkable case)
        must not be flagged."""
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "20260101-a", status="ACTIVE")
        errors = ceg.check_status_conditional_fields(ceg.discover_graph_files())
        assert errors == []


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


class TestIndexIntegrity:
    """The invariant: an experiment that exists must be discoverable.

    Same invariant CI's own "Registry <-> disk consistency gate" already enforces for
    skills, extended to experiments. Measured need (PR #446 + PR D): five experiment
    directories had no INDEX.md row, including BOTH cycles that were themselves working
    on experiment tracking -- so the "grep INDEX.md before starting work" protocol could
    not see them.
    """

    def _setup(self, tmp_path, monkeypatch, index_body: str, dirs: list[str]):
        exp = tmp_path / "experiments"
        exp.mkdir()
        for d in dirs:
            (exp / d).mkdir()
        (exp / "INDEX.md").write_text(index_body, encoding="utf-8")
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", exp)
        monkeypatch.setattr(ceg, "INDEX_PATH", exp / "INDEX.md")

    _HEADER = "# Experiments Index\n\n| ID | Date | Claim (slug) | Tier | Verdict |\n|---|---|---|---|---|\n"

    def test_orphan_detected(self, tmp_path, monkeypatch):
        self._setup(
            tmp_path,
            monkeypatch,
            self._HEADER + "| 20260101-a | 2026-01-01 | claim | Full | PROMOTE |\n",
            ["20260101-a", "20260101-b"],
        )
        errors = ceg.check_index_integrity()
        assert any("orphan experiment" in e and "20260101-b" in e for e in errors)
        assert not any("20260101-a" in e for e in errors)

    def test_stale_entry_detected(self, tmp_path, monkeypatch):
        self._setup(
            tmp_path,
            monkeypatch,
            self._HEADER
            + "| 20260101-a | 2026-01-01 | claim | Full | PROMOTE |\n"
            + "| 20260101-gone | 2026-01-01 | claim | Full | REJECT |\n",
            ["20260101-a"],
        )
        errors = ceg.check_index_integrity()
        assert any("stale index entry" in e and "20260101-gone" in e for e in errors)

    def test_duplicate_row_detected(self, tmp_path, monkeypatch):
        self._setup(
            tmp_path,
            monkeypatch,
            self._HEADER
            + "| 20260101-a | 2026-01-01 | claim | Full | PROMOTE |\n"
            + "| 20260101-a | 2026-01-01 | claim again | Full | PROMOTE |\n",
            ["20260101-a"],
        )
        errors = ceg.check_index_integrity()
        assert any("duplicate index entry" in e for e in errors)

    def test_template_is_not_an_orphan(self, tmp_path, monkeypatch):
        """`_template` is scaffolding, not an experiment. It must never be demanded
        as an index row, and the index's own convenience `_template` row must never be
        read as naming an experiment."""
        self._setup(
            tmp_path,
            monkeypatch,
            self._HEADER
            + "| 20260101-a | 2026-01-01 | claim | Full | PROMOTE |\n"
            + "| _template | — | template files | — | — |\n",
            ["20260101-a", "_template"],
        )
        assert ceg.check_index_integrity() == []

    def test_clean_repo_passes(self, tmp_path, monkeypatch):
        self._setup(
            tmp_path,
            monkeypatch,
            self._HEADER + "| 20260101-a | 2026-01-01 | claim | Full | PROMOTE |\n",
            ["20260101-a"],
        )
        assert ceg.check_index_integrity() == []

    def test_missing_index_is_an_error_not_a_pass(self, tmp_path, monkeypatch):
        """A missing index must fail loudly. Treating 'no index' as 'nothing to check'
        is the same silence-reads-as-approval failure this whole cycle keeps finding."""
        exp = tmp_path / "experiments"
        exp.mkdir()
        (exp / "20260101-a").mkdir()
        monkeypatch.setattr(ceg, "EXPERIMENTS_DIR", exp)
        monkeypatch.setattr(ceg, "INDEX_PATH", exp / "INDEX.md")
        errors = ceg.check_index_integrity()
        assert errors and "missing" in errors[0]

    def test_real_repository_satisfies_the_invariant(self):
        """Runs against the actual repository, not a fixture -- this is the assertion
        that would have caught all five real orphans."""
        assert ceg.check_index_integrity() == []


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
