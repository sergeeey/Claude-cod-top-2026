#!/usr/bin/env python3
"""Generate docs/hook-control-matrix.md from hooks/registry.yaml + hooks/settings.json.

WHY: an external audit (2026-08-14) correctly flagged that README's "95 hooks
always on" overclaims -- registry.yaml's own `class: dormant` / `class:
library` entries don't fire on any live Claude Code event, and even among
hooks that DO fire, only PreToolUse escalation:block hooks can actually deny
a tool call (see hooks/CLAUDE.md). Hand-deriving this breakdown by eye (as
this repo's own author first tried) produced wrong numbers on the first two
attempts -- a regex that let "class: dormant" leak from one registry entry
into its neighbor, and a "6 libraries" guess that didn't match the real
`class: library` field. Generating it from the source of truth removes that
failure mode: wrong-by-hand becomes wrong-by-construction-and-caught-by---check.

Categories (wiring status, from registry.yaml `class:`):
  wired      -- class in {security, quality, observability, automation} AND
                found registered in hooks/settings.json
  dormant    -- class: dormant (defined, intentionally not wired)
  library    -- class: library (imported by other hooks, never itself
                triggered by a Claude Code event)
  orphaned   -- none of the above matched -- flagged loudly, not hidden,
                since a silent 4th bucket is exactly the kind of drift this
                script exists to prevent

Categories (real capability, from registry.yaml `event:` + `escalation:`):
  PREVENT    -- event: PreToolUse AND escalation: block (per hooks/CLAUDE.md,
                only PreToolUse can sys.exit(1) / emit permissionDecision:deny)
  WARN       -- escalation: warn, or escalation: block on a non-PreToolUse
                event (mislabeled-block: fires after the fact, can only nudge
                via additionalContext -- same check as
                tests/test_structure.py::TestGateNamedHooksDisclosure)
  OBSERVE    -- escalation: info (pure logging/telemetry, no user-facing signal)
  N/A        -- dormant or library entries have no live event to evaluate
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "hooks" / "registry.yaml"
SETTINGS = ROOT / "hooks" / "settings.json"
OUTPUT = ROOT / "docs" / "hook-control-matrix.md"

# WHY [A-Za-z_0-9]+, not [a-z_0-9]+ (reviewer P1, 2026-08-14): the lowercase-only
# version silently dropped `activeContext_hygiene` (a real, wired hook -- see
# hooks/settings.json) because of its capital C/H, undercounting the registry
# total as 94 instead of 95 -- the exact "wrong number about hooks" class of bug
# this generator exists to prevent, just moved from README prose into the parser.
ENTRY_RE = re.compile(r"^  ([A-Za-z_0-9]+):$", re.MULTILINE)
# registry.yaml inconsistently quotes scalar values (event: "PreToolUse" vs
# event: PreToolUse) -- strip optional surrounding quotes so both forms
# compare equal (a bare `\S+` capture missed this and silently mis-classified
# weakened_test_guard as non-blocking; caught by spot-checking the output,
# not by inspection of the regex alone).
FIELD_RE = re.compile(r'^\s*(class|event|escalation|fail_mode):\s*"?([^"\s]+)"?\s*$', re.MULTILINE)


def parse_registry(text: str) -> dict[str, dict[str, str]]:
    """Split registry.yaml into per-entry blocks bounded by the NEXT top-level
    key (or EOF), so a field lookup can't leak from one entry into its
    neighbor -- the exact bug an earlier hand-written version of this had."""
    starts = list(ENTRY_RE.finditer(text))
    entries: dict[str, dict[str, str]] = {}
    for i, m in enumerate(starts):
        name = m.group(1)
        start = m.end()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        body = text[start:end]
        fields = {k: v for k, v in FIELD_RE.findall(body)}
        entries[name] = fields
    return entries


def parse_wired(settings_text: str) -> set[str]:
    return set(re.findall(r"([A-Za-z_][A-Za-z_0-9]*)\.py", settings_text))


def classify_wiring(name: str, fields: dict[str, str], wired: set[str]) -> str:
    cls = fields.get("class", "")
    if cls == "dormant":
        return "dormant"
    if cls == "library":
        return "library"
    if name in wired:
        return "wired"
    return "orphaned"


def classify_capability(fields: dict[str, str], wiring: str) -> str:
    if wiring in ("dormant", "library", "orphaned"):
        return "N/A"
    event = fields.get("event", "")
    events = event.split("|")
    escalation = fields.get("escalation", "")
    if escalation == "block":
        if "PreToolUse" not in events:
            return "WARN (mislabeled block)"
        return "PREVENT" if len(events) == 1 else "PREVENT (on PreToolUse leg only)"
    if escalation == "warn":
        return "WARN"
    if escalation == "info":
        return "OBSERVE"
    return "UNKNOWN"


def build_matrix() -> tuple[str, dict[str, int]]:
    registry_text = REGISTRY.read_text(encoding="utf-8")
    settings_text = SETTINGS.read_text(encoding="utf-8")
    entries = parse_registry(registry_text)
    wired = parse_wired(settings_text)

    rows = []
    counts = {"wired": 0, "dormant": 0, "library": 0, "orphaned": 0}
    capability_counts: dict[str, int] = {}
    for name in sorted(entries):
        fields = entries[name]
        wiring = classify_wiring(name, fields, wired)
        capability = classify_capability(fields, wiring)
        counts[wiring] += 1
        capability_counts[capability] = capability_counts.get(capability, 0) + 1
        rows.append(
            (name, wiring, fields.get("event", "-"), fields.get("escalation", "-"), capability)
        )

    lines = [
        "<!-- GENERATED by scripts/gen_hook_matrix.py — do not hand-edit. -->",
        "<!-- Regenerate: python scripts/gen_hook_matrix.py -->",
        "",
        "# Hook Control Matrix",
        "",
        "Source of truth: `hooks/registry.yaml` (`class`/`event`/`escalation` fields)",
        "cross-referenced against `hooks/settings.json` (actual wiring).",
        "",
        "Per `hooks/CLAUDE.md`: only a `PreToolUse` hook can actually block a tool",
        "call (`sys.exit(1)` / `permissionDecision: deny`). Every other event can only",
        "inject `additionalContext` after the action already happened — advisory, not",
        "preventive, regardless of what its own `escalation:` field claims.",
        "",
        f"**Totals:** {sum(counts.values())} registry entries — "
        f"{counts['wired']} wired · {counts['dormant']} dormant · "
        f"{counts['library']} library modules"
        + (
            f" · {counts['orphaned']} ORPHANED (not wired, not dormant, not library — needs triage)"
            if counts["orphaned"]
            else ""
        ),
        "",
        "**Real capability, wired hooks only:** "
        + " · ".join(f"{v} {k}" for k, v in sorted(capability_counts.items()) if k != "N/A"),
        "",
        "| Hook | Wiring | Event | Escalation | Real capability |",
        "|------|--------|-------|------------|------------------|",
    ]
    for name, wiring, event, escalation, capability in rows:
        lines.append(f"| `{name}` | {wiring} | {event} | {escalation} | {capability} |")
    lines.append("")
    return "\n".join(lines), counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if regenerated output differs from committed file",
    )
    args = parser.parse_args()

    content, counts = build_matrix()

    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            print(
                f"[gen_hook_matrix] {OUTPUT} is stale — "
                "run `python scripts/gen_hook_matrix.py` and commit.",
                file=sys.stderr,
            )
            return 1
        print("[gen_hook_matrix] up to date.")
        return 0

    OUTPUT.write_text(content, encoding="utf-8")
    print(f"[gen_hook_matrix] wrote {OUTPUT} ({sum(counts.values())} entries).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
