"""build_research_catalog: derived catalog of experiments across worktrees and branches.

Reproducer for the defect: a finished experiment committed only on an unmerged branch (or
untracked in a worktree) was in no index, so a fresh agent proposed redoing it from scratch.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_research_catalog as brc  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _exp(base: Path, name: str, body: str = "# decision\n- [x] REPEAT\n") -> Path:
    d = base / "experiments" / name
    d.mkdir(parents=True)
    (d / "decision.md").write_text(body, encoding="utf-8")
    (d / "claim.md").write_text(f"# claim for {name}\nWe compare routers.\n", encoding="utf-8")
    return d


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "init")
    return repo


def _by_id(catalog: list[dict]) -> dict[str, dict]:
    return {r["research_id"]: r for r in catalog}


def test_state_merged_branch_and_orphan(tmp_path):
    repo = _repo(tmp_path)
    _exp(repo, "20260101-merged", "# d\n- [x] PROMOTE\n")
    _git(repo, "add", "experiments")
    _git(repo, "commit", "-qm", "merged exp")
    _git(repo, "checkout", "-qb", "feat")
    _exp(repo, "20260102-onbranch", "# d\n- [x] REJECT\n")
    _git(repo, "add", "experiments")
    _git(repo, "commit", "-qm", "branch exp")
    _exp(repo, "20260103-orphan")
    cat = _by_id(brc.build([repo]))
    assert cat["20260101-merged"]["state"] == "MERGED_DEFAULT"
    assert cat["20260101-merged"]["verdict"] == "PROMOTE"
    assert cat["20260102-onbranch"]["state"] == "COMMITTED_BRANCH"
    assert cat["20260102-onbranch"]["verdict"] == "REJECT"
    assert cat["20260103-orphan"]["state"] == "UNCOMMITTED_ORPHAN"


def test_experiment_only_on_an_unchecked_out_branch_is_found(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-qb", "side")
    _exp(repo, "20260104-hidden", "# Router study\n- [x] REPEAT\n")
    _git(repo, "add", "experiments")
    _git(repo, "commit", "-qm", "exp")
    _git(repo, "checkout", "-q", "main")  # the folder is no longer on disk
    cat = _by_id(brc.build([repo]))
    rec = cat["20260104-hidden"]
    assert rec["state"] == "COMMITTED_BRANCH"
    assert rec["verdict"] == "REPEAT"
    assert rec["canonical_path"].startswith("git:side:")


def test_worktree_orphan_is_found_with_its_location(tmp_path):
    repo = _repo(tmp_path)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "side", str(wt))
    _exp(wt, "20260105-in-worktree")
    cat = _by_id(brc.build([repo, wt]))
    rec = cat["20260105-in-worktree"]
    assert rec["state"] == "UNCOMMITTED_ORPHAN"
    assert "wt" in rec["canonical_path"]


def test_same_folder_in_two_places_is_one_object_best_state_wins(tmp_path):
    repo = _repo(tmp_path)
    _exp(repo, "20260106-twice")
    _git(repo, "add", "experiments")
    _git(repo, "commit", "-qm", "exp")
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "--detach", str(wt))
    cat = brc.build([repo, wt])
    same = [r for r in cat if r["research_id"] == "20260106-twice"]
    assert len(same) == 1
    assert len(same[0]["aliases"]) == 1


def test_copies_and_fixtures_are_not_experiments(tmp_path):
    repo = _repo(tmp_path)
    _exp(repo / "tmp" / "snap", "20260107-copy")
    _exp(repo, "20260101-test")
    cat = brc.build([repo])
    assert cat == []


def test_verdict_parsing():
    assert brc.parse_verdict("- [ ] PROMOTE\n- [x] **REJECT** because\n") == "REJECT"
    assert brc.parse_verdict("## Verdict: **PROMOTE (illustration)**") == "PROMOTE"
    assert brc.parse_verdict("# decision\nno verdict words") == "UNKNOWN"


def test_write_outputs_jsonl_and_markdown_twin(tmp_path):
    repo = _repo(tmp_path)
    _exp(repo, "20260108-x")
    out = tmp_path / "out"
    jl, md = brc.write(brc.build([repo]), out)
    rows = [json.loads(line) for line in jl.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["research_id"] == "20260108-x"
    assert "generated_at" in rows[0]
    text = md.read_text(encoding="utf-8")
    assert "20260108-x" in text and "UNCOMMITTED_ORPHAN" in text
    assert "do not edit" in text


def test_not_a_git_directory_still_lists_as_orphan(tmp_path):
    _exp(tmp_path / "plain", "20260109-nogit")
    cat = _by_id(brc.build([tmp_path / "plain"]))
    assert cat["20260109-nogit"]["state"] == "UNCOMMITTED_ORPHAN"


def test_free_form_verdicts_are_kept_as_written():
    assert (
        brc.parse_verdict("# G88D\n\n## Verdict\n\n`CANONICAL_PROXY_ONLY`\n")
        == "CANONICAL_PROXY_ONLY"
    )
    assert brc.parse_verdict("**Verdict:** `PASS_CALIBRATED`\nmore") == "PASS_CALIBRATED"
    # an explicitly checked box wins over a free-form value
    assert brc.parse_verdict("## Verdict\n\nFOO\n- [x] REJECT\n") == "REJECT"


def test_earliest_verdict_wins_over_a_quoted_later_one():
    # reproducer: a WEAKENED decision that quotes a sibling experiment's 'Verdict: CONFIRMED'
    # further down was catalogued as CONFIRMED
    text = (
        "# decision.md — H-B2-1n\n\n## Result\n**Verdict: WEAKENED** (per pre-registered "
        "criterion)\n\nSee H-B2-1m.\nVerdict: CONFIRMED\n"
    )
    assert brc.parse_verdict(text) == "WEAKENED"


def test_title_drops_the_claim_md_prefix_and_the_id(tmp_path):
    repo = _repo(tmp_path)
    d = _exp(repo, "20260110-t")
    (d / "claim.md").write_text("# claim.md — 20260110-t\nBody sentence here.\n", encoding="utf-8")
    rec = _by_id(brc.build([repo]))["20260110-t"]
    assert rec["title"] == "20260110-t"  # nothing informative in the heading -> keep the id
    assert rec["summary"] == "Body sentence here."


def test_summary_prefers_claim_rows_over_admin_prose(tmp_path):
    repo = _repo(tmp_path)
    d = _exp(repo, "20260111-s")
    (d / "claim.md").write_text(
        "# claim.md — 20260111-s\n\nWritten 2026-10-14 BEFORE any label existed.\n\n"
        "| Field | Value |\n|---|---|\n"
        "| **Entity** | the router choice of card for a typed prompt, in four architectures |\n"
        "| **Falsifiable predicate** | embeddings find more true requests than the keyword baseline |\n",
        encoding="utf-8",
    )
    s = _by_id(brc.build([repo]))["20260111-s"]["summary"]
    assert "embeddings" in s and "router" in s
    assert not s.startswith("Written")


def test_unchecked_option_list_is_never_the_verdict():
    # reproducer: '## Decision' followed by an unchecked '- [ ] PROMOTE' was read as PROMOTE
    opts = "## Decision\n\n- [ ] PROMOTE\n- [ ] REJECT\n"
    assert brc.parse_verdict(opts + "- [x] REJECT\n") == "REJECT"
    assert brc.parse_verdict(opts + "\nVerdict: WEAKENED\n") == "WEAKENED"
    assert brc.parse_verdict(opts) == "UNKNOWN"


def test_checked_project_specific_verdict_is_kept():
    text = "## Verdict\n- [ ] PROMOTE\n- [x] **CRITERION_INVALID** (stop-verdict)\n"
    assert brc.parse_verdict(text) == "CRITERION_INVALID"
    # a checked prose item is not a verdict
    assert brc.parse_verdict("- [x] Peter Lake lead noted\n") == "UNKNOWN"


def test_repo_under_a_tmp_directory_is_not_discarded(tmp_path):
    # Codex P2 reproducer (this is what broke CI under /tmp/pytest-of-...): a copy marker in an
    # ANCESTOR of the scan root must not discard every experiment.
    repo = _repo(tmp_path / "tmp" / "work")
    _exp(repo, "20260112-under-tmp")
    cat = _by_id(brc.build([repo]))
    assert "20260112-under-tmp" in cat


def test_linked_worktree_outside_the_given_roots_is_scanned(tmp_path):
    # Codex P2 reproducer: only the main repo is given; the untracked experiment lives in a
    # linked worktree elsewhere on disk.
    repo = _repo(tmp_path)
    wt = tmp_path.parent / (tmp_path.name + "_linked_wt")
    _git(repo, "worktree", "add", "-q", "-b", "side2", str(wt))
    _exp(wt, "20260113-in-linked-worktree")
    cat = _by_id(brc.build([repo]))
    assert cat["20260113-in-linked-worktree"]["state"] == "UNCOMMITTED_ORPHAN"
    assert "linked_wt" in cat["20260113-in-linked-worktree"]["canonical_path"]


def test_checked_verdict_beats_unchecked_option_in_a_real_decision_shape():
    # Codex P1 reproducer: '## Verdict\n- [ ] PROMOTE\n- [x] **NEEDS-MORE-DATA**' -> PROMOTE
    text = "## Verdict\n\n- [ ] PROMOTE\n- [x] **NEEDS-MORE-DATA** (infrastructure verified)\n"
    assert brc.parse_verdict(text) == "NEEDS-MORE-DATA"


# --- correction addenda: the governing verdict is the corrected one ----------------------------
_DOWNGRADE_ARROW = (
    "# decision.md - H-1\n\n## CORRECTION ADDENDUM (2026-09-07)\n\n"
    "**Verdict downgraded CONFIRMED → FALSIFIED.** Original text kept below.\n\n"
    "## Verdict\n\n**CONFIRMED** under the code's own criterion.\n"
)


def test_correction_addendum_overrides_the_original_verdict():
    assert brc.parse_verdict(_DOWNGRADE_ARROW) == "FALSIFIED"
    assert brc.has_correction(_DOWNGRADE_ARROW) is True


def test_downgraded_from_a_to_b_form():
    text = (
        "# decision.md\n\n## CORRECTION ADDENDUM\n\n"
        "The verdict below is downgraded from CONFIRMED to WEAKENED. Original kept.\n\n"
        "## Verdict\n\nCONFIRMED\n"
    )
    assert brc.parse_verdict(text) == "WEAKENED"


def test_addendum_without_an_explicit_new_verdict_is_flagged_not_guessed():
    text = (
        "# decision.md\n\n## CORRECTION ADDENDUM\n\n"
        'The finding is DOWNGRADED from "genuine reversal" to "seed noise".\n\n'
        "## Verdict\n\n- [x] PROMOTE\n"
    )
    assert brc.has_correction(text) is True
    assert brc.parse_verdict(text) == "PROMOTE"  # unchanged: nothing explicit to take


def test_control_plain_decision_is_not_flagged():
    text = "# decision.md\n\n## Verdict\n\n- [x] REJECT\n"
    assert brc.has_correction(text) is False
    assert brc.parse_verdict(text) == "REJECT"


def test_a_downgrade_quoted_far_below_the_header_is_not_a_correction():
    text = "# decision.md\n\n- [x] REJECT\n" + "filler line\n" * 60
    text += "\nAn earlier study was downgraded from CONFIRMED to WEAKENED.\n"
    assert brc.has_correction(text) is False
    assert brc.parse_verdict(text) == "REJECT"


def test_record_and_markdown_carry_the_correction_flag(tmp_path):
    repo = _repo(tmp_path)
    _exp(repo, "20260907-corrected", _DOWNGRADE_ARROW)
    _exp(repo, "20260908-plain", "# decision\n- [x] REPEAT\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "e")
    cat = {r["research_id"]: r for r in brc.build([repo])}
    assert cat["20260907-corrected"]["verdict"] == "FALSIFIED"
    assert cat["20260907-corrected"]["has_correction"] is True
    assert cat["20260908-plain"]["has_correction"] is False
    _, md = brc.write(list(cat.values()), tmp_path / "out")
    rows = {
        ln.split("|")[1].strip(): ln
        for ln in md.read_text(encoding="utf-8").splitlines()
        if ln.startswith("| 2026")
    }
    assert "FALSIFIED (corrected)" in rows["20260907-corrected"]
    assert "(corrected)" not in rows["20260908-plain"]


def test_correction_keeps_digits_dots_and_slashes_in_the_new_verdict():
    text = "# d\n\n## CORRECTION ADDENDUM\n\nVerdict revised CONFIRMED -> PASS_V2 after review.\n"
    assert brc.parse_verdict(text) == "PASS_V2"
    text = "# d\n\n## CORRECTION ADDENDUM\n\nVerdict downgraded CONFIRMED → FALSIFIED.\n"
    assert brc.parse_verdict(text) == "FALSIFIED"  # sentence-final dot is not part of the token


def test_an_overlong_new_verdict_token_is_not_truncated():
    text = (
        "# d\n\n## CORRECTION ADDENDUM\n\nVerdict revised CONFIRMED -> "
        + "X" * 60
        + "\n\n- [x] REPEAT\n"
    )
    assert brc.parse_verdict(text) == "REPEAT"  # nothing explicit and complete: fall back


def test_branch_only_record_carries_the_correction_flag(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "side")
    _exp(repo, "20260907-corrected", _DOWNGRADE_ARROW)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "e")
    _git(repo, "checkout", "-q", "main")
    rec = {r["research_id"]: r for r in brc.build([repo])}["20260907-corrected"]
    assert rec["state"] == "COMMITTED_BRANCH"
    assert rec["verdict"] == "FALSIFIED"
    assert rec["has_correction"] is True


# --- fallback formats (calibration 2026-11-04): synthetic examples, no real decision text -------

_LONG = "PASS_ONE_WEAK_SIGNAL_NARROW_SELECTION_HOLDS_ON_THE_TOY_MODEL_ONLY"  # > 40 chars


def test_long_free_form_verdict_under_heading_is_read():
    assert len(_LONG) > 41
    assert brc.parse_verdict(f"# X\n\n## Verdict\n\n`{_LONG}`\n") == _LONG


def test_long_free_form_verdict_after_label_is_read():
    assert brc.parse_verdict(f"**Date:** 2026-01-01\n\n**Verdict:** `{_LONG}`\nmore\n") == _LONG


def test_same_line_heading_form_is_read():
    assert brc.parse_verdict("# X\n\n## Decision: **GO** -> ship the small fix\n") == "GO"


def test_result_heading_followed_by_bold_token_is_read():
    assert brc.parse_verdict("## Result\n\n**MECHANISM_VERIFIED.** The effect holds.\n") == (
        "MECHANISM_VERIFIED"
    )


def test_fallback_never_overrides_what_the_main_chain_found():
    # A checked box and a short labelled verdict win over a later long fallback token.
    assert brc.parse_verdict(f"- [x] REJECT\n\n## Result\n\n**{_LONG}**\n") == "REJECT"
    assert brc.parse_verdict(f"Verdict: WEAKENED\n\n## Decision: **{_LONG}**\n") == "WEAKENED"


def test_a_status_label_is_not_a_verdict():
    assert brc.parse_verdict("**Status:** DRAFT\n\nsome analysis\n") == "UNKNOWN"
    assert brc.parse_verdict("**Status:** EXPLORATORY\n") == "UNKNOWN"


def test_prose_without_a_verdict_stays_unknown_with_the_fallback():
    assert brc.parse_verdict("# T\n\n## Result\n\nThe numbers moved a little.\n") == "UNKNOWN"
    assert brc.parse_verdict("## Decision\n\nWe decided to wait for more data.\n") == "UNKNOWN"


def test_result_heading_does_not_turn_a_status_or_an_id_into_a_verdict():
    assert brc.parse_verdict("## Result\n**DRAFT**\n") == "UNKNOWN"
    assert brc.parse_verdict("## Result\n\n**OB12** was inspected\n") == "UNKNOWN"
    assert brc.parse_verdict("## Result\n\n**EXP1** ran\n") == "UNKNOWN"


def test_fallback_does_not_blow_up_on_blank_line_runs():
    import time

    # The new patterns only; the older chain has its own (pre-existing) quadratic pattern.
    text = "## Verdict\n" + " \n" * 8000 + "!"
    t0 = time.perf_counter()
    for rx in brc._FALLBACK:
        rx.search(text)
    assert time.perf_counter() - t0 < 0.5
