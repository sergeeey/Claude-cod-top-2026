#!/usr/bin/env python3
"""SessionStart hook: warn when a project has an estimand/claim but key fields
(MCID, ICE strategy) are unfilled — so the design layer can actually be enforced.

WHY: estimand.md can sit in the repo with MCID/ICE left as template placeholders.
Then Skeptic and go/no-go run on generic triggers and the careful design is never
enforced (the 'design ↔ verification' gap). This cheap guard nudges: if you have
an estimand, finish MCID + ICE, then run /estimand-bridge to wire it into Skeptic.

Only fires when estimand/claim files exist — silent for non-research projects.
Stdlib only.
"""

import sys
from pathlib import Path

PLACEHOLDER_MARKERS = ("[value", "[description", "[ice", "tbd", "todo", "xxx", "[variable", "...")


def find_estimands(root: Path) -> list[Path]:
    try:
        return [p for p in root.glob("**/estimand.md") if "_template" not in str(p)]
    except (OSError, ValueError):
        return []


def field_unfilled(text: str, label: str) -> bool:
    """True if the VALUE line for `label` (e.g. 'MCID: ...') is missing or a placeholder.

    WHY: anchor on the value assignment 'label:' not the heading — the heading
    '### MCID (Minimum...)' is not where the value lives, and a fixed-width window
    from it misses the real '[value]' placeholder a few lines down.
    """
    target = label.lower() + ":"
    for raw in text.splitlines():
        line = raw.strip().lower()
        # match 'mcid:' but skip markdown headings like '### mcid (...)'
        if line.startswith("#"):
            continue
        if line.startswith(target) or (target in line and line.index(target) < 4):
            value = line.split(":", 1)[1].strip()
            if not value:
                return True
            return any(m in value for m in PLACEHOLDER_MARKERS)
    return True  # no value line found at all


def main() -> None:
    try:
        root = Path.cwd()
        estimands = find_estimands(root)
        # Also flag the case: claim.md exists but no estimand at all.
        has_claim = next(root.glob("**/claim.md"), None) is not None
        if not estimands:
            if has_claim:
                print(
                    "[estimand-guard] Found claim.md but no estimand.md — define the estimand "
                    "first (population/endpoint/MCID/ICE), else Skeptic can't enforce your criteria."
                )
            return
        issues = []
        for est in estimands:
            try:
                text = est.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            missing = []
            if field_unfilled(text, "MCID"):
                missing.append("MCID (significance threshold)")
            if field_unfilled(text, "ICE") and "strategy" not in text.lower():
                missing.append("ICE strategy")
            if missing:
                issues.append(f"{est.parent.name}: {', '.join(missing)}")
        if issues:
            print(
                "[estimand-guard] estimand.md present but key fields unfilled — "
                "Skeptic/go-no-go can't enforce them yet:\n  "
                + "\n  ".join(issues)
                + "\n  → fill them, then run /estimand-bridge to wire MCID/ICE into Skeptic."
            )
    except Exception as e:  # never block session start
        print(f"[estimand-guard] skipped ({type(e).__name__})", file=sys.stderr)


if __name__ == "__main__":
    main()
