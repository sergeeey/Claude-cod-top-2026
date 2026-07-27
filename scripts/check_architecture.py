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
  8. the hooks/ intra-module import graph is acyclic (protects the audit's headline metric:
     0 import cycles across the dense 91-module hook core -- see docs/architecture-coupling/)
  9. every file-backed `depends_on: X(rule|hook|agent)` resolves to a file this repo ships
     (clean-install integrity; skill<->skill deps are gated in tests/test_structure.py)
  10. every registry entry declares a valid `kind` (functional role) + `maturity` (evidence
     ladder); dogfooded/benchmarked maturity requires a citable `maturity_evidence` (anti-theater)

Design notes:
  - stdlib + PyYAML only (no jsonschema): CI installs exactly the requirements.txt pins.
    A minimal JSON-Schema subset validator lives in `validate_against_schema`.
  - Acyclicity (gate 3) runs over `requires` ONLY. `verification_required` is a back-reference
    to a verifier (skeptic verifies X, and skeptic also consumes X's downstream) and would
    create false cycles. `depends_on` is load-order, not a data-flow edge, so it is excluded
    from gate 3; its skill<->skill edges are gated bidirectionally in tests/test_structure.py,
    and its file-backed rule/hook/agent refs are gated by gate 9 below.
  - Any scoring is additive-normalized by construction here (we do not multiply criticality
    factors) -- a single zero factor must never zero out a rare-but-catastrophic dependency.

Usage:
    python scripts/check_architecture.py            # human report, exit 0/1
    python scripts/check_architecture.py --check     # CI mode, quiet on success, exit 0/1
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]  # types-PyYAML intentionally not a dep
except ImportError:  # pragma: no cover - PyYAML is a pinned CI dep
    print("ERROR: PyYAML is required (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "hooks"
REGISTRY = ROOT / "skills" / "registry.yaml"
CAP_SCHEMA = ROOT / "architecture" / "capability.schema.json"
WF_SCHEMA = ROOT / "architecture" / "workflow.schema.json"
WF_DIR = ROOT / "architecture" / "workflows"

# Process gates that are NOT skills (see TestRegistryCapabilitySchema in tests/test_structure.py).
PROCESS_GATES = {"source_trace", "safety_floor_check", "at_least_one_kill_test"}
# Reserved workflow completion tokens satisfied by structure, not by a step's `produces`.
RESERVED_COMPLETION_TOKENS = {"memory_destination"}
RISK_TIERS_NEEDING_CHECKPOINT = {"Yellow", "Red", "Black"}

# Gate 9: file-backed `depends_on` references. A `depends_on: X(kind)` token points at a file
# this repo must SHIP for a clean install to resolve it. skill<->skill deps are a separate
# namespace, gated bidirectionally in tests/test_structure.py -- not re-checked here.
# Only rule/hook/agent are file-backed and thus checkable here. Other kinds (e.g. `X(MCP)`, a
# runtime server dependency) are INTENTIONALLY out of scope: their availability is a runtime
# concern, not a shipped file, so a missing MCP server is not a clean-install packaging defect.
_DEP_REF = re.compile(r"^([a-z0-9_-]+)\((rule|hook|agent)\)$")
_DEP_ARTIFACT_DIRS = {
    "rule": (ROOT / "rules", ".md"),
    "hook": (HOOKS_DIR, ".py"),
    "agent": (ROOT / "agents", ".md"),
}

# Gate 10: functional-role + evidence-graded maturity on every registry entry.
# `kind` is orthogonal to `category` (domain): category = WHICH domain, kind = functional ROLE,
# so a router can pick a method over a tool. `maturity` is an evidence ladder and is DISTINCT
# from capability.status (a binary stable/experimental flag that gate 4 uses to skip experimental
# skills) -- the two co-exist on purpose. dogfooded/benchmarked demand a citable artifact: a
# maturity claim with no evidence is exactly the validation-theater the evidence policy prevents.
_KIND_VALUES = {
    "methodology",
    "orchestrator",
    "verifier",
    "gate",
    "generator",
    "utility",
    "integration",
    "domain",
}
_MATURITY_VALUES = {"described", "wired", "dogfooded", "benchmarked"}
_MATURITY_NEEDS_EVIDENCE = {"dogfooded", "benchmarked"}

# WHY (2026-07-24, /boyko dogfood run against this exact gate): the non-emptiness check alone
# passed a synthetic junk string ("asdkjhaskjdh not a real file...") as valid maturity_evidence --
# confirmed live by running gate_kind_maturity() against a crafted registry entry. Non-emptiness
# proves someone typed *something*, not that the citation resolves to anything real. The observed
# convention (registry.yaml's one real dogfooded entry) is `"<repo-relative path> -- <description>"`
# -- split on the first " -- " and treat the leading segment as the citation target.


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
                return stack[stack.index(nxt) :] + [nxt]
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


def build_hook_import_graph(hooks_dir: Path = HOOKS_DIR) -> dict[str, set[str]]:
    """Build the intra-package import graph over hooks/*.py (module = file stem).

    An edge stem -> base means the file `hooks/<stem>.py` imports the sibling module
    `hooks/<base>.py`, via `import base`, `from base import ...`, or a relative
    `from . import base`. Only edges between sibling hook modules are kept; stdlib and
    third-party imports are ignored. A file that cannot be parsed contributes no edges
    (a syntax error is a separate concern, caught by the test suite, not this gate).
    """
    modules = {p.stem: p for p in hooks_dir.glob("*.py") if p.stem != "__init__"}
    graph: dict[str, set[str]] = {stem: set() for stem in modules}
    for stem, path in modules.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    if base in modules and base != stem:
                        graph[stem].add(base)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:  # from . import sibling
                    for alias in node.names:
                        if alias.name in modules and alias.name != stem:
                            graph[stem].add(alias.name)
                elif node.module:  # from base import ...
                    base = node.module.split(".")[0]
                    if base in modules and base != stem:
                        graph[stem].add(base)
    return graph


def gate_hooks_import_acyclic() -> list[str]:
    """Gate 8: the hooks/ intra-module import graph has no cycle.

    Baseline is clean (0 cycles), so this can only fire on a NEW cyclic import -- a false
    positive is structurally impossible. Reuses the same _find_cycle used for the
    capability requires-graph.
    """
    cycle = _find_cycle(build_hook_import_graph())
    if cycle:
        return ["hooks import graph has a cycle: " + " -> ".join(cycle)]
    return []


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


def gate_dangling_rule_dependencies(registry: dict[str, Any]) -> list[str]:
    """Gate 9: every file-backed `depends_on: X(rule|hook|agent)` resolves to a shipped file.

    WHY (2026-07-19): registry.yaml declared `boyko-triangle-audit` -> depends_on
    perelman-audit(rule) while rules/perelman-audit.md was absent from the repo. The
    maintainer's ~/.claude had the rule, so runtime worked -- but a clean install copies only
    the rules/*.md that this repo ships, so the dependency dangled. depends_on rule/hook refs
    live in a different namespace than capability tokens (gate 4 sees only provides/produces/
    requires), and skill<->skill deps are gated in tests/test_structure.py -- so this class of
    dangling reference had no gate until now.
    """
    errors: list[str] = []
    for skill in iter_skills(registry):
        # `or []` (not a get-default): an explicit `depends_on:` with no value parses to None in
        # YAML, and `skill.get("depends_on", [])` returns that None (default only fires on an
        # ABSENT key) -- `for dep in None` would then crash the whole checker. Mirrors the
        # `skill.get("capability") or {}` guard used elsewhere in this module.
        for dep in skill.get("depends_on") or []:
            if not isinstance(dep, str):
                continue
            m = _DEP_REF.match(dep.strip())
            if not m:  # bare/skill dep -> validated bidirectionally in test_structure.py
                continue
            base, kind = m.group(1), m.group(2)
            directory, ext = _DEP_ARTIFACT_DIRS[kind]
            if not (directory / f"{base}{ext}").exists():
                errors.append(
                    f"{skill['name']}: depends_on '{dep}' but "
                    f"{directory.name}/{base}{ext} is not shipped by this repo "
                    f"(clean-install would dangle)"
                )
    return errors


def gate_kind_maturity(registry: dict[str, Any]) -> list[str]:
    """Gate 10: every registry entry declares a valid `kind` + `maturity`, and any dogfooded/
    benchmarked maturity carries a non-empty `maturity_evidence`.

    WHY: separating methods from tools (kind) lets a router pick a methodology over a utility
    instead of treating a `category: research` bucket as one type. Grading maturity honestly
    (described -> wired -> dogfooded -> benchmarked) stops the catalog from implying every skill
    is proven; the evidence requirement on dogfooded/benchmarked makes a maturity claim
    falsifiable rather than self-declared -- the same discipline this checker applies to counts.
    """
    errors: list[str] = []
    for skill in iter_skills(registry):
        name = skill.get("name", "<no-name>")
        kind = skill.get("kind")
        maturity = skill.get("maturity")
        if kind is None:
            errors.append(f"{name}: missing 'kind'")
        elif kind not in _KIND_VALUES:
            errors.append(f"{name}: kind {kind!r} not in {sorted(_KIND_VALUES)}")
        if maturity is None:
            errors.append(f"{name}: missing 'maturity'")
        elif maturity not in _MATURITY_VALUES:
            errors.append(f"{name}: maturity {maturity!r} not in {sorted(_MATURITY_VALUES)}")
        elif maturity in _MATURITY_NEEDS_EVIDENCE:
            # Treat explicit YAML null the same as missing/empty: `str(None)` is "None" (truthy),
            # so a bare `maturity_evidence: null` would otherwise slip through the anti-theater
            # rule as if evidence were provided. Same YAML-null trap as depends_on in gate 9.
            evidence = skill.get("maturity_evidence")
            if evidence is None or not str(evidence).strip():
                errors.append(
                    f"{name}: maturity {maturity!r} requires a non-empty 'maturity_evidence' "
                    f"(path/citation to a real run) -- anti-theater"
                )
            else:
                # Non-emptiness alone proves someone typed *something*, not that it resolves to
                # anything real -- a junk string like "asdkjhaskjdh not a real file" previously
                # passed. Extract the leading citation target (the repo convention is
                # "<path> -- <description>"; split on the first " -- " if present) and require it
                # to either look like a URL (unverifiable offline, accepted as-is -- this gate has
                # no network access and shouldn't need one) or resolve to a real file in this repo.
                target = str(evidence).split(" -- ", 1)[0].strip().strip("\"'")
                if not (target.startswith("http://") or target.startswith("https://")):
                    if not (ROOT / target).exists():
                        errors.append(
                            f"{name}: maturity_evidence cites {target!r} but that file does not "
                            f"exist in this repo -- anti-theater (a citation to nothing is the "
                            f"same as no citation)"
                        )
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
    errors.extend(gate_hooks_import_acyclic())
    errors.extend(gate_dangling_references(registry, workflows))
    errors.extend(gate_dangling_rule_dependencies(registry))
    errors.extend(gate_kind_maturity(registry))
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
