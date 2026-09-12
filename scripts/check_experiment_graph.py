#!/usr/bin/env python3
"""Cross-experiment dependency-graph checker for OPTIONAL experiments/<id>/graph.yaml
and experiments/<id>/sealed_holdout.yaml files.

WHY this script exists: experiments/_template/decision.md already tracks branch-level
state in prose (Hypothesis Generation Mode's table, Rescue Review's Final Status) --
but nothing lets a script ask "what's ACTIVE right now?", "what does killing X
unblock?", or "does this depend on something that doesn't exist?" across the whole
experiments/ tree. This is the minimal, additive answer -- an experiment WITHOUT a
graph.yaml is simply not part of the graph, not an error.

Reuses scripts/check_architecture.py's own generic machinery directly (same
stdlib-only JSON-Schema subset, same cycle detector) rather than reimplementing it --
both files live in scripts/, so the import needs no path setup.

Checks:
  1. Every graph.yaml validates against experiments/graph.schema.json.
  2. The `requires`+`blocks`+`parent_ids` dependency graph (edge X -> Y means
     "X depends on Y") is acyclic.
  3. No dangling reference: every id in requires/blocks/parent_ids must be a real
     experiments/<id>/ directory; every id in evidence_for/evidence_against must be
     a real experiment OR a real null_results/parked entry (prefix match on the
     established <YYYYMMDD>-<slug> filename convention).
  4. Every path in artifact_refs exists relative to that experiment's own directory.
  5. Every sealed_holdout.yaml (if present) is structurally valid: `holdout_ref`
     does not look like inlined data; `consumed: true` requires a non-null
     `opened_at`.
  6. status=KILLED requires a non-null kill_reason; status=KILLED or BLOCKED
     requires a non-null revival_condition (conditional-requiredness the
     schema's own field descriptions document but cannot enforce structurally).

Usage:
    python scripts/check_experiment_graph.py            # human report, exit 0/1
    python scripts/check_experiment_graph.py --check     # CI mode, quiet on success
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - PyYAML is a pinned CI dep
    print("ERROR: PyYAML is required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)

from check_architecture import _find_cycle, validate_against_schema  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS_DIR = ROOT / "experiments"
GRAPH_SCHEMA_PATH = ROOT / "experiments" / "graph.schema.json"

# WHY a value shaped like this is rejected for holdout_ref (leakage guard): a real
# reference is short (a hash or a path), not a long literal blob. This is a coarse,
# deliberately cheap heuristic -- it cannot detect a SHORT secret pasted inline, only
# an obviously-too-long value that looks like actual data rather than a pointer to it.
_MAX_HOLDOUT_REF_LEN = 200
# Positive shape check, run IN ADDITION to the length ceiling above (sec-auditor-
# found, 2026-09-12): "sha256:<64 hex>" or a path-shaped token (letters/digits/
# common path separators, no whitespace or quote characters). Still a shape
# guard, not a secret scanner -- see check_sealed_holdouts()'s own WHY comment.
_HOLDOUT_REF_SHAPE_RE = re.compile(r"^(sha256:[0-9a-f]{64}|[A-Za-z0-9_][A-Za-z0-9_./\\:-]{0,199})$")


def _load_yaml(p: Path) -> Any:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _load_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(GRAPH_SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema


def _experiment_ids() -> set[str]:
    if not EXPERIMENTS_DIR.exists():
        return set()
    return {
        p.name for p in EXPERIMENTS_DIR.iterdir() if p.is_dir() and p.name not in ("_template",)
    }


def _null_or_parked_ids() -> set[str]:
    """Prefix ids from null_results/*.md and parked/*.md (excluding INDEX.md),
    per the established <YYYYMMDD>-<slug>.md convention -- the id is the leading
    <YYYYMMDD>-<short-token> portion, not the whole filename."""
    ids: set[str] = set()
    for dirname in ("null_results", "parked"):
        d = ROOT / dirname
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            if p.stem == "INDEX":
                continue
            ids.add(p.stem)
    return ids


def discover_graph_files() -> list[Path]:
    if not EXPERIMENTS_DIR.exists():
        return []
    return sorted(p for p in EXPERIMENTS_DIR.glob("*/graph.yaml") if p.parent.name != "_template")


def discover_sealed_holdout_files() -> list[Path]:
    if not EXPERIMENTS_DIR.exists():
        return []
    return sorted(
        p for p in EXPERIMENTS_DIR.glob("*/sealed_holdout.yaml") if p.parent.name != "_template"
    )


def validate_schema_for_all(graph_files: list[Path]) -> list[str]:
    schema = _load_schema()
    errors: list[str] = []
    for gf in graph_files:
        try:
            data = _load_yaml(gf) or {}
        except yaml.YAMLError as e:
            errors.append(f"{gf}: unparsable YAML: {e}")
            continue
        for err in validate_against_schema(data, schema):
            errors.append(f"{gf}: {err}")
    return errors


def build_dependency_graph(graph_files: list[Path]) -> dict[str, set[str]]:
    """Edge X -> Y means 'X depends on Y' (Y must complete first).
    requires: A requires B => A -> B.
    blocks:   A blocks C   => C depends on A => C -> A.
    parent_ids: A's parent P => A -> P (a branch can't depend on its own descendant).
    """
    graph: dict[str, set[str]] = {}
    for gf in graph_files:
        try:
            data = _load_yaml(gf) or {}
        except yaml.YAMLError:
            continue
        this_id = data.get("id") or gf.parent.name
        graph.setdefault(this_id, set())
        for target in data.get("requires") or []:
            graph[this_id].add(target)
        for target in data.get("blocks") or []:
            graph.setdefault(target, set())
            graph[target].add(this_id)
        for parent in data.get("parent_ids") or []:
            graph[this_id].add(parent)
    return graph


def check_acyclic(graph_files: list[Path]) -> list[str]:
    graph = build_dependency_graph(graph_files)
    cycle = _find_cycle(graph)
    if cycle:
        return ["experiment dependency graph has a cycle: " + " -> ".join(cycle)]
    return []


def check_status_conditional_fields(graph_files: list[Path]) -> list[str]:
    """Enforce the conditional-requiredness rules graph.schema.json's field
    descriptions document but cannot express structurally.

    WHY a separate Python check, not a schema fix (Codex P2 finding, 2026-09-12):
    `kill_reason`/`revival_condition` are typed `["string", "null"]` because they are
    legitimately null for most statuses -- the requiredness is conditional on `status`,
    and this project's schema validator is a deliberate stdlib-only JSON-Schema SUBSET
    (type/required/enum/items only) with no if/then/else support.

    WHICH FIELD IS REQUIRED FOR WHICH STATUS, derived from the Rescue Review rules in
    `experiments/_template/decision.md` and `falsification-ladder.md` -- NOT chosen by
    symmetry:

        hard_killed  "outside Rescue scope; only new theorem-level input can change it"
                     -> a stated revival condition is not merely optional, it is
                        meaningless: revival needs a new theorem, not a trigger
        killed       "formulation falsified; NEW BRANCH allowed (Minimal Relaxation
                     Rule applies)" -> the path forward is a new experiment with its own
                        id via the Relaxation Map, NOT a revival of this one
        parked       "Revival Condition required"        <- explicit in the rules
        weak_alive   "... + Revival Condition + ..."     <- explicit in the rules

    The template's own crosswalk maps hard_killed/killed -> KILLED and parked -> BLOCKED.
    So the rules require `revival_condition` for BLOCKED, and do NOT require it for
    KILLED.

    CORRECTION (PR C, measured by `experiments/20260912-cycle2-retrospective-replay/`):
    the first version of this check demanded `revival_condition` for KILLED as well --
    exactly backwards for the KILLED family. On the real corpus that produced two false
    demands against `20260824-elai-hooks-skeptic-pilot` and
    `20260824-permission-policy-skeptic-pilot`, both of which are "claim falsified AND
    the underlying defect fixed" records: they carry substantial Kill Analysis and have
    nothing to revive, because the claim was retired rather than parked. Demanding a
    revival condition there would have forced authors to invent a fictitious
    resurrection trigger to satisfy a checker -- worse than the gap it was closing.

    KNOWN LIMITATION, recorded rather than silently accepted: `weak_alive` also requires
    a Revival Condition per the rules, but it crosswalks to `ACTIVE`, which equally
    covers an ordinary running experiment that has never been through a Rescue Review.
    Demanding the field for all ACTIVE would fire on every healthy in-flight experiment,
    so it is not demanded at all. That is a consequence of one `status` field carrying
    two different questions -- see docs/experiment-dependency-graph.md.
    """
    errors: list[str] = []
    for gf in graph_files:
        try:
            data = _load_yaml(gf) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        status = data.get("status")
        if status == "KILLED" and not data.get("kill_reason"):
            errors.append(f"{gf}: status=KILLED but kill_reason is null/missing/empty")
        if status == "BLOCKED" and not data.get("revival_condition"):
            errors.append(
                f"{gf}: status=BLOCKED (parked) but revival_condition is "
                "null/missing/empty -- the Rescue Review rules require one for a parked "
                "branch"
            )
    return errors


def check_dangling_references(graph_files: list[Path]) -> list[str]:
    errors: list[str] = []
    experiment_ids = _experiment_ids()
    evidence_targets = experiment_ids | _null_or_parked_ids()

    for gf in graph_files:
        try:
            data = _load_yaml(gf) or {}
        except yaml.YAMLError:
            continue

        for field in ("requires", "blocks", "parent_ids"):
            for target in data.get(field) or []:
                if target not in experiment_ids:
                    errors.append(
                        f"{gf}: {field} references '{target}' which is not a real "
                        "experiments/<id>/ directory"
                    )

        for field in ("evidence_for", "evidence_against"):
            for target in data.get(field) or []:
                if target not in evidence_targets:
                    errors.append(
                        f"{gf}: {field} references '{target}' which is not a real "
                        "experiment, null_results, or parked entry"
                    )

        exp_dir = gf.parent
        for artifact in data.get("artifact_refs") or []:
            # WHY reject absolute/traversal shapes BEFORE checking existence
            # (sec-auditor-found, 2026-09-12): `(exp_dir / artifact)` silently
            # escapes exp_dir for an absolute path or a `../../..` shape,
            # contradicting the schema's own "inside this experiment's own
            # directory" description (experiments/graph.schema.json's
            # artifact_refs field). Checked via resolved-path containment,
            # not a string prefix check, so a mid-path `..` that still
            # resolves back inside exp_dir isn't falsely rejected.
            if Path(artifact).is_absolute():
                errors.append(
                    f"{gf}: artifact_refs entry '{artifact}' is an absolute path -- must be "
                    "relative to this experiment's own directory"
                )
                continue
            resolved = (exp_dir / artifact).resolve()
            try:
                resolved.relative_to(exp_dir.resolve())
            except ValueError:
                errors.append(
                    f"{gf}: artifact_refs entry '{artifact}' resolves outside this "
                    "experiment's own directory"
                )
                continue
            if not resolved.exists():
                errors.append(f"{gf}: artifact_refs entry '{artifact}' does not exist")

        declared_id = data.get("id")
        if declared_id and declared_id != gf.parent.name:
            errors.append(
                f"{gf}: id field '{declared_id}' does not match its own folder name "
                f"'{gf.parent.name}'"
            )
    return errors


def check_sealed_holdouts(holdout_files: list[Path]) -> list[str]:
    errors: list[str] = []
    for hf in holdout_files:
        try:
            data = _load_yaml(hf) or {}
        except yaml.YAMLError as e:
            errors.append(f"{hf}: unparsable YAML: {e}")
            continue

        holdout_ref = data.get("holdout_ref")
        if holdout_ref is not None:
            ref_str = str(holdout_ref)
            if len(ref_str) > _MAX_HOLDOUT_REF_LEN:
                errors.append(
                    f"{hf}: holdout_ref is {len(ref_str)} chars -- looks like inlined "
                    "data, not a hash/path reference (max allowed: "
                    f"{_MAX_HOLDOUT_REF_LEN}). Never store raw held-out data in this file."
                )
            elif not _HOLDOUT_REF_SHAPE_RE.match(ref_str):
                # WHY a positive shape check IN ADDITION to the length ceiling
                # (sec-auditor-found, 2026-09-12): a length ceiling can only
                # reject obviously-long blobs -- it cannot tell a 40-char API
                # key from a 40-char hash. This is still a SHAPE guard, not a
                # secret scanner: it cannot distinguish a real hash from a
                # real secret of the same shape. Documented limitation, not a
                # claim of leak prevention -- route anything more sensitive
                # through this repo's own hooks/redact.py patterns instead.
                errors.append(
                    f"{hf}: holdout_ref {ref_str!r} does not look like a reference "
                    "('sha256:<64 hex>' or a path-shaped string) -- this is a shape "
                    "check, not a secret scanner, but an unusual shape here is worth "
                    "a second look before assuming it's safe to commit."
                )

        if data.get("consumed") is True and not data.get("opened_at"):
            errors.append(
                f"{hf}: consumed=true but opened_at is not set -- structurally invalid "
                "consumption (a holdout can only be consumed by being opened)"
            )
    return errors


INDEX_PATH = EXPERIMENTS_DIR / "INDEX.md"


def _experiment_dirs() -> list[str]:
    """Every directory under experiments/ that is a real experiment.

    `_template` is scaffolding, not an experiment, and is excluded here exactly as it
    is from every other discovery function in this file.
    """
    if not EXPERIMENTS_DIR.exists():
        return []
    return sorted(p.name for p in EXPERIMENTS_DIR.iterdir() if p.is_dir() and p.name != "_template")


def _indexed_ids(index_text: str) -> list[str]:
    """Ids listed in INDEX.md's markdown table, in file order (duplicates kept).

    The id is the first cell of each data row. Header and separator rows are skipped,
    and the `_template` row -- which the index does carry as a convenience -- is not
    treated as an experiment.
    """
    ids: list[str] = []
    for line in index_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        first = cells[0].strip("`").strip()
        if not first or first.lower() == "id" or set(first) <= set("-: "):
            continue
        if first == "_template":
            continue
        ids.append(first)
    return ids


def check_index_integrity() -> list[str]:
    """An experiment that exists must be discoverable.

    WHY this invariant, and why a checker rather than adding the missing rows by hand
    (measured in `experiments/20260912-cycle2-retrospective-replay/`, PR #446): the
    established protocol for avoiding repeated dead ends is "grep INDEX.md before
    starting work", which can only ever surface what somebody remembered to index. On
    this repository's own history that left FIVE experiments invisible to it -- including
    the experiment of the very cycle that built the dependency graph, and the experiment
    of the cycle that measured the gap. Hand-adding the rows fixes today's list and
    leaves tomorrow's to memory again.

    This is deliberately the same invariant CI's own "Registry <-> disk consistency
    gate" already enforces for skills (orphan / ghost detection, added after 7 skills
    landed on disk without registry entries). Extending a proven gate to experiments,
    not inventing a mechanism.

    WHY Python rather than the bash+`comm` shape that gate uses: INDEX.md is a markdown
    TABLE, and this repository has already been bitten once by a CI step computing a
    doc-count with a flat `ls` (see the README metric gate's own history). A table
    parser belongs in something unit-testable.

    Detects, in both directions:
      orphan     a directory under experiments/ with no INDEX.md row
      stale      an INDEX.md row naming a directory that does not exist
      duplicate  the same id appearing in more than one row
    """
    errors: list[str] = []
    if not INDEX_PATH.exists():
        return [f"{INDEX_PATH} is missing -- the experiments index is the discovery surface"]

    try:
        index_text = INDEX_PATH.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{INDEX_PATH}: unreadable ({e})"]

    on_disk = _experiment_dirs()
    indexed = _indexed_ids(index_text)
    indexed_set = set(indexed)

    for exp_id in on_disk:
        if exp_id not in indexed_set:
            errors.append(
                f"orphan experiment: experiments/{exp_id}/ exists but has no row in "
                "experiments/INDEX.md -- it is invisible to the grep-the-index protocol"
            )

    disk_set = set(on_disk)
    for exp_id in sorted(indexed_set):
        if exp_id not in disk_set:
            errors.append(
                f"stale index entry: experiments/INDEX.md lists '{exp_id}' but "
                "experiments/{exp_id}/ does not exist"
            )

    for exp_id in sorted({i for i in indexed if indexed.count(i) > 1}):
        errors.append(f"duplicate index entry: '{exp_id}' appears more than once in INDEX.md")

    return errors


def run_all() -> tuple[list[str], int, int]:
    """Return (errors, n_graph_files, n_holdout_files)."""
    graph_files = discover_graph_files()
    holdout_files = discover_sealed_holdout_files()
    errors: list[str] = []
    errors.extend(validate_schema_for_all(graph_files))
    errors.extend(check_acyclic(graph_files))
    errors.extend(check_status_conditional_fields(graph_files))
    errors.extend(check_dangling_references(graph_files))
    errors.extend(check_sealed_holdouts(holdout_files))
    errors.extend(check_index_integrity())
    return errors, len(graph_files), len(holdout_files)


def main() -> int:
    check_mode = "--check" in sys.argv
    errors, n_graphs, n_holdouts = run_all()

    if errors:
        for e in errors:
            print(f"[check-experiment-graph] ERROR: {e}", file=sys.stderr)
        return 1

    if not check_mode:
        print(
            f"[check-experiment-graph] OK -- {n_graphs} graph.yaml, "
            f"{n_holdouts} sealed_holdout.yaml validated, no cycles, no dangling refs; "
            f"{len(_experiment_dirs())} experiments all present in INDEX.md."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
