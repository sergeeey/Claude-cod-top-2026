# Morning Focus - 2026-07-05

## 🐸 A1 Task (eat the frog first)
Run `pytest --cov --cov-report=term-missing`, identify the top uncovered modules, write targeted tests until coverage ≥86%, push, confirm CI green — breaking 25 consecutive days of structural avoidance on the single remaining "Done when" gate.

## Top-3 Priority
1. **Coverage gate: measure → test → CI green at ≥86%** — SIGNAL. This is the explicit Scope Fence "Done when" criterion (currently 75% CI/Linux). Every other task is blocked or irrelevant until this closes. 25-day structural avoidance pattern must break today. Concrete entry: `pytest --cov --cov-report=term-missing | grep TOTAL`, then grep for lowest-coverage modules, write tests there first.
2. **Pin ruff (and mypy/pytest) versions in pyproject.toml or requirements-dev.txt** — SIGNAL. The July 1 CI regression (ruff I001 masked by stale local 0.3.2 vs CI's unpinned latest) is a documented recurring-failure class. 1h work, prevents the next hidden CI breakage. Do after coverage gate or alongside it.
3. **Run install.sh --profile=standard on 3rd machine (sboi)** — SIGNAL. Final "Done when" gate after coverage. Currently tested on 2 machines. Can't claim distribution-ready until the 3rd machine passes. Unblock: finish A1 first so the installer being tested is CI-green.

## Ignore Today
- mcp-bouncer Show HN post — Scope Fence explicitly says NOT NOW for marketplace/public distribution; 0 consequence for one more day
- New features, new hooks, new skills — scope fence: "not until CI green + coverage ≥86% + install.sh on 3 machines"
- Obsidian graph colorGroups reset — cosmetic, noise, zero project-forward value
- repo-clean-test worktree cleanup — administrative, D-tier, no consequence

## SNR Score yesterday: 2/10
(from evening-snr-20260704.md — zero substantive commits toward A1 for 25 consecutive days; only automated FocusOS infra ran)

---
**Pattern alert:** Coverage gap (75%→86%) has appeared as A1 in morning-focus files since at least 2026-06-10. This is confirmed structural avoidance. The frog is the same frog. Eat it first, before email, before planning, before any B task.

#morning-focus #focusos #tracy #snr
