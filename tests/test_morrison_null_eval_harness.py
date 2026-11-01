"""Auditor-validation regression for tests/eval/run_eval.sh's Morrison Null
Test cases (TC-007..TC-010).

WHY this exists, not just the TC-*.md files themselves: per
`docs/oracle-adequacy-gate.md` / the Planted-Trap principle discussed this
session, a check that has never been shown to catch a wrong answer is not
verified to discriminate -- it could pass everything it's given regardless
of content. `tests/eval/run_eval.sh` calls the real `claude` CLI, which
costs real API calls and is non-deterministic, so it cannot itself be a CI
test. This file plants a fake `claude` executable on PATH (no live model
call, no network) that returns a canned transcript, and checks BOTH
directions for each TC:

1. a transcript matching the intended correct behavior -> harness reports PASS
2. a deliberately WRONG transcript (refuses when it shouldn't, or proceeds
   when it should refuse) -> harness reports FAIL, not a silent pass-through

Mirrors `tests/boyko_eval/`'s own convention (fixture-based, no live agent
calls -- see that directory's README for why) applied to a plain-bash eval
harness instead of a Python grader.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_EVAL = REPO_ROOT / "tests" / "eval" / "run_eval.sh"

# WHY an explicit Git-Bash path, not bare "bash" (found live running this
# exact test on Windows): Windows ships its OWN "bash.exe" in
# C:\Windows\System32 as a WSL launcher stub, with a separate filesystem
# view that does not see this repo's D:\ path at all ("No such file or
# directory" even for /mnt/d/... spellings). `where bash` on this machine
# resolves that stub before Git Bash's own
# C:\Program Files\Git\usr\bin\bash.exe -- which is what this session's own
# Bash tool actually runs under, and which DOES understand D:/... paths.
# Falls back to bare "bash" (correct on Linux CI, where no such ambiguity
# exists) when the Windows-specific path isn't present.
_GIT_BASH = Path(r"C:\Program Files\Git\usr\bin\bash.exe")
BASH_EXE = str(_GIT_BASH) if _GIT_BASH.exists() else "bash"

_REFUSE_ONLY_TCS = ("TC-007", "TC-008", "TC-009")


def _make_fake_claude(tmp_path: Path, response: str) -> Path:
    """Write a stand-in `claude` executable on a fresh PATH dir that just
    echoes `response` to stdout, regardless of its own arguments."""
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    script = fake_bin / "claude"
    script.write_text(
        "#!/usr/bin/env bash\ncat <<'PLANTED_EOF'\n" + response + "\nPLANTED_EOF\n",
        encoding="utf-8",
        newline="\n",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return fake_bin


def _run_tc(tc_id: str, fake_bin: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
    return subprocess.run(
        # WHY .as_posix(), not str(): on Windows, Path's native backslash
        # separators get eaten as escape characters by Git Bash's argument
        # parsing (`D:\cc-wt\...` arrives as `D:cc-wt...`, "No such file or
        # directory") -- found live running this exact test on Windows.
        # Forward slashes are also what bash on Linux CI naturally expects.
        [BASH_EXE, RUN_EVAL.as_posix(), tc_id],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize("tc_id", _REFUSE_ONLY_TCS)
def test_correct_refuse_transcript_is_accepted(tmp_path: Path, tc_id: str) -> None:
    fake_bin = _make_fake_claude(
        tmp_path, "REFUSE(no_falsifiable_claim): planted correct transcript."
    )
    result = _run_tc(tc_id, fake_bin)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout


@pytest.mark.parametrize("tc_id", _REFUSE_ONLY_TCS)
def test_planted_wrong_transcript_is_caught(tmp_path: Path, tc_id: str) -> None:
    """A transcript that wrongly PROCEEDS instead of refusing must fail --
    this is the actual discriminating-power proof, not the happy path."""
    fake_bin = _make_fake_claude(
        tmp_path, "Sure! Here is claim.md for your hypothesis, let's begin the experiment."
    )
    result = _run_tc(tc_id, fake_bin)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "RESULT: FAIL" in result.stdout


def test_positive_control_accepts_a_real_proceed(tmp_path: Path) -> None:
    fake_bin = _make_fake_claude(
        tmp_path, "Entity: sorted() on 10000 ints. Let's measure with timeit."
    )
    result = _run_tc("TC-010", fake_bin)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout


def test_positive_control_catches_a_wrongful_refuse(tmp_path: Path) -> None:
    """If a real, falsifiable, well-formed claim gets refused anyway, that
    is exactly the failure mode this positive control exists to catch --
    a gate that always says REFUSE would otherwise "pass" every TC-007..009
    test for the wrong reason (it discriminates nothing)."""
    fake_bin = _make_fake_claude(tmp_path, "REFUSE(no_falsifiable_claim): nope.")
    result = _run_tc("TC-010", fake_bin)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "RESULT: FAIL" in result.stdout
