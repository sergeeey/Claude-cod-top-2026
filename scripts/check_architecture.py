#!/usr/bin/env python3
"""Executable architectural-coherence checker (fitness function).

Validates that the declared architecture is machine-consistent:
  1. every `capability:` block in skills/registry.yaml matches architecture/capability.schema.json
  2. every workflow step names a real skill AND a capability that skill actually `provides`
  3. the data-flow `requires` graph over capabilities is acyclic
  4. no dangling provider: every token that is `requires`d, or referenced by a workflow step or
     completion clause, is provided/produced by some skill (no orphan reference)
  5. every Yellow/Red/Black workflow declares a verifier AND a human_checkpoint
  6. every workflow's steps/verifier resolve to a skill that exists on disk (registry <-> disk)
  7. every workflow has a non-empty termination_condition

Design notes:
  - stdlib + PyYAML only (no jsonschema): CI installs exactly the requirements.txt pins.
    A minimal JSON-Schema subset validator lives in `validate_against_schema`.
  - Acyclicity (gate 3) runs over `requires` ONLY. `verification_required` is a back-reference
    to a verifier (skeptic verifies X, and skeptic also consumes X's downstream) and would
    create false cycles; `depends_on` is load-order, a separate concern already gated elsewhere.
  - Any scoring is additive-normalized by construction here (we do not multiply criticality
    factors) -- a single zero factor must never zero out a rare-but-catastrophic dependency.

Usage:
    python scripts/check_architecture.py            # human report, exit 0/1
    python scripts/check_architecture.py --check     # CI mode, quiet on success, exit 0/1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]  # types-PyYAML intentionally not a dep
except ImportError:  # pragma: no cover - PyYAML is a pinned CI dep
    print("ERROR: PyYAML is required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "skills" / "registry.yaml"
CAP_SCHEMA = ROOT / "architecture" / "capability.schema.json"
WF_SCHEMA = ROOT / "architecture" / "workflow.schema.json"
WF_DIR = ROOT / "architecture" / "workflows"

# Process gates that are NOT skills (see TestRegistryCapabilitySchema in tests/test_structure.py).
PROCESS_GATES = {"source_trace", "safety_floor_check", "at_least_one_kill_test"}
# Reserved workflow completion tokens satisfied by structure, not by a step's `produces`.
RESERVED_COMPLETION_TOKENS = {"memory_destination"}
RISK_TIERS_NEEDING_CHECKPOINT = {"Yellow", "Red", "Black"}


# --------------------------------------------------------------------------- schema validation
def validate_against_schema(obj: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    """Validate `obj` against a JSON-Schema SUBSET (type, enum, required, properties, items,
    minItems). Returns a list of human-readable violations (empty = valid)."""
    errors: list[str] = []
    at = path or "<root>"

    # Normalize `type` to a list once so every branch below handles unions like
    # ["array", "null"] correctly -- NOT just the top-level `_type_ok` check.
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected is not None else []
    if expected is not None and not _type_ok(obj, types):
        errors.append(f"{at}: expected type {types}, got {type(obj).__name__}")
        return errors  # further checks assume the type held

    if "enum" in schema and obj not in schema["enum"]:
        errors.append(f"{at}: {obj!r} not in allowed {schema['enum']}")

    if "object" in types and isinstance(obj, dict):
        for req in schema.get("required", []):
            if req not in obj:
                errors.append(f"{at}: missing required key '{req}'")
        props = schema.get("properties", {})
        for key, subschema in props.items():
            if key in obj:
                errors.extend(validate_against_schema(obj[key], subschema, f"{at}.{key}"))

    if "array" in types and isinstance(obj, list):
        if "minItems" in schema and len(obj) < schema["minItems"]:
            errors.append(f"{at}: needs >= {schema['minItems']} items, got {len(obj)}")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(obj):
                errors.extend(validate_against_schema(item, item_schema, f"{at}[{i}]"))

    return errors


def _type_ok(obj: Any, types: list[str]) -> bool:
    checks = {
        "object": lambda o: isinstance(o, dict),
        "array": lambda o: isinstance(o, list),
        "string": lambda o: isinstance(o, str),
        "number": lambda o: isinstance(o, (int, float)) and not isinstance(o, bool),
        "integer": lambda o: isinstance(o, int) and not isinstance(o, bool),
        "boolean": lambda o: isinstance(o, bool),
        "null": lambda o: o is None,
    }
    return any(checks.get(t, lambda _o: False)(obj) for t in types)


# --------------------------------------------------------------------------- loading
def _load_yaml(p: Path) -> Any:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def iter_skills(registry: dict[str, Any]):
    """Yield every skill dict across core/extensions/community sections."""
    for items in registry.values():
        if isinstance(items, list):
            for skill in items:
                if isinstance(skill, dict) and "name" in skill:
                    yield skill


def build_capability_index(registry: dict[str, Any]) -> dict[str, str]:
    """Map every provided/produced capability token -> the skill name that yields it.

    First writer wins on duplicate tokens (setdefault). Token providers are expected unique;
    a duplicate only affects which provider an acyclicity edge points at, not existence checks.
    """
    index: dict[str, str] = {}
    for skill in iter_skills(registry):
        cap = skill.get("capability") or {}
        for token in list(cap.get("provides", [])) + list(cap.get("produces", [])):
            index.setdefault(token, skill["name"])
    return index


def build_provider_index(registry: dict[str, Any]) -> dict[str, set[str]]:
    """Map every provided/produced token -> the SET of skills that yield it.

    Unlike build_capability_index (first-writer-wins, for existence checks), this keeps ALL
    providers so the acyclicity gate can edge to every one -- a token produced by two skills
    must never let a cycle through the second provider hide behind the first.
    """
    index: dict[str, set[str]] = {}
    for skill in iter_skills(registry):
        cap = skill.get("capability") or {}
        for token in list(cap.get("provides", [])) + list(cap.get("produces", [])):
            index.setdefault(token, set()).add(skill["name"])
    return index


# --------------------------------------------------------------------------- gates
def gate_capability_schema(registry: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for skill in iter_skills(registry):
        if "capability" in skill:
            where = f"{skill['name']}.capability"
            errors.extend(validate_against_schema(skill["capability"], schema, where))
    return errors


def gate_requires_acyclic(registry: dict[str, Any]) -> list[str]:
    """Gate 3: the data-flow `requires` graph (consumer -> provider skill) is acyclic."""
    providers = build_provider_index(registry)
    graph: dict[str, set[str]] = {}
    errors: list[str] = []
    for skill in iter_skills(registry):
        cap = skill.get("capability") or {}
        name = skill["name"]
        graph.setdefault(name, set())
        for token in cap.get("requires", []):
            # Edge to EVERY provider of the token (not just the first) so a duplicate
            # producer can't hide a cycle. Dangling tokens are reported by gate 4.
            for provider in providers.get(token, ()):
                if provider != name:
                    graph[name].add(provider)

    cycle = _find_cycle(graph)
    if cycle:
        errors.append("requires-graph has a cycle: " + " -> ".join(cycle))
    return errors


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)
    stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        color[node] = GREY
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            if color.get(nxt, WHITE) == GREY:
                return stack[stack.index(nxt):] + [nxt]
            if color.get(nxt, WHITE) == WHITE:
                found = dfs(nxt)
                if found:
                    return found
        color[node] = BLACK
        stack.pop()
        return None

    for start in sorted(graph):
        if color[start] == WHITE:
            found = dfs(start)
            if found:
                return found
    return None


def gate_dangling_references(
    registry: dict[str, Any], workflows: list[dict[str, Any]]
) -> list[str]:
    """Gate 4: every `requires` token and every workflow-referenced capability is provided
    by some skill. A stable skill whose `requires` points at nothing is an orphan reference."""
    index = build_capability_index(registry)
    provided = set(index)
    errors: list[str] = []

    for skill in iter_skills(registry):
        cap = skill.get("capability") or {}
        if cap.get("status", "stable") == "experimental":
            continue
        for token in cap.get("requires", []):
            if token not in provided:
                errors.append(
                    f"{skill['name']}: requires '{token}' which no skill provides/produces"
                )

    for wf in workflows:
        for step in wf.get("steps", []):
            token = step.get("capability")
            if token not in provided:
                errors.append(f"workflow {wf.get('id')}: step capability '{token}' has no provider")
    return errors


def gate_workflow(
    wf: dict[str, Any], registry: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """Gates 2, 5, 6, 7 for a single workflow, plus schema validity of the workflow file."""
    errors: list[str] = []
    wid = wf.get("id", "<no-id>")

    errors.extend(validate_against_schema(wf, schema, f"workflow[{wid}]"))

    skills_by_name = {s["name"]: s for s in iter_skills(registry)}

    # Gate 2 + 6: each step -> real skill on disk providing that capability.
    for step in wf.get("steps", []):
        sname, token = step.get("skill"), step.get("capability")
        skill = skills_by_name.get(sname)
        if skill is None:
            errors.append(f"workflow {wid}: step skill '{sname}' not in registry")
            continue
        provides = (skill.get("capability") or {}).get("provides", [])
        if token not in provides:
            errors.append(f"workflow {wid}: '{sname}' does not provide '{token}' (has {provides})")
        if not _skill_exists_on_disk(sname, skill):
            errors.append(f"workflow {wid}: skill '{sname}' has no SKILL.md on disk")

    # Verifier must be a step and must yield a *.verdict capability (or be a process gate).
    verifier = wf.get("verifier")
    if verifier:
        vskill = skills_by_name.get(verifier)
        step_skills = {s.get("skill") for s in wf.get("steps", [])}
        if verifier not in step_skills:
            errors.append(f"workflow {wid}: verifier '{verifier}' is not one of the steps")
        elif vskill is not None:
            vprov = (vskill.get("capability") or {}).get("provides", [])
            if not any(".verdict" in t or t == "falsification.verdict" for t in vprov):
                errors.append(
                    f"workflow {wid}: verifier '{verifier}' provides no *.verdict capability"
                )

    # Gate 5: Yellow/Red/Black workflows need a verifier AND a human_checkpoint.
    if wf.get("risk_tier") in RISK_TIERS_NEEDING_CHECKPOINT:
        if not wf.get("verifier"):
            errors.append(f"workflow {wid}: risk_tier {wf['risk_tier']} requires a verifier")
        if not wf.get("human_checkpoint"):
            tier = wf["risk_tier"]
            errors.append(f"workflow {wid}: risk_tier {tier} requires a human_checkpoint")

    # Gate 7: non-empty termination_condition.
    if not str(wf.get("termination_condition", "")).strip():
        errors.append(f"workflow {wid}: termination_condition must be non-empty")

    # Completion satisfiability: each required token is produced by a step or reserved.
    produced: set[str] = set()
    for step in wf.get("steps", []):
        skill = skills_by_name.get(step.get("skill"))
        if skill:
            produced.update((skill.get("capability") or {}).get("produces", []))
    for token in wf.get("completion", {}).get("requires", []):
        if token not in produced and token not in RESERVED_COMPLETION_TOKENS:
            errors.append(f"workflow {wid}: completion token '{token}' is produced by no step")

    return errors


def _skill_exists_on_disk(name: str, skill: dict[str, Any]) -> bool:
    """A step's skill must resolve to a real SKILL.md under skills/ (registry <-> disk)."""
    for base in (ROOT / "skills" / "core", ROOT / "skills" / "extensions"):
        if (base / name / "SKILL.md").exists():
            return True
    return False


# --------------------------------------------------------------------------- driver
def run_all_checks() -> list[str]:
    errors: list[str] = []
    registry = _load_yaml(REGISTRY)
    cap_schema = _load_json(CAP_SCHEMA)
    wf_schema = _load_json(WF_SCHEMA)
    workflows = [_load_yaml(p) for p in sorted(WF_DIR.glob("*.yaml"))]

    errors.extend(gate_capability_schema(registry, cap_schema))
    errors.extend(gate_requires_acyclic(registry))
    errors.extend(gate_dangling_references(registry, workflows))
    for wf in workflows:
        errors.extend(gate_workflow(wf, registry, wf_schema))
    return errors


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    check_mode = "--check" in argv
    errors = run_all_checks()
    if errors:
        print("Architectural coherence: FAIL", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    if not check_mode:
        n_wf = len(list(WF_DIR.glob("*.yaml")))
        print(f"Architectural coherence: OK ({n_wf} workflow(s), all gates green)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
