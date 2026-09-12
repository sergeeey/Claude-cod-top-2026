#!/usr/bin/env python3
"""Cycle 2 Part 1 — retrospective replay of the Cycle-1 gates over this repo's own history.

Run from the repo root:  python experiments/20260912-cycle2-retrospective-replay/replay.py

WHY this script instead of eyeballing the files: the whole claim is a COUNT, and a count
produced by reading twelve files by hand is exactly the kind of number that drifts between
the prose and the artifact (this repo has its own incident of that -- see the README badge
drift gate). It writes metrics/run.json so the numbers in decision.md can be diffed against
a machine-produced source rather than retyped.

It deliberately does NOT judge whether a firing would have been CORRECT -- that requires
reading what actually happened afterwards and is done by hand, per-artifact, in
decision.md. This script only answers "would the gate fire", never "should it have".
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))

OUT_DIR = Path(__file__).resolve().parent / "metrics"

# --- corpus -----------------------------------------------------------------


# This experiment's own folder. Excluded from its own corpus -- see SELF_EXCLUDE below.
SELF = Path(__file__).resolve().parent.name

# WHY self-exclusion is not optional (caught live, 2026-09-12, after the floor arm was
# added): the moment this experiment's own decision.md existed, it entered the corpus it
# measures. The count jumped 12 -> 13 artifacts and P4's relationship count 6 -> 12,
# purely because the report NAMES the experiments it discusses. Left in, every edit to
# the write-up would silently change the numbers the write-up reports -- a measurement
# feeding on its own output.
_EXCLUDED_DIRS = {"_template", SELF}


def decision_files() -> list[Path]:
    return sorted(
        p for p in ROOT.glob("experiments/*/decision.md") if p.parent.name not in _EXCLUDED_DIRS
    )


def template_decision() -> Path:
    """The negative control: must never fire."""
    return ROOT / "experiments" / "_template" / "decision.md"


def null_result_files() -> list[Path]:
    return sorted(p for p in ROOT.glob("null_results/*.md") if p.stem != "INDEX")


def parked_files() -> list[Path]:
    return sorted(p for p in ROOT.glob("parked/*.md") if p.stem != "INDEX")


# --- verdict extraction (prose -> schema, the Layer B mapping) ---------------

# WHY four patterns, not one (found by this replay's own first run, 2026-09-12): the
# corpus is NOT format-consistent. A single checkbox-shaped regex silently returned None
# for 6 of 12 artifacts, which made Layer B report "0 firings" that were really "0 files
# successfully parsed". The four observed forms:
#   1. `- [x] **REJECT**`            (the _template's own checkbox form)
#   2. `## Verdict: ARCHIVE (parked) — ...`
#   3. `## Decision: NEEDS-HUMAN (...)`
#   4. `**STATUS: RESOLVED**`        (bold status line, token not even in the FL vocabulary)
_VERDICT_PATTERNS = (
    re.compile(r"^\s*-?\s*\[[xX]\]\s*\*{0,2}\s*([A-Z][A-Z\-]{2,})", re.MULTILINE),
    re.compile(r"^#+\s*(?:Verdict|Decision)\s*:\s*\*{0,2}([A-Z][A-Z\-]{2,})", re.MULTILINE),
    re.compile(
        r"^\s*\*\*\s*(?:STATUS|Verdict|Final Status)\s*:\s*([A-Z][A-Z\-]{2,})", re.MULTILINE
    ),
    re.compile(r"^\s*(?:Verdict|Final Status)\s*:\s*\*{0,2}([A-Z][A-Z\-]{2,})", re.MULTILINE),
)

_VERDICT_TO_STATUS = {
    # Falsification-Ladder vocabulary proper
    "PROMOTE": "PROMOTED",
    "REPEAT": "ACTIVE",
    "REJECT": "KILLED",
    "ARCHIVE": "BLOCKED",
    "NEEDS-MORE-DATA": "ACTIVE",
    "SPLIT": "ACTIVE",
    # Tokens this corpus actually uses that are NOT in that vocabulary -- mapped here
    # explicitly rather than silently dropped, because "the corpus invented its own
    # verdict words" is itself one of this replay's findings.
    "RESOLVED": "PROMOTED",
    "CONFIRMED": "PROMOTED",
    "NEEDS-HUMAN": "BLOCKED",
}

_NON_STANDARD_VERDICTS = {"RESOLVED", "CONFIRMED", "NEEDS-HUMAN"}

# Tokens that look verdict-shaped to the regexes but are decoration, not a verdict.
_VERDICT_NOISE = {"DIAMOND", "GOLD", "SILVER", "STONE", "PASS", "FAIL", "YES", "NO"}


def extract_verdict(text: str) -> str | None:
    """Normalised verdict token, or None if no form matched.

    Returning None is meaningful and is COUNTED by the caller -- an unparsed file must
    never silently become a 'no firing' file (that is the exact false-negative this
    function's first version produced).
    """
    for pattern in _VERDICT_PATTERNS:
        for m in pattern.finditer(text):
            token = m.group(1).strip().rstrip("-").strip().upper()
            if token in _VERDICT_NOISE:
                continue
            for known in _VERDICT_TO_STATUS:
                if token.startswith(known):
                    return known
    return None


def _section(text: str, *heading_keywords: str) -> str:
    """Return the body of the first markdown section whose heading contains ALL
    the given keywords (case-insensitive). Empty string if absent."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("#"):
            continue
        heading = line.lower()
        if all(k.lower() in heading for k in heading_keywords):
            level = len(line) - len(line.lstrip("#").lstrip()) if False else line.count("#")
            body: list[str] = []
            for nxt in lines[i + 1 :]:
                if nxt.lstrip().startswith("#") and nxt.count("#") <= level:
                    break
                body.append(nxt)
            return "\n".join(body)
    return ""


_PLACEHOLDER_RE = re.compile(
    r"\bTODO\b|\bTBD\b|\bplaceholder\b|<[a-z_\- ]+>|^\s*-\s*$|^\s*\.\.\.\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def has_real_content(section_body: str) -> bool:
    """Non-empty after stripping markdown scaffolding, and not just a placeholder."""
    stripped = re.sub(r"[|\-\s>*_`]", "", section_body)
    if len(stripped) < 20:
        return False
    prose = section_body.strip()
    if _PLACEHOLDER_RE.search(prose) and len(stripped) < 80:
        return False
    return True


def map_to_graph_fields(text: str) -> dict:
    """Layer B: map an existing decision.md's prose into the graph.yaml schema
    fields the new check_status_conditional_fields() gate reads."""
    verdict = extract_verdict(text)
    status = _VERDICT_TO_STATUS.get(verdict or "", None)

    kill_body = _section(text, "kill", "analysis") or _section(text, "kill")
    revival_body = (
        _section(text, "revival")
        or _section(text, "relaxation", "map")
        or _section(text, "what changes next")
    )
    return {
        "verdict": verdict,
        "status": status,
        "kill_reason": kill_body.strip() if has_real_content(kill_body) else None,
        "revival_condition": revival_body.strip() if has_real_content(revival_body) else None,
    }


# --- Layer A: gates exactly as they ship ------------------------------------


def layer_a() -> dict:
    """Run the gates as actually shipped, against real on-disk state."""
    import promotion_gate_guard as pgg

    results = []
    for d in decision_files():
        exp_dir = d.parent
        passed, detail = pgg._check_sealed_holdout(exp_dir)
        results.append(
            {
                "experiment": exp_dir.name,
                "has_graph_yaml": (exp_dir / "graph.yaml").exists(),
                "has_sealed_holdout": (exp_dir / "sealed_holdout.yaml").exists(),
                "sealed_holdout_gate_fires": not passed,
                "sealed_holdout_detail": detail,
            }
        )
    return {
        "artifacts_checked": len(results),
        "sealed_holdout_firings": sum(1 for r in results if r["sealed_holdout_gate_fires"]),
        "artifacts_with_graph_yaml": sum(1 for r in results if r["has_graph_yaml"]),
        "artifacts_with_sealed_holdout": sum(1 for r in results if r["has_sealed_holdout"]),
        "per_artifact": results,
    }


# --- Layer B: counterfactual schema-fill ------------------------------------


def layer_b() -> dict:
    """Map each historical decision.md's prose into the new schema, then apply the
    same conditional-requiredness rule check_status_conditional_fields() enforces."""
    results = []
    for d in decision_files():
        text = d.read_text(encoding="utf-8", errors="replace")
        fields = map_to_graph_fields(text)
        status = fields["status"]
        flags = []
        if status == "KILLED" and not fields["kill_reason"]:
            flags.append("kill_reason missing/empty")
        if status in ("KILLED", "BLOCKED") and not fields["revival_condition"]:
            flags.append("revival_condition missing/empty")
        results.append(
            {
                "experiment": d.parent.name,
                "verdict": fields["verdict"],
                "verdict_is_non_standard": fields["verdict"] in _NON_STANDARD_VERDICTS,
                "mapped_status": status,
                "kill_reason_present": bool(fields["kill_reason"]),
                "revival_condition_present": bool(fields["revival_condition"]),
                "flags": flags,
                "fires": bool(flags),
                "unparsed": status is None,
            }
        )

    killed_or_blocked = [r for r in results if r["mapped_status"] in ("KILLED", "BLOCKED")]
    unparsed = [r for r in results if r["unparsed"]]
    return {
        "artifacts_checked": len(results),
        # WHY reported separately and prominently: an unparsed artifact is NOT a "clean"
        # artifact. Collapsing the two is how this script's own first run produced a
        # 0/12 that looked like a finding and was really a parser failure on 6 files.
        "unparsed_count": len(unparsed),
        "unparsed_artifacts": [r["experiment"] for r in unparsed],
        "non_standard_verdict_count": sum(1 for r in results if r["verdict_is_non_standard"]),
        "non_standard_verdicts": {
            r["experiment"]: r["verdict"] for r in results if r["verdict_is_non_standard"]
        },
        "killed_or_blocked_count": len(killed_or_blocked),
        "firings": sum(1 for r in results if r["fires"]),
        "firings_among_killed_or_blocked": sum(1 for r in killed_or_blocked if r["fires"]),
        "per_artifact": results,
    }


# --- P3: sealed-holdout retrospective evaluability ---------------------------

_DELTA_MENTION_RE = re.compile(r"\b(internal_delta|held_out_delta|held-out delta)\b", re.IGNORECASE)
# A RECORDED delta is a field name followed by an actual number -- `internal_delta: 0.05`.
# WHY this distinction is load-bearing (caught on this script's own first run): the only
# hit for the loose pattern was Cycle 1's own decision.md, which *describes* the gate and
# therefore contains the field NAMES in prose. Counting that as "a historical artifact
# records a delta" would be this repo's own [AVOID x7] pattern -- a keyword match treated
# as an assertion -- committed by the very script meant to measure rigour.
_DELTA_RECORD_RE = re.compile(
    r"\b(internal_delta|held_out_delta)\b\s*[:=]\s*[-+]?\d*\.?\d+", re.IGNORECASE
)


def p3_holdout_evaluability() -> dict:
    """Does ANY historical artifact RECORD both an internal and a held-out delta
    in a form the invariant could actually evaluate (name + number), as opposed to
    merely mentioning the field names in prose?"""
    mentions, records = [], []
    corpus = decision_files() + null_result_files() + parked_files()
    for p in corpus:
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if _DELTA_MENTION_RE.search(text):
            mentions.append(rel)
        found = {m.group(1).lower() for m in _DELTA_RECORD_RE.finditer(text)}
        if {"internal_delta", "held_out_delta"} <= found:
            records.append(rel)
    return {
        "corpus_size": len(corpus),
        "artifacts_mentioning_a_delta_field": mentions,
        "artifacts_actually_recording_both_deltas": records,
        "evaluable_invariant_checks": len(records),
    }


# --- P4: DAG dead-end-detection retrospective power --------------------------

_EXP_ID_RE = re.compile(r"\b(20\d{6}-[a-z0-9][a-z0-9\-]{3,})\b")


def p4_cross_experiment_relationships() -> dict:
    """How many cross-experiment relationships exist in decision.md prose that the
    human-curated experiments/INDEX.md does NOT already record? Those are the only
    ones a machine-readable DAG could have surfaced that the existing grep-the-INDEX
    protocol could not."""
    index_path = ROOT / "experiments" / "INDEX.md"
    index_text = (
        index_path.read_text(encoding="utf-8", errors="replace") if index_path.exists() else ""
    )
    known_ids = {p.name for p in (ROOT / "experiments").iterdir() if p.is_dir()}

    relationships, unrecorded = [], []
    for d in decision_files():
        own_id = d.parent.name
        text = d.read_text(encoding="utf-8", errors="replace")
        referenced = {m.group(1) for m in _EXP_ID_RE.finditer(text)} & known_ids
        referenced.discard(own_id)
        for target in sorted(referenced):
            rel = {"from": own_id, "to": target}
            relationships.append(rel)
            # "recorded" = both ids appear in INDEX.md, i.e. the existing prose index
            # already lets a human connect them by grepping it.
            if not (own_id in index_text and target in index_text):
                unrecorded.append(rel)
    return {
        "relationships_found_in_prose": relationships,
        "relationship_count": len(relationships),
        "unrecorded_in_INDEX": unrecorded,
        "unrecorded_count": len(unrecorded),
    }


# --- FLOOR: what the PRE-Cycle-1 machinery already catches --------------------


def floor_pre_existing_gate() -> dict:
    """FL Step 4a floor arm — "mechanism removed".

    `hooks/reject_gate_guard.py` has enforced Kill-Analysis completeness on REJECT
    decision.md files since 2026-06-24, i.e. BEFORE Cycle 1 existed. If it already
    flags the same records Layer B flags, Cycle 1's check_status_conditional_fields
    adds nothing on this corpus and the Layer B count is not headroom -- it is the
    floor being re-measured under a new name.
    """
    import reject_gate_guard as rgg

    results = []
    for d in decision_files():
        text = d.read_text(encoding="utf-8", errors="replace")
        applies = rgg._has_reject(text)
        failed: list[str] = []
        if applies:
            for name, fn in (
                ("what_killed", rgg._check_what_killed),
                ("what_survived", rgg._check_what_survived),
                ("relaxation_map", rgg._check_relaxation_map),
                ("reason_specific", rgg._check_reason_specific),
            ):
                ok, _detail = fn(text)
                if not ok:
                    failed.append(name)
        results.append(
            {
                "experiment": d.parent.name,
                "pre_existing_gate_applies": applies,
                "pre_existing_gate_failures": failed,
                "fires": bool(failed),
            }
        )
    return {
        "artifacts_checked": len(results),
        "gate_applies_to": sum(1 for r in results if r["pre_existing_gate_applies"]),
        "firings": sum(1 for r in results if r["fires"]),
        "firing_artifacts": [r["experiment"] for r in results if r["fires"]],
        "per_artifact": results,
    }


# --- negative / positive controls -------------------------------------------


def controls() -> dict:
    import promotion_gate_guard as pgg

    tmpl = template_decision()
    tmpl_text = tmpl.read_text(encoding="utf-8", errors="replace")
    tmpl_fields = map_to_graph_fields(tmpl_text)
    tmpl_layer_b_fires = bool(
        (tmpl_fields["status"] == "KILLED" and not tmpl_fields["kill_reason"])
        or (tmpl_fields["status"] in ("KILLED", "BLOCKED") and not tmpl_fields["revival_condition"])
    )
    tmpl_passed, tmpl_detail = pgg._check_sealed_holdout(tmpl.parent)

    pos = ROOT / "experiments" / "20260728-osa-fl-protocol-vs-standard-analysis" / "decision.md"
    pos_fields = map_to_graph_fields(pos.read_text(encoding="utf-8", errors="replace"))
    pos_fires = bool(
        (pos_fields["status"] == "KILLED" and not pos_fields["kill_reason"])
        or (pos_fields["status"] in ("KILLED", "BLOCKED") and not pos_fields["revival_condition"])
    )

    return {
        "negative_control_template": {
            "layer_a_fires": not tmpl_passed,
            "layer_a_detail": tmpl_detail,
            "layer_b_fires": tmpl_layer_b_fires,
            "mapped_status": tmpl_fields["status"],
            "PASS": (tmpl_passed and not tmpl_layer_b_fires),
        },
        "positive_control_known_good_reject": {
            "experiment": pos.parent.name,
            "mapped_status": pos_fields["status"],
            "kill_reason_present": bool(pos_fields["kill_reason"]),
            "revival_condition_present": bool(pos_fields["revival_condition"]),
            "layer_b_fires": pos_fires,
            "PASS": not pos_fires,
        },
    }


def main() -> int:
    out = {
        "generated_by": "experiments/20260912-cycle2-retrospective-replay/replay.py",
        "corpus": {
            "decision_files": len(decision_files()),
            "null_results": len(null_result_files()),
            "parked": len(parked_files()),
        },
        "layer_a_gates_as_shipped": layer_a(),
        "layer_b_counterfactual_schema_fill": layer_b(),
        "p3_sealed_holdout_evaluability": p3_holdout_evaluability(),
        "p4_cross_experiment_relationships": p4_cross_experiment_relationships(),
        "floor_pre_existing_gate": floor_pre_existing_gate(),
        "controls": controls(),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "run.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    a = out["layer_a_gates_as_shipped"]
    b = out["layer_b_counterfactual_schema_fill"]
    p3 = out["p3_sealed_holdout_evaluability"]
    c = out["controls"]
    print(f"corpus: {out['corpus']}")
    print(
        f"LAYER A  sealed-holdout firings: {a['sealed_holdout_firings']}/{a['artifacts_checked']}"
        f"   (with graph.yaml: {a['artifacts_with_graph_yaml']},"
        f" with sealed_holdout.yaml: {a['artifacts_with_sealed_holdout']})"
    )
    print(
        f"LAYER B  firings: {b['firings']}/{b['artifacts_checked']}"
        f"   among KILLED/BLOCKED: {b['firings_among_killed_or_blocked']}/"
        f"{b['killed_or_blocked_count']}"
    )
    print(
        f"         UNPARSED (not 'clean' -- excluded from the denominator above):"
        f" {b['unparsed_count']}/{b['artifacts_checked']} {b['unparsed_artifacts']}"
    )
    print(
        f"         non-standard verdict tokens: {b['non_standard_verdict_count']}"
        f" {b['non_standard_verdicts']}"
    )
    print(f"P3       evaluable invariant checks: {p3['evaluable_invariant_checks']}")
    p4 = out["p4_cross_experiment_relationships"]
    print(
        f"P4       cross-experiment relationships in prose: {p4['relationship_count']}"
        f"   NOT already recorded in INDEX.md: {p4['unrecorded_count']}"
    )
    fl = out["floor_pre_existing_gate"]
    print(
        f"FLOOR    pre-Cycle-1 reject_gate_guard fires: {fl['firings']}/{fl['artifacts_checked']}"
        f"   (applies to {fl['gate_applies_to']}) {fl['firing_artifacts']}"
    )
    print(
        f"CONTROLS negative(_template) PASS={c['negative_control_template']['PASS']}  "
        f"positive(known-good REJECT) PASS="
        f"{c['positive_control_known_good_reject']['PASS']}"
    )
    print(f"\nwrote {OUT_DIR / 'run.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
