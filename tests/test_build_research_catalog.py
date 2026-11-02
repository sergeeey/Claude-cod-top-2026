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
    repo.mkdir()
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
