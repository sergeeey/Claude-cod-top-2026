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
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "hooks" / "registry.yaml"
SETTINGS = ROOT / "hooks" / "settings.json"
OUTPUT = ROOT / "docs" / "hook-control-matrix.md"
HOOKS_DIR = ROOT / "hooks"

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
    """Classify a registry entry's wiring status.

    WHY the dormant/library branches check `name in wired` too (2026-08-27):
    file_auto_parser, hook_observability, and smart_model_router were wired
    into hooks/settings.json by PR #272, but their `class: dormant` field was
    never updated -- this function trusted the label unconditionally and kept
    reporting them dormant in docs/hook-control-matrix.md for the whole
    window between that PR and a later live-machine wiring-gap audit that
    caught it by hand. A stale `class: dormant`/`class: library` label that
    disagrees with the actual wired set is exactly the kind of silent drift
    this generator exists to prevent elsewhere (see the "orphaned" bucket
    below) -- it must not have a blind spot for its own primary label.
    """
    cls = fields.get("class", "")
    if cls == "dormant":
        return "mismatch" if name in wired else "dormant"
    if cls == "library":
        return "mismatch" if name in wired else "library"
    if name in wired:
        return "wired"
    return "orphaned"


def classify_capability(fields: dict[str, str], wiring: str) -> str:
    if wiring in ("dormant", "library", "orphaned", "mismatch"):
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


_PREVENT_CAPABILITIES = frozenset({"PREVENT", "PREVENT (on PreToolUse leg only)"})


def check_prevent_hooks_explicit_fail_closed(
    entries: dict[str, dict[str, str]], wired: set[str]
) -> list[str]:
    """Gate 12a: every PREVENT-classified hook must call hook_main() with an
    EXPLICIT fail_closed= argument at its entrypoint.

    WHY (2026-08-28, designed as a follow-up to weakened_test_guard.py's
    PR #280 fix): a PREVENT hook (event contains PreToolUse AND escalation:
    block -- the only hooks in this repo able to actually deny a tool call,
    per hooks/CLAUDE.md) has its whole security value riding on ALSO handling
    its OWN failure gracefully. A bare `main()` call has no timeout guard,
    and on an uncaught exception exits via Python's default
    traceback-to-stderr path -- which PreToolUse's protocol ignores entirely
    (only stdout JSON blocks, not exit code; see hooks/lib/runtime.py's
    module docstring). A crashed PREVENT hook therefore silently becomes an
    ALLOW by omission -- exactly the failure weakened_test_guard.py had
    before PR #280, and which re-reading its 6 siblings during Gate 12a's
    design (same day) found still live in iteration_guard.py and
    promotion_gate_guard.py.

    Explicitly does NOT compare fail_closed's VALUE against registry.yaml's
    fail_mode field. Direct evidence across all 7 PREVENT hooks (design
    session, 2026-08-28) proved that 1:1 mapping wrong: input_guard.py and
    weakened_test_guard.py both correctly use fail_closed=True despite
    fail_mode: open, and agent_tool_scope_guard.py correctly uses
    fail_closed=False despite escalation: block. fail_mode describes the
    hook's own business-logic decision path (e.g. "malformed input -- don't
    block an unrelated call"); hook_main's fail_closed describes the
    infrastructure crash/timeout path -- orthogonal by design, per
    weakened_test_guard.py's own WHY comment on this exact point. This gate
    only requires the fail_closed decision to be made EXPLICITLY -- never
    what the decision is.

    Hooks with no readable hooks/<name>.py source are skipped, not flagged --
    a missing source file for an allegedly-wired hook is a different, already
    -detectable problem (the orphaned/mismatch checks above); conflating the
    two would blur this gate's one job.

    Known, deliberate scope boundaries (matches by NAME, not by verified
    origin -- a full import-resolution check is out of scope for this gate):
    - Only matches a bare `hook_main(...)` call (`from utils import hook_main`
      / `from lib.runtime import hook_main` then calling it unqualified) --
      every real PREVENT hook uses this style today. An aliased or
      attribute-style call (`utils.hook_main(...)`, `hook_main as hm`) would
      not be recognized and would be reported as `no_hook_main`, a false
      positive rather than a silent miss.
    - A hook that locally defined its OWN function also named `hook_main`
      (shadowing the real import) would be wrongly accepted -- confirmed
      (2026-08-28) no hook in this repo does this via
      `grep -n "^def hook_main" hooks/*.py`, but this is a false-negative
      shape the AST check cannot itself rule out, since it only checks the
      called name, not its resolved origin.
    Both named here, not silently broken, matching this repo's convention
    elsewhere (e.g. hooks/registry.yaml's own header comment).
    """
    errors: list[str] = []
    for name in sorted(entries):
        fields = entries[name]
        wiring = classify_wiring(name, fields, wired)
        capability = classify_capability(fields, wiring)
        if capability not in _PREVENT_CAPABILITIES:
            continue
        source_path = HOOKS_DIR / f"{name}.py"
        try:
            text = source_path.read_text(encoding="utf-8")
        except OSError:
            continue  # not this gate's job -- see docstring
        try:
            tree = ast.parse(text, filename=str(source_path))
        except SyntaxError:
            continue  # a source syntax error is a different, already-caught problem
        call = _find_dunder_main_hook_main_call(tree)
        if call is None:
            errors.append(
                f"{name}: PREVENT hook ({source_path.name}) calls its entrypoint "
                "bare (no hook_main() wrapper) -- an uncaught exception or hang "
                "crashes silently with no permissionDecision ever emitted, "
                "defeating this hook's block. Wrap it: hook_main(main, "
                "fail_closed=<True|False>), same as pre_commit_guard.py."
            )
        elif not any(kw.arg == "fail_closed" for kw in call.keywords):
            errors.append(
                f"{name}: PREVENT hook ({source_path.name}) calls hook_main() "
                "without an explicit fail_closed= argument -- relies on the "
                "silent default (False). For a hook whose job is to deny "
                "dangerous actions, this choice must be explicit and reasoned "
                "in a WHY comment, not implicit."
            )
    return errors


def _find_dunder_main_hook_main_call(tree: ast.Module) -> ast.Call | None:
    """Return the `hook_main(...)` Call node inside `if __name__ == "__main__":`,
    or None if that block doesn't exist or doesn't call it.

    WHY an AST walk, not a text/substring scan (found during Gate 12a's own
    review, 2026-08-28): an earlier version of this check scanned raw source
    text from the LAST `if __name__ == "__main__":` line to EOF for the
    substrings "hook_main(" and "fail_closed=". That has a real false-negative
    hole -- ANY comment inside that block mentioning the string "fail_closed="
    (e.g. "# TODO: fail_closed= should probably be True here") makes the check
    pass even when the actual call is a bare `hook_main(main)` with no such
    argument. Confirmed live with a 3-line repro before this fix landed. AST
    parsing looks at the real keyword-argument list of the real Call node,
    which comments cannot influence.
    """
    for node in tree.body:
        if not (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.Eq)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value == "__main__"
        ):
            continue
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Name)
                    and sub.func.id == "hook_main"
                ):
                    return sub
    return None


def build_matrix() -> tuple[str, dict[str, int]]:
    registry_text = REGISTRY.read_text(encoding="utf-8")
    settings_text = SETTINGS.read_text(encoding="utf-8")
    entries = parse_registry(registry_text)
    wired = parse_wired(settings_text)

    rows = []
    counts = {"wired": 0, "dormant": 0, "library": 0, "orphaned": 0, "mismatch": 0}
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
        )
        + (
            f" · {counts['mismatch']} MISMATCH (class says dormant/library but "
            "hooks/settings.json shows it registered — registry.yaml's class field is stale)"
            if counts["mismatch"]
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
        # WHY this check is separate from the staleness check below (2026-08-27):
        # a mismatch is a bug in hooks/registry.yaml itself, not in the generated
        # doc. Someone could regenerate+commit the doc faithfully every time and
        # this check would still pass under the staleness test alone, silently
        # enshrining a stale `class: dormant`/`class: library` label as "correct"
        # forever. Fail on it unconditionally, regardless of doc staleness.
        if counts["mismatch"]:
            print(
                f"[gen_hook_matrix] {counts['mismatch']} MISMATCH entries in "
                f"{REGISTRY}: class says dormant/library but hooks/settings.json "
                "shows the hook registered. Fix the class field (see the row "
                "marked 'mismatch' after regenerating without --check).",
                file=sys.stderr,
            )
            return 1

        # WHY separate from the mismatch/staleness checks above (Gate 12a,
        # 2026-08-28): same reasoning as the mismatch check's own WHY --
        # this is a bug in the hooks/ source tree and hooks/registry.yaml
        # together, not in the generated doc. Fail on it unconditionally.
        entries = parse_registry(REGISTRY.read_text(encoding="utf-8"))
        wired = parse_wired(SETTINGS.read_text(encoding="utf-8"))
        prevent_errors = check_prevent_hooks_explicit_fail_closed(entries, wired)
        if prevent_errors:
            print(
                f"[gen_hook_matrix] Gate 12a: {len(prevent_errors)} PREVENT "
                "hook(s) don't call hook_main() with an explicit fail_closed=:",
                file=sys.stderr,
            )
            for e in prevent_errors:
                print(f"  - {e}", file=sys.stderr)
            return 1

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
