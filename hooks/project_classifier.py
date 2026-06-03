#!/usr/bin/env python3
"""SessionStart hook: classify project TYPE from filesystem signals.

WHY: the system applied one-size-fits-all methodology. A quick CSS fix got the
full research-falsification protocol; a research project might skip EstimandOps
because nobody invoked it. This hook reads deterministic signals (folders, files)
and writes a verdict to .claude/memory/_auto/project_profile.md, so the Dispatcher
skill can load the RIGHT methodology instead of everything-always.

Hybrid design: the hook decides confidently when signals are clear (deterministic,
0 tokens). When signals are ambiguous (low margin), it marks the profile
`ambiguous` and asks the LLM to confirm — that is the only case where a token is spent.

Stdlib only — runs anywhere without pip install.
"""

import sys
from pathlib import Path

# WHY: each signal contributes weight to a project type. Highest score wins;
# the margin to the runner-up becomes the confidence. Deterministic and explainable.
SIGNALS = {
    "research": [
        ("experiments", "dir"),
        ("null_results", "dir"),
        ("parked", "dir"),
        ("estimand.md", "glob:**/estimand.md"),
        ("notebooks", "glob:**/*.ipynb"),
        ("claim.md", "glob:**/claim.md"),
    ],
    "data-science": [
        ("data", "dir"),
        ("csv/parquet", "glob:**/*.csv"),
        ("parquet", "glob:**/*.parquet"),
        ("pyproject.toml", "file"),
    ],
    "production": [
        ("tests", "dir"),
        ("ci", "glob:.github/workflows/*.yml"),
        ("ci-yaml", "glob:.github/workflows/*.yaml"),
        ("pyproject.toml", "file"),
        ("package.json", "file"),
        ("src", "dir"),
    ],
    "mvp": [
        ("src", "dir"),
        ("readme-mvp", "readme_kw:mvp|prototype|proof of concept|poc"),
    ],
}

METHODOLOGY = {
    "research": "FL Full-Ladder + EstimandOps (L0 gate) + skeptic-triggers. Mark claims [VERIFIED]/[HYPOTHESIS].",
    "data-science": "EstimandOps L0 gate + validation on REAL data ([VERIFIED-REAL], not synthetic). FL Standard.",
    "production": "reviewer mandatory + tester ≥80% coverage + FL Standard. security-audit before release.",
    "mvp": "Speed > rigor. Tests optional. FL Micro (PR-inline). builder solo.",
    "unonboarded": "No .claude/ found → run NEW PROJECT onboarding: ask goal/stack, create CLAUDE.md + activeContext.",
    "ambiguous": "Signals unclear → LLM: confirm project type from README/goal before loading heavy methodology.",
}


def _exists_dir(root: Path, name: str) -> bool:
    return (root / name).is_dir()


def _exists_file(root: Path, name: str) -> bool:
    return (root / name).is_file()


def _glob_any(root: Path, pattern: str) -> bool:
    try:
        return next(root.glob(pattern), None) is not None
    except (OSError, ValueError):
        return False


def _readme_has(root: Path, keywords: str) -> bool:
    kws = keywords.lower().split("|")
    for name in ("README.md", "readme.md", "README.MD"):
        p = root / name
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            return any(k in text for k in kws)
    return False


def _check(root: Path, kind: str) -> bool:
    if kind == "dir":
        return False  # handled by caller with the name
    return False


def score_project(root: Path) -> dict[str, int]:
    """Return {type: score} from filesystem signals. Pure, no side effects."""
    scores: dict[str, int] = {}
    for ptype, signals in SIGNALS.items():
        s = 0
        for _label, spec in signals:
            if spec == "dir":
                # label IS the dir name for plain "dir" specs
                continue
            if spec == "file":
                continue
            if spec.startswith("glob:"):
                if _glob_any(root, spec[5:]):
                    s += 1
            elif spec.startswith("readme_kw:"):
                if _readme_has(root, spec[10:]):
                    s += 1
        scores[ptype] = s
    # second pass for dir/file specs where label is the name
    for ptype, signals in SIGNALS.items():
        for label, spec in signals:
            if spec == "dir" and _exists_dir(root, label):
                scores[ptype] += 1
            elif spec == "file" and _exists_file(root, label):
                scores[ptype] += 1
    return scores


# WHY: the project's OWN CLAUDE.md/README states intent far more reliably than
# folder structure. experiments/ and null_results/ exist both in research repos
# AND in repos that merely SHIP the FL methodology — so structure alone misfires
# (verified: it called a config-toolkit "research"). Content keywords are the
# strong signal; structure is a tiebreaker only.
CONTENT_KEYWORDS = {
    "research": ["hypothesis", "falsif", "estimand", "научн", "гипотез", "research question", "experiment design"],
    "data-science": ["dataset", "training data", "model accuracy", "f1 score", "data pipeline", "feature engineering"],
    "production": ["production", "deploy", "ci/cd", "release", "uptime", "config toolkit", "library", "api server"],
    "mvp": ["mvp", "prototype", "proof of concept", "poc", "early version", "experiment with the idea"],
}


def _content_scores(root: Path) -> dict[str, int]:
    """Read project CLAUDE.md + README, score by explicit intent keywords."""
    text = ""
    for name in ("CLAUDE.md", "README.md", "readme.md"):
        p = root / name
        if p.is_file():
            try:
                text += "\n" + p.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                pass
    scores = {}
    for ptype, kws in CONTENT_KEYWORDS.items():
        scores[ptype] = sum(2 for k in kws if k in text)  # weight 2 — stronger than structure
    return scores


def classify(root: Path) -> tuple[str, int, dict[str, int]]:
    """Return (type, confidence_margin, raw_scores).

    Strategy: content (intent) dominates; structure breaks ties. Low margin → defer to LLM.
    """
    if not (root / ".claude").exists():
        return "unonboarded", 99, {}
    struct = score_project(root)
    content = _content_scores(root)
    # WHY: combine, content already weighted 2x. Structure is the weak tiebreaker.
    scores = {t: struct.get(t, 0) + content.get(t, 0) for t in SIGNALS}
    if not scores or max(scores.values()) == 0:
        return "ambiguous", 0, scores
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top, top_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    margin = top_score - runner_up
    # WHY: with only structural signals (no content keywords matched), the verdict is
    # unreliable — hand to LLM. Require content to have spoken for a confident call.
    content_spoke = max(content.values(), default=0) > 0
    if margin < 2 or not content_spoke:
        return "ambiguous", margin, scores
    return top, margin, scores


def write_profile(root: Path, ptype: str, margin: int, scores: dict[str, int]) -> Path:
    out_dir = root / ".claude" / "memory" / "_auto"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "project_profile.md"
    confidence = "HIGH" if margin >= 2 else ("MEDIUM" if margin == 1 else "LOW (ambiguous)")
    lines = [
        "# Project Profile (auto-detected)",
        "",
        f"- **Type:** {ptype}",
        f"- **Confidence:** {confidence} (margin={margin})",
        f"- **Signals:** {scores or 'none'}",
        "",
        "## Methodology to load",
        METHODOLOGY.get(ptype, METHODOLOGY["ambiguous"]),
        "",
        "> Auto-written by project_classifier.py at SessionStart.",
        "> If type looks wrong, the Dispatcher skill / LLM may override after reading README+goal.",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    try:
        root = Path.cwd()
        ptype, margin, scores = classify(root)
        if ptype == "unonboarded":
            print(f"[project-classifier] No .claude/ in {root.name} — NEW PROJECT onboarding suggested.")
            return
        write_profile(root, ptype, margin, scores)
        method = METHODOLOGY.get(ptype, "")
        if ptype == "ambiguous":
            print(
                f"[project-classifier] Project '{root.name}' type AMBIGUOUS (signals tie). "
                f"LLM: confirm from README/goal before loading heavy methodology. Scores: {scores}"
            )
        else:
            print(
                f"[project-classifier] Project '{root.name}' → {ptype} "
                f"(margin={margin}). Load: {method}"
            )
    except Exception as e:  # WHY: a SessionStart hook must never block the session.
        print(f"[project-classifier] skipped ({type(e).__name__})", file=sys.stderr)


if __name__ == "__main__":
    main()
