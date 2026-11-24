## 🏆 Beat Claude — 2026-11-15

**File:** hooks/statusline.py  
**Current approach:** [CODE] Every status-line render invokes Git twice in sequence: `git rev-parse --show-toplevel`, then `git branch --show-current`. The complete 129-line file was read after selecting it randomly with PowerShell `Get-ChildItem hooks -File -Filter '*.py' | Get-Random`.  
**Better approach:** Obtain the root and full symbolic HEAD in one Git process on the normal path. Remove the `refs/heads/` prefix, preserve an empty branch display for detached HEAD, and fall back to the original two commands when the combined result is unsuccessful, warns, or has an unexpected shape.  
**Why it's better:** [VERIFIED-REAL] On this real workspace, the median Git-discovery time fell from **62.281 ms to 31.775 ms**, saving **30.506 ms / 49.0%**; subprocess launches fall from **2 to 1** on the normal path. These are local measurements, not an external benchmark or a claim about total render latency. Git documents both [`--show-toplevel` and `--symbolic-full-name`](https://git-scm.com/docs/git-rev-parse); the existing detached-HEAD behavior is documented by [`git branch --show-current`](https://git-scm.com/docs/git-branch).  
**Effort to implement:** **S — approximately 45–90 minutes** [INFERRED], including GitNexus impact analysis, integration, updating subprocess mocks, and focused regression tests.  
**Impact:** One fewer process creation per ordinary refresh, with approximately 30.5 ms less Git-discovery latency on this Windows machine. No new dependency, cache invalidation policy, or stale-branch risk from caching. Production/session-wide benefit remains [NEEDS-REAL-DATA].

```python
import os

# Replace only the project/branch block inside main(); reset already exists.
project = ""
branch = ""
try:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel", "--symbolic-full-name", "HEAD"],
        capture_output=True, text=True, timeout=2,
    )
    root, separator, ref = result.stdout.rstrip("\n").rpartition("\n")
    if (result.returncode == 0 and not result.stderr and separator
            and (ref.startswith("refs/heads/") or ref == "HEAD")):
        project = f" \033[1m{os.path.basename(root.strip())}{reset} |"
        name = ref.removeprefix("refs/heads/") if ref != "HEAD" else ""
        branch = f" {name}" if name else ""
    else:
        # Preserve the original behavior for unborn/bare repos and odd output.
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            project = f" \033[1m{os.path.basename(result.stdout.strip())}{reset} |"
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            branch = f" {result.stdout.strip()}"
except Exception:
    pass  # Cosmetic status line: retain existing best-effort behavior.
```

The snippet replaces the existing project/branch block inside `main()`, immediately after `reset` is defined. It is a tested proposal, **not applied to the hook**.

### Evidence and boundaries

- **Baseline:** local branch `y17/pilot-pains`, HEAD `4e6328a`; the hook has no working-tree diff. This review concerns the local checkout, not an asserted current upstream version.
- **Source digest:** SHA-256 of UTF-8 text read with Python newline normalization: `7e4356e9a524b46bb54df10f566587a1be1f57f71f6a0e123ad349e92fe5138f`.
- **Environment:** Windows, Python 3.11.13, Git 2.51.1.windows.1.
- **Method:** execute the exact original Git block extracted from the file and the proposed block in memory, using real Git subprocesses and the real repository. Five warmup pairs; 50 measured pairs with alternating baseline/proposal order; `perf_counter_ns()`. No disk source replacement.
- **Results:** original median 62.28075 ms, proposed median 31.77495 ms; nearest-rank p95 65.5755 ms versus 33.4234 ms. This excludes Python interpreter startup and the remainder of the status-line function.
- **Artifact verification:** both Python blocks parse successfully. Running the reproduction block directly from the saved report gave medians 62.86255 ms versus 31.91635 ms (p95 65.5391 ms versus 34.1961 ms), supporting the same local effect. The source digest remained unchanged.
- **Real compatibility:** identical project/branch strings from repository root and its `hooks/` subdirectory.
- **[VERIFIED-SYNTHETIC] Boundary checks:** identical strings in six temporary Git scenarios: unborn branch, attached branch, same-name tag and branch, detached HEAD, outside a repository, and bare repository. Fixture root contains spaces. Non-repository testing used `GIT_CEILING_DIRECTORIES` to prevent discovery of the enclosing workspace. These checks establish only the tested mechanics.
- **[VERIFIED] Existing baseline tests:** `python -B -m pytest tests/test_coverage_statusline.py::TestStatusline tests/test_analysis_hooks.py::TestStatusline -q -p no:cacheprovider` → **24 passed in 1.68s**. These ran against the unchanged hook, not an integrated patch. A CuPy CUDA-path warning was unrelated to these checks.
- **Tradeoff:** fallback scenarios invoke **three commands rather than two**, so they may be slower; their nominal summed per-call timeout budgets increase from four to six seconds. No improvement is claimed for those scenarios. Missing-Git and timeout behavior of the proposal was not separately fault-injected.
- **Integration remaining:** subprocess mocks that expect exactly two outputs need deliberate updates; check the entire rendered output after integration. GitNexus tools were unavailable in this session. No production symbol was edited and no commit was made; impact analysis is still required before implementation.
- **Scope:** performance is the one selected improvement. Readability adds a fallback branch in exchange for the measured saving. The existing argument-list subprocess calls avoid introducing a shell; no new security finding or CVE claim is made.

### Reproduce the timing

Run from the repository root after saving this report. This uses the first Python block above as the candidate and leaves the hook unchanged.

```python
import re
import statistics
import subprocess
import textwrap
import time
from pathlib import Path

source = Path("hooks/statusline.py").read_text(encoding="utf-8")
report = Path("beat-claude-2026-11-15.md").read_text(encoding="utf-8")
original = textwrap.dedent(
    source.split("    # project name + git branch")[1]
    .split("    # active subagent")[0].split("\n", 1)[1]
)
proposed = re.search(r"```python\n(.*?)\n```", report, re.S).group(1)
blocks = [compile(original, "<original>", "exec"),
          compile(proposed, "<proposed>", "exec")]

def measure(index):
    scope = {"subprocess": subprocess, "reset": "\033[0m"}
    start = time.perf_counter_ns()
    exec(blocks[index], scope)
    elapsed = (time.perf_counter_ns() - start) / 1e6
    return elapsed, (scope["project"], scope["branch"])

for _ in range(5):
    assert measure(0)[1] == measure(1)[1]
samples = [[], []]
for pair in range(50):
    for index in ((0, 1) if pair % 2 == 0 else (1, 0)):
        elapsed, _ = measure(index)
        samples[index].append(elapsed)
print("median_ms:", [statistics.median(s) for s in samples])
print("p95_ms:", [sorted(s)[47] for s in samples])
```

### 🔥 Trend Gap

No dated industry trend is asserted. The relevant improvement is measured removal of redundant subprocess work using existing, officially documented Git capabilities. A rewrite merely to adopt a newer library is not justified by this review.

### Claude Score: 8/10

Subjective assessment of this bounded status-line implementation: architecture 8/10; security 8/10 (limited source inspection, not a security audit); trend alignment 8/10 (no obsolescence found). Missed: repeated process startup on the refresh path. Would ship as-is: **YES**; the finding is a performance opportunity, not a release blocker.

**Automate this:** reuse this small paired benchmark when the Git-discovery block changes → local developer command, without a noisy wall-clock CI threshold → estimated 5–10 minutes per relevant review; weekly savings unknown.

**Implemented:** report and in-memory candidate only; hook unchanged.  
**Verified:** measured local Git-block improvement, two real-location equivalence checks, six synthetic boundary comparisons, and 24 existing baseline tests. No claim of production deployment or model-wide superiority.

**Save-path limitation:** requested destination `.codex/reports/beat-claude-2026-11-15.md` could not be created: this session has read-only access to `.codex`, and directory creation returned Access denied. Saved at repository root instead. Temporary fixture repositories are under `tmp/beat-claude-fixtures-20261115/`; no cleanup or permission changes were attempted.

#improvement #competition
