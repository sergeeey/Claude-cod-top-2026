#!/usr/bin/env python3
"""Route resolver: task -> machine-readable route artifact over the canonical workflows.

This is a RESOLVER, not a generative super-agent. Given a task type (or free-text goal), it
selects the matching canonical workflow from architecture/workflows/, emits the ordered
capabilities, the rejected alternatives (with reasons), the required verifier, and the memory
sinks -- then validates that artifact against the registry so the route cannot claim a
capability, verifier, or sink that does not exist.

It composes with the safety floor, it does not replace it: capability SELECTION is this
resolver's job; the mandatory safety FLOOR is `hooks/routing_floor_classifier.py` (enforced by
code on every prompt). We import that hook's tier table so the floor shown here is the same one
the hook injects -- single source of truth, no divergence.

Usage:
    python scripts/resolve_route.py "test the hypothesis that X causes Y"
    python scripts/resolve_route.py --task-type scientific-hypothesis
    python scripts/resolve_route.py --task-type scientific-hypothesis --out route.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))  # for routing_floor_classifier (single floor source)

from check_architecture import (  # noqa: E402  (path set above)
    WF_DIR,
    _load_yaml,
    build_capability_index,
    iter_skills,
)

REGISTRY = ROOT / "skills" / "registry.yaml"


def _safety_floor(goal: str) -> list[str]:
    """Reuse the hook's tier table so the floor here == the floor the hook injects."""
    try:
        from routing_floor_classifier import _TIERS  # type: ignore
    except ImportError:
        return []
    floors: list[str] = []
    for name, pattern, floor in _TIERS:
        # _TIERS holds compiled re.Pattern objects (IGNORECASE already baked in).
        if pattern.search(goal):
            floors.append(f"{name}: {floor}")
    return floors


def load_workflows() -> dict[str, dict[str, Any]]:
    return {wf["id"]: wf for wf in (_load_yaml(p) for p in sorted(WF_DIR.glob("*.yaml")))}


def _match_task_type(goal: str, workflows: dict[str, dict[str, Any]]) -> str | None:
    """Very small keyword match goal -> task_type. Deterministic; ties broken by id order."""
    signals = {
        "scientific-hypothesis": [
            "hypothesis", "гипотеза", "causes", "correlat", "experiment", "falsif",
            "research", "estimand", "predict",
        ],
    }
    goal_l = goal.lower()
    for wid in sorted(workflows):
        for kw in signals.get(wid, []):
            if kw in goal_l:
                return wid
    return None


def resolve(goal: str | None, task_type: str | None) -> dict[str, Any]:
    """Build and validate a route artifact. Raises ValueError on any inconsistency."""
    registry = _load_yaml(REGISTRY)
    workflows = load_workflows()
    index = build_capability_index(registry)
    skills_by_name = {s["name"]: s for s in iter_skills(registry)}

    if task_type is None:
        if goal is None:
            raise ValueError("provide a goal string or --task-type")
        task_type = _match_task_type(goal, workflows)
        if task_type is None:
            raise ValueError(f"no canonical workflow matches goal: {goal!r}")

    wf = workflows.get(task_type)
    if wf is None:
        raise ValueError(f"unknown task_type/workflow: {task_type!r}")

    selected = [f"{s['skill']}:{s['capability']}" for s in wf["steps"]]

    # Validate every selected capability resolves to a provider.
    for step in wf["steps"]:
        if step["capability"] not in index:
            raise ValueError(f"capability {step['capability']!r} has no provider in registry")
        if step["skill"] not in skills_by_name:
            raise ValueError(f"skill {step['skill']!r} not in registry")

    verifier = wf.get("verifier")
    if not verifier or verifier not in skills_by_name:
        raise ValueError(f"workflow {task_type}: verifier {verifier!r} missing or unknown")

    memory_sink, failure_sink = wf.get("memory_sink"), wf.get("failure_sink")
    if not memory_sink or not failure_sink:
        raise ValueError(f"workflow {task_type}: memory_sink/failure_sink must be set")

    # Rejected alternatives: sibling science skills NOT chosen for this route, with a reason.
    chosen = {s["skill"] for s in wf["steps"]}
    rejected: list[dict[str, str]] = []
    for skill in iter_skills(registry):
        cap = skill.get("capability") or {}
        provides = cap.get("provides", [])
        is_science = any(
            t.startswith(("hypothesis", "falsification", "proof", "evidence", "claim"))
            for t in provides
        )
        if is_science and skill["name"] not in chosen and skill["name"] != verifier:
            # Keep the same "skill:token" vocabulary as selected_capabilities so a downstream
            # consumer can cross-reference; `skill` is the bare name, `capability` the token.
            token = f"{skill['name']}:{provides[0]}" if provides else skill["name"]
            rejected.append({
                "skill": skill["name"],
                "capability": token,
                "reason": "provides an adjacent evidence capability but is not on the "
                          "canonical scientific-hypothesis critical path",
            })

    fallbacks = {
        s["skill"]: (skills_by_name[s["skill"]].get("capability") or {}).get("fallback")
        for s in wf["steps"]
    }

    artifact = {
        "task_type": task_type,
        "workflow": wf["id"],
        "risk_tier": wf.get("risk_tier"),
        "selected_capabilities": selected,
        "rejected_alternatives": rejected,
        "required_verifier": verifier,
        "gates": wf.get("gates", []),
        "memory_sink": memory_sink,
        "failure_sink": failure_sink,
        "fallback": fallbacks,
        "termination_condition": wf.get("termination_condition", "").strip(),
        "safety_floor": _safety_floor(goal) if goal else [],
    }
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve a task to a machine-readable route.")
    parser.add_argument("goal", nargs="?", help="free-text research goal")
    parser.add_argument("--task-type", help="explicit workflow id (skips keyword match)")
    parser.add_argument("--out", help="write the route artifact JSON to this path")
    args = parser.parse_args(argv)

    try:
        artifact = resolve(args.goal, args.task_type)
    except ValueError as e:
        print(f"resolve_route: {e}", file=sys.stderr)
        return 1

    text = json.dumps(artifact, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
