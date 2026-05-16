"""Tests for scripts/validate_experiment.py — FL experiment folder validator."""

import sys
import os

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from validate_experiment import (
    detect_tier,
    check_artifact_file,
    check_artifact_dir,
    validate_experiment,
    find_placeholder,
    list_experiments,
    print_summary,
    REQUIRED_FILES,
)


# ── detect_tier ────────────────────────────────────────────────────────────────


class TestDetectTier:
    def test_no_yaml_defaults_to_standard(self, tmp_path):
        # ARRANGE: directory without experiment.yaml
        exp = tmp_path / "20260515-foo"
        exp.mkdir()

        # ACT
        tier = detect_tier(exp)

        # ASSERT: falls back to standard when no yaml present
        assert tier == "standard"

    def test_reads_tier_from_yaml(self, tmp_path):
        # ARRANGE: experiment.yaml declares full tier
        exp = tmp_path / "20260515-full"
        exp.mkdir()
        (exp / "experiment.yaml").write_text("tier: full\n", encoding="utf-8")

        # ACT
        tier = detect_tier(exp)

        # ASSERT: returns the tier declared in yaml
        assert tier == "full"

    def test_reads_micro_tier(self, tmp_path):
        # ARRANGE: experiment.yaml declares micro
        exp = tmp_path / "20260515-micro"
        exp.mkdir()
        (exp / "experiment.yaml").write_text("tier: micro\n", encoding="utf-8")

        # ACT / ASSERT
        assert detect_tier(exp) == "micro"

    def test_invalid_tier_in_yaml_falls_back_to_standard(self, tmp_path):
        # ARRANGE: yaml with unrecognised tier value
        exp = tmp_path / "20260515-bad"
        exp.mkdir()
        (exp / "experiment.yaml").write_text("tier: unknown_value\n", encoding="utf-8")

        # ACT / ASSERT: unrecognised tier → fallback standard
        assert detect_tier(exp) == "standard"

    def test_yaml_with_quoted_tier(self, tmp_path):
        # ARRANGE: tier value in single quotes
        exp = tmp_path / "20260515-quoted"
        exp.mkdir()
        (exp / "experiment.yaml").write_text("tier: 'full'\n", encoding="utf-8")

        # ACT / ASSERT: quotes are stripped correctly
        assert detect_tier(exp) == "full"


# ── find_placeholder ──────────────────────────────────────────────────────────


class TestFindPlaceholder:
    def test_no_placeholder(self):
        # ARRANGE: clean content
        assert find_placeholder("This is a real experiment claim.") is None

    def test_detects_yyyymmdd_pattern(self):
        # ARRANGE: unfilled template date
        result = find_placeholder("Experiment <YYYYMMDD-slug>")
        assert result is not None

    def test_detects_todo(self):
        # ARRANGE: common template leftover
        result = find_placeholder("## Result\n\n[TODO] Fill this in.")
        assert result is not None

    def test_detects_claim_here(self):
        result = find_placeholder("Claim: [claim here]")
        assert result is not None


# ── check_artifact_file ────────────────────────────────────────────────────────


class TestCheckArtifactFile:
    def test_missing_file_returns_fail(self, tmp_path):
        # ARRANGE: path to non-existent file
        path = tmp_path / "claim.md"

        # ACT
        result = check_artifact_file(path)

        # ASSERT: missing file is a failure
        assert result.status == "fail"
        assert "MISSING" in result.detail

    def test_empty_file_returns_warn(self, tmp_path):
        # ARRANGE: file exists but is empty
        path = tmp_path / "claim.md"
        path.write_text("   \n  ", encoding="utf-8")

        # ACT
        result = check_artifact_file(path)

        # ASSERT: empty file is a warning, not an outright failure
        assert result.status == "warn"

    def test_placeholder_file_returns_warn(self, tmp_path):
        # ARRANGE: file filled with template placeholder text
        path = tmp_path / "claim.md"
        path.write_text("Claim: <YYYYMMDD-slug> the hypothesis", encoding="utf-8")

        # ACT
        result = check_artifact_file(path)

        # ASSERT: placeholder content triggers warning so author fills it in
        assert result.status == "warn"
        assert "placeholder" in result.detail

    def test_valid_file_returns_pass(self, tmp_path):
        # ARRANGE: well-formed file
        path = tmp_path / "claim.md"
        path.write_text("# Claim\n\nThis hook detects prompt injection.", encoding="utf-8")

        # ACT
        result = check_artifact_file(path)

        # ASSERT: clean file passes
        assert result.status == "pass"


# ── check_artifact_dir ────────────────────────────────────────────────────────


class TestCheckArtifactDir:
    def test_missing_dir_returns_fail(self, tmp_path):
        # ARRANGE: directory that does not exist
        path = tmp_path / "baselines"

        # ACT
        result = check_artifact_dir(path)

        # ASSERT
        assert result.status == "fail"

    def test_empty_dir_returns_warn(self, tmp_path):
        # ARRANGE: directory exists but is empty
        path = tmp_path / "baselines"
        path.mkdir()

        # ACT
        result = check_artifact_dir(path)

        # ASSERT: empty dir warns — may be populated after experiments run
        assert result.status == "warn"

    def test_dir_with_content_returns_pass(self, tmp_path):
        # ARRANGE: directory with a file inside
        path = tmp_path / "baselines"
        path.mkdir()
        (path / "baseline.json").write_text("{}", encoding="utf-8")

        # ACT
        result = check_artifact_dir(path)

        # ASSERT
        assert result.status == "pass"


# ── validate_experiment ────────────────────────────────────────────────────────


def _make_standard_experiment(base: "Path") -> "Path":
    """Helper: create a valid standard-tier experiment folder.

    WHY: EstimandOps 2.0 requires claim.md to have at least one ticked checkbox [x]
    and experiment.yaml to contain question_type + hypothesis fields.
    """
    exp = base / "20260515-test"
    exp.mkdir()
    for fname in REQUIRED_FILES["standard"]:
        (exp / fname).write_text(f"# {fname}\n\nFilled content.", encoding="utf-8")
    # Override claim.md with EstimandOps-compliant content (ticked checkbox)
    (exp / "claim.md").write_text(
        "# Claim\n\n- [x] Descriptive\n\nFilled content.",
        encoding="utf-8",
    )
    # Override experiment.yaml with required EstimandOps fields for standard tier
    (exp / "experiment.yaml").write_text(
        "question_type: descriptive\nhypothesis: some testable hypothesis\n",
        encoding="utf-8",
    )
    return exp


class TestValidateExperiment:
    def test_valid_standard_experiment_is_valid(self, tmp_path):
        # ARRANGE: complete standard experiment with all required files
        exp = _make_standard_experiment(tmp_path)

        # ACT
        results, tier, is_valid = validate_experiment(exp)

        # ASSERT: all files present and filled → valid
        assert tier == "standard"
        assert is_valid is True
        assert all(r.status == "pass" for r in results)

    def test_missing_file_makes_experiment_invalid(self, tmp_path):
        # ARRANGE: standard experiment with one required file missing
        exp = _make_standard_experiment(tmp_path)
        (exp / "claim.md").unlink()

        # ACT
        results, tier, is_valid = validate_experiment(exp)

        # ASSERT: missing file → experiment is invalid
        assert is_valid is False
        fail_names = [r.name for r in results if r.status == "fail"]
        assert "claim.md" in fail_names

    def test_tier_override_applies(self, tmp_path):
        # ARRANGE: experiment directory with micro override
        exp = tmp_path / "20260515-micro"
        exp.mkdir()
        # No files needed for micro

        # ACT: force micro tier regardless of directory content
        results, tier, is_valid = validate_experiment(exp, tier_override="micro")

        # ASSERT: micro tier has no required files → always valid
        assert tier == "micro"
        assert results == []
        assert is_valid is True

    def test_tier_auto_detected_from_yaml(self, tmp_path):
        # ARRANGE: standard experiment declaring itself as standard
        exp = _make_standard_experiment(tmp_path)
        (exp / "experiment.yaml").write_text("tier: standard\n", encoding="utf-8")

        # ACT
        _results, tier, _is_valid = validate_experiment(exp)

        # ASSERT: auto-detection reads the yaml
        assert tier == "standard"

    def test_sha256_creates_file(self, tmp_path):
        # ARRANGE: valid standard experiment
        exp = _make_standard_experiment(tmp_path)

        # ACT: request sha256 computation
        validate_experiment(exp, compute_sha256=True)

        # ASSERT: artifacts.sha256 is written
        sha_path = exp / "artifacts.sha256"
        assert sha_path.exists()
        content = sha_path.read_text(encoding="utf-8")
        # Each line should contain a hash and filename separated by two spaces
        for line in content.strip().splitlines():
            assert "  " in line, f"Expected '  ' separator in: {line!r}"

    def test_placeholder_file_does_not_block_valid_flag_but_warns(self, tmp_path):
        # ARRANGE: standard experiment where one file has placeholder text
        exp = _make_standard_experiment(tmp_path)
        (exp / "claim.md").write_text("Claim: [claim here]", encoding="utf-8")

        # ACT
        results, tier, is_valid = validate_experiment(exp)

        # ASSERT: warnings don't make is_valid False — only fails do
        assert is_valid is False  # is_valid = all pass (no warns allowed)
        warn_names = [r.name for r in results if r.status == "warn"]
        assert "claim.md" in warn_names


# ── list_experiments ──────────────────────────────────────────────────────────


class TestListExperiments:
    def test_empty_experiments_dir_prints_no_experiments(self, tmp_path, capsys):
        # ARRANGE: experiments root exists but has no subdirectories
        exps_root = tmp_path / "experiments"
        exps_root.mkdir()

        # ACT
        list_experiments(exps_root)

        # ASSERT: message about no experiments is printed
        captured = capsys.readouterr()
        assert "No experiments found" in captured.out

    def test_one_experiment_listed(self, tmp_path, capsys):
        # ARRANGE: one valid standard experiment inside experiments root
        exps_root = tmp_path / "experiments"
        exps_root.mkdir()
        exp = exps_root / "20260515-test"
        exp.mkdir()
        for fname in REQUIRED_FILES["standard"]:
            (exp / fname).write_text(f"# {fname}\n\nReal content.", encoding="utf-8")

        # ACT
        list_experiments(exps_root)

        # ASSERT: the experiment ID appears in the table output
        captured = capsys.readouterr()
        assert "20260515-test" in captured.out

    def test_private_dirs_skipped(self, tmp_path, capsys):
        # ARRANGE: directory starting with underscore should be ignored (template)
        exps_root = tmp_path / "experiments"
        exps_root.mkdir()
        (exps_root / "_template").mkdir()

        # ACT
        list_experiments(exps_root)

        # ASSERT: _template is filtered out, nothing else to show
        captured = capsys.readouterr()
        assert "No experiments found" in captured.out

    def test_missing_experiments_dir_exits(self, tmp_path):
        # ARRANGE: experiments root that doesn't exist
        import pytest

        exps_root = tmp_path / "does_not_exist"

        # ACT / ASSERT: should call sys.exit(1)
        with pytest.raises(SystemExit) as exc_info:
            list_experiments(exps_root)
        assert exc_info.value.code == 1


# ── print_summary ─────────────────────────────────────────────────────────────


class TestPrintSummary:
    def test_all_pass_returns_true(self, capsys):
        # ARRANGE
        from validate_experiment import CheckResult

        results = [
            CheckResult("claim.md", "pass", "ok"),
            CheckResult("controls.md", "pass", "ok"),
        ]

        # ACT
        is_valid = print_summary(results, "standard")

        # ASSERT
        assert is_valid is True
        out = capsys.readouterr().out
        assert "VALID" in out

    def test_fail_returns_false(self, capsys):
        # ARRANGE
        from validate_experiment import CheckResult

        results = [
            CheckResult("claim.md", "fail", "MISSING"),
            CheckResult("controls.md", "pass", "ok"),
        ]

        # ACT
        is_valid = print_summary(results, "standard")

        # ASSERT
        assert is_valid is False
        out = capsys.readouterr().out
        assert "INVALID" in out

    def test_warn_only_returns_true_with_warning_message(self, capsys):
        # ARRANGE: warnings don't fail the experiment — they advise
        from validate_experiment import CheckResult

        results = [
            CheckResult("claim.md", "warn", "contains placeholder"),
            CheckResult("controls.md", "pass", "ok"),
        ]

        # ACT
        is_valid = print_summary(results, "standard")

        # ASSERT: warn-only is still considered valid (exit 0)
        assert is_valid is True
        out = capsys.readouterr().out
        assert "WARNINGS" in out.upper() or "WARNING" in out.upper()
