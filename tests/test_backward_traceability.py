"""Regression tests for the backward-traceability numeric reference checker.

Each defect from the Skill Audit 2.1 №3 (2026-11-01) is pinned by one test. Cases marked
"limit" document what the checker does NOT prove; they are asserted so the limit stays visible.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "extensions" / "backward-traceability"
SCRIPT = SKILL_DIR / "scripts" / "ref_numeric_values.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("ref_numeric_values", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tex(*lines: str) -> str:
    return "\n".join(lines)


# --- consistency of labels (existing behaviour, kept) ---------------------------------


def test_matching_target_and_link_pass(mod):
    r = mod.verify_integrity(_tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.3}"))
    assert r["status"] == "PASS"
    assert r["integrity_ok"] is True


def test_link_value_differs_from_target_fails(mod):
    r = mod.verify_integrity(_tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.4}"))
    assert r["status"] == "FAIL"
    assert r["integrity_ok"] is False


def test_dangling_link_fails(mod):
    r = mod.verify_integrity(_tex(r"\hyperlink{R9}{1.0}"))
    assert r["status"] == "FAIL"
    assert r["unresolved_links"] == ["R9"]


def test_unused_target_still_passes(mod):
    # Unused target is reported, not failed: it is a coverage note, not an integrity break.
    r = mod.verify_integrity(_tex(r"\hypertarget{R1}{45.3}"))
    assert r["status"] == "PASS"
    assert r["unused_targets"] == ["R1"]


def test_limit_wrong_value_with_consistent_labels_passes(mod):
    # LIMIT: the checker compares labels with each other, not the number with the truth.
    r = mod.verify_integrity(_tex(r"\hypertarget{R1}{7.7}", r"\hyperlink{R1}{7.7}"))
    assert r["status"] == "PASS"


# --- P0: absence of evidence is never PASS -------------------------------------------


def test_code_output_not_requested_is_not_checked(mod):
    r = mod.verify_integrity(_tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.3}"), None)
    assert r["code_missing_labels"] == []
    assert r["status"] == "PASS"


def test_empty_code_output_is_inconclusive_not_pass(mod):
    # Audit P0: a missing or empty code-output used to give integrity_ok=true.
    r = mod.verify_integrity(_tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.3}"), "")
    assert r["status"] == "INCONCLUSIVE"
    assert r["integrity_ok"] is False
    assert r["code_missing_labels"] == ["R1"]


def test_code_output_without_the_label_is_inconclusive(mod):
    # Audit P0: a label absent from the executed output used to give PASS.
    r = mod.verify_integrity(
        _tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.3}"), "unrelated output 3"
    )
    assert r["status"] == "INCONCLUSIVE"
    assert r["integrity_ok"] is False


def test_code_output_value_mismatch_is_fail(mod):
    r = mod.verify_integrity(
        _tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.3}"), r"\hypertarget{R1}{99.9}"
    )
    assert r["status"] == "FAIL"
    assert len(r["code_mismatches"]) == 1


def test_code_output_matching_is_pass(mod):
    r = mod.verify_integrity(
        _tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.3}"), r"\hypertarget{R1}{45.3}"
    )
    assert r["status"] == "PASS"


# --- P1: ambiguous or empty input is INVALID_INPUT -----------------------------------


def test_duplicate_target_label_is_invalid_input(mod):
    # Audit P1: the second definition silently overwrote the first.
    r = mod.verify_integrity(
        _tex(r"\hypertarget{R1}{111}", r"\hypertarget{R1}{222}", r"\hyperlink{R1}{222}")
    )
    assert r["status"] == "INVALID_INPUT"
    assert r["duplicate_targets"] == ["R1"]
    assert r["integrity_ok"] is False


def test_empty_link_text_is_invalid_input(mod):
    # Audit P1: an empty reference text used to pass.
    r = mod.verify_integrity(_tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{}"))
    assert r["status"] == "INVALID_INPUT"
    assert r["empty_links"] == ["R1"]


def test_empty_target_text_is_invalid_input(mod):
    r = mod.verify_integrity(_tex(r"\hypertarget{R1}{}", r"\hyperlink{R1}{}"))
    assert r["status"] == "INVALID_INPUT"
    assert r["empty_targets"] == ["R1"]


def test_invalid_input_takes_precedence_over_fail(mod):
    r = mod.verify_integrity(
        _tex(r"\hypertarget{R1}{111}", r"\hypertarget{R1}{222}", r"\hyperlink{R1}{999}")
    )
    assert r["status"] == "INVALID_INPUT"


# --- CLI: a named but missing code-output is an error --------------------------------


def _run_cli(args, tmp_path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )


def test_cli_missing_code_output_exits_2(tmp_path):
    tex = tmp_path / "main.tex"
    tex.write_text(_tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.3}"), encoding="utf-8")
    proc = _run_cli(["--verify", str(tex), "--code-output", "no_such_file.txt"], tmp_path)
    assert proc.returncode == 2
    assert "not found" in proc.stderr


def test_cli_verify_fail_exits_1(tmp_path):
    tex = tmp_path / "main.tex"
    tex.write_text(_tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.4}"), encoding="utf-8")
    proc = _run_cli(["--verify", str(tex)], tmp_path)
    assert proc.returncode == 1
    assert "Integrity: FAIL" in proc.stderr


def test_cli_verify_pass_exits_0(tmp_path):
    tex = tmp_path / "main.tex"
    tex.write_text(_tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{45.3}"), encoding="utf-8")
    proc = _run_cli(["--verify", str(tex)], tmp_path)
    assert proc.returncode == 0
    assert "Integrity: PASS" in proc.stderr


# --- description: Russian, no promise the script does not keep ----------------------


def _frontmatter_description() -> str:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"^description:\s*\"(.*?)\"\s*$", text, re.MULTILINE | re.DOTALL)
    assert match, "description must be a single double-quoted line"
    return match.group(1)


def test_description_is_russian():
    assert re.search(r"[А-Яа-яЁё]", _frontmatter_description())


def test_description_does_not_promise_compile_time_evaluation():
    # Audit: the script has no \num{} evaluator; the old text promised one.
    assert "compile time" not in _frontmatter_description()
    assert "evaluated" not in _frontmatter_description()


# --- audit v2 (2026-11-01): per-link checks, comments, multi-hit lines, two-file workflow ---


def test_wrong_first_link_is_caught_not_hidden_by_the_last_one(mod):
    # Audit P0: only the last link was compared, so a wrong first link passed silently.
    r = mod.verify_integrity(
        _tex(r"\hypertarget{R1}{45.3}", r"\hyperlink{R1}{0.1}", r"\hyperlink{R1}{45.3}")
    )
    assert r["status"] == "FAIL"
    assert [m["link_value"] for m in r["value_mismatches"]] == ["0.1"]


def test_commented_target_creates_no_anchor(mod):
    # Audit P1: \hypertarget inside a LaTeX comment does not create an anchor.
    r = mod.verify_integrity(_tex(r"% \hypertarget{R1}{45.3}", r"Reported: \hyperlink{R1}{45.3}."))
    assert r["status"] == "FAIL"
    assert r["unresolved_links"] == ["R1"]


def test_escaped_percent_is_not_a_comment(mod):
    r = mod.verify_integrity(_tex(r"\hypertarget{R1}{45\%}", r"\hyperlink{R1}{45\%}"))
    assert r["status"] == "PASS"


def test_two_targets_on_one_code_line_are_both_found(mod):
    # Audit P1: re.search kept only the first hypertarget per line; the second went unchecked.
    tex = _tex(
        r"\hypertarget{R1}{45.3}",
        r"\hyperlink{R1}{45.3}",
        r"\hypertarget{R2}{9}",
        r"\hyperlink{R2}{9}",
    )
    r = mod.verify_integrity(tex, r"\hypertarget{R1}{45.3} \hypertarget{R2}{9}")
    assert r["status"] == "PASS"
    assert r["code_missing_labels"] == []


def test_two_file_workflow_link_resolved_by_code_output(mod):
    # Audit P1 / SKILL.md Step 1: the paper links to a tag that lives in the code output.
    r = mod.verify_integrity(_tex(r"\hyperlink{R1}{45.3}"), r"\hypertarget{R1}{45.3}")
    assert r["status"] == "PASS"
    assert r["unresolved_links"] == []


def test_two_file_value_mismatch_is_fail(mod):
    r = mod.verify_integrity(_tex(r"\hyperlink{R1}{45.4}"), r"\hypertarget{R1}{45.3}")
    assert r["status"] == "FAIL"
    assert len(r["code_mismatches"]) == 1


def test_two_file_missing_label_is_unresolved(mod):
    r = mod.verify_integrity(_tex(r"\hyperlink{R9}{1}"), r"\hypertarget{R1}{45.3}")
    assert r["status"] == "FAIL"
    assert r["unresolved_links"] == ["R9"]


def test_wrong_link_with_tag_only_in_code_output_is_not_a_wrong_first_pass(mod):
    # Regression for the per-link rule: a correct second link must not hide a wrong first one.
    r = mod.verify_integrity(
        _tex(r"\hyperlink{R1}{0.1}", r"\hyperlink{R1}{45.3}"), r"\hypertarget{R1}{45.3}"
    )
    assert r["status"] == "FAIL"


def test_skill_does_not_promise_latex_formula_evaluation():
    # Audit v2 P1: pdflatex fails on \num with hyperref+listings; the checker evaluates nothing.
    body = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "compile-time evaluation" not in body
    assert "evaluated at compile time" not in body
    assert "\num{45.3 - 38.7" not in body
