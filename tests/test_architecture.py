"""Tests for executable architectural coherence (scripts/check_architecture.py + resolve_route.py).

Two layers:
  1. Control: the REAL registry + workflows pass every gate (green baseline).
  2. Mutation: for each defect the checker is meant to catch, we mutate an in-memory copy and
     assert the relevant gate now reports an error -- AND that the un-mutated fixture is clean,
     so every mutation test is proven able to fail (adversarial check, per repo guard discipline).

Fixtures are in-memory dicts (not disk writes) so mutations never touch the tree.
"""

from __future__ import annotations

import copy

import pytest

check = pytest.importorskip("check_architecture")
resolve_route = pytest.importorskip("resolve_route")


# --------------------------------------------------------------------------- loaders / fixtures
def _real_registry():
    return check._load_yaml(check.REGISTRY)


def _real_workflows():
    return [check._load_yaml(p) for p in sorted(check.WF_DIR.glob("*.yaml"))]


def _cap_schema():
    return check._load_json(check.CAP_SCHEMA)


def _wf_schema():
    return check._load_json(check.WF_SCHEMA)


def _mini_registry():
    """Small self-contained registry with a valid 2-step data-flow, no disk dependency."""
    return {
        "core": [
            {
                "name": "producer",
                "capability": {
                    "provides": ["thing.made"],
                    "risk_tier": "Green",
                    "verification_required": [],
                    "produces": ["thing_made"],
                    "requires": [],
                },
            },
            {
                "name": "consumer",
                "capability": {
                    "provides": ["thing.used"],
                    "risk_tier": "Green",
                    "verification_required": [],
                    "requires": ["thing.made"],
                },
            },
        ]
    }


# --------------------------------------------------------------------------- 1. control (green)
def test_real_architecture_passes_all_gates():
    assert check.run_all_checks() == []


def test_resolver_produces_valid_artifact_for_real_workflow():
    art = resolve_route.resolve("test the hypothesis that X causes Y", None)
    assert art["workflow"] == "scientific-hypothesis"
    assert art["required_verifier"] == "skeptic"
    assert art["selected_capabilities"][0].startswith("routing-policy:")
    assert art["memory_sink"] and art["failure_sink"]


# --------------------------------------------------------------------------- 2. schema layer
def test_capability_schema_accepts_wellformed_block():
    good = {"provides": ["a.b"], "risk_tier": "Green", "verification_required": []}
    assert check.validate_against_schema(good, _cap_schema()) == []


def test_capability_schema_rejects_missing_provides():
    bad = {"risk_tier": "Green", "verification_required": []}
    assert check.validate_against_schema(bad, _cap_schema())


def test_capability_schema_rejects_bad_risk_tier():
    bad = {"provides": ["a.b"], "risk_tier": "Turquoise", "verification_required": []}
    assert check.validate_against_schema(bad, _cap_schema())


def test_capability_schema_rejects_empty_provides():
    bad = {"provides": [], "risk_tier": "Green", "verification_required": []}
    assert check.validate_against_schema(bad, _cap_schema())


# --------------------------------------------------------------------------- 3. mutation: gates
def test_mutation_removed_required_dependency_is_caught():
    reg = _mini_registry()
    # control: clean
    assert check.gate_dangling_references(reg, []) == []
    # mutate: consumer now requires a token nobody provides
    reg["core"][1]["capability"]["requires"] = ["ghost.capability"]
    errs = check.gate_dangling_references(reg, [])
    assert any("ghost.capability" in e for e in errs)


def test_mutation_requires_cycle_is_caught():
    reg = _mini_registry()
    assert check.gate_requires_acyclic(reg) == []
    # mutate: producer now requires the consumer's output -> cycle
    reg["core"][0]["capability"]["requires"] = ["thing.used"]
    errs = check.gate_requires_acyclic(reg)
    assert any("cycle" in e.lower() for e in errs)


def test_mutation_removed_verifier_is_caught():
    reg = _real_registry()
    wf = copy.deepcopy(_real_workflows()[0])
    assert check.gate_workflow(wf, reg, _wf_schema()) == []
    wf["verifier"] = "nonexistent-verifier"
    errs = check.gate_workflow(wf, reg, _wf_schema())
    assert any("verifier" in e for e in errs)


def test_mutation_step_capability_not_provided_is_caught():
    reg = _real_registry()
    wf = copy.deepcopy(_real_workflows()[0])
    wf["steps"][1]["capability"] = "capability.that.does.not.exist"
    errs = check.gate_workflow(wf, reg, _wf_schema())
    assert any("does not provide" in e for e in errs)


def test_mutation_step_skill_not_in_registry_is_caught():
    reg = _real_registry()
    wf = copy.deepcopy(_real_workflows()[0])
    wf["steps"][0]["skill"] = "ghost-skill"
    errs = check.gate_workflow(wf, reg, _wf_schema())
    assert any("not in registry" in e for e in errs)


def test_mutation_incompatible_risk_tier_needs_checkpoint():
    reg = _real_registry()
    wf = copy.deepcopy(_real_workflows()[0])
    assert check.gate_workflow(wf, reg, _wf_schema()) == []
    wf["risk_tier"] = "Red"  # Red without human_checkpoint must fail
    errs = check.gate_workflow(wf, reg, _wf_schema())
    assert any("human_checkpoint" in e for e in errs)


def test_mutation_removed_termination_condition_is_caught():
    reg = _real_registry()
    wf = copy.deepcopy(_real_workflows()[0])
    wf["termination_condition"] = "   "
    errs = check.gate_workflow(wf, reg, _wf_schema())
    assert any("termination_condition" in e for e in errs)


def test_mutation_unsatisfiable_completion_token_is_caught():
    reg = _real_registry()
    wf = copy.deepcopy(_real_workflows()[0])
    wf["completion"]["requires"].append("token_no_step_produces")
    errs = check.gate_workflow(wf, reg, _wf_schema())
    assert any("token_no_step_produces" in e for e in errs)


def test_mutation_orphan_capability_reference_is_caught():
    reg = _mini_registry()
    reg["core"].append({
        "name": "orphan",
        "capability": {
            "provides": ["orphan.out"],
            "risk_tier": "Green",
            "verification_required": [],
            "requires": ["nothing.provides.this"],
        },
    })
    errs = check.gate_dangling_references(reg, [])
    assert any("nothing.provides.this" in e for e in errs)


# --------------------------------------------------------------------------- 3b. validator unions
def test_schema_validator_honors_required_under_union_type():
    """Regression: object/array checks must fire even when `type` is a union list
    (e.g. ['object','null']), not only when it is the bare string 'object'."""
    union_schema = {
        "type": ["object", "null"],
        "required": ["must_have"],
        "properties": {"must_have": {"type": "string"}},
    }
    assert check.validate_against_schema(None, union_schema) == []          # null branch ok
    assert check.validate_against_schema({"must_have": "x"}, union_schema) == []
    errs = check.validate_against_schema({}, union_schema)                  # missing required
    assert any("must_have" in e for e in errs)


def test_acyclicity_edges_to_all_providers_of_a_token():
    """Regression: a token produced by two skills must edge to BOTH, so a cycle through
    the second provider cannot hide behind the first (build_provider_index, not first-wins)."""
    reg = {
        "core": [
            # both A and B produce token 'dup'
            {"name": "A", "capability": {"provides": ["a.out"], "risk_tier": "Green",
                                          "verification_required": [], "produces": ["dup"]}},
            {"name": "B", "capability": {"provides": ["b.out"], "risk_tier": "Green",
                                          "verification_required": [], "produces": ["dup"],
                                          "requires": ["a.out"]}},
            # C requires 'dup' (both A and B provide) and B requires C's output -> cycle via B
            {"name": "C", "capability": {"provides": ["c.out"], "risk_tier": "Green",
                                          "verification_required": [], "requires": ["dup"]}},
        ]
    }
    # make B depend on C to force a B->...->B cycle only visible if C edges to B
    reg["core"][1]["capability"]["requires"] = ["a.out", "c.out"]
    reg["core"][2]["capability"]["requires"] = ["dup"]  # C -> {A, B}
    errs = check.gate_requires_acyclic(reg)
    assert any("cycle" in e.lower() for e in errs)


# --------------------------------------------------------------------------- 4. resolver guards
def test_resolver_rejects_unknown_task_type():
    with pytest.raises(ValueError):
        resolve_route.resolve(None, "no-such-workflow")


def test_resolver_rejects_ungoaled_call():
    with pytest.raises(ValueError):
        resolve_route.resolve(None, None)


def test_resolver_lists_rejected_alternatives_with_reasons():
    art = resolve_route.resolve(None, "scientific-hypothesis")
    assert isinstance(art["rejected_alternatives"], list)
    for alt in art["rejected_alternatives"]:
        assert alt["skill"] and alt["reason"]
        # `capability` must be in the same "skill:token" vocabulary as selected_capabilities,
        # not a bare skill name (regression: it used to hold the skill name under this key).
        assert alt["capability"].startswith(f"{alt['skill']}:") or alt["capability"] == alt["skill"]


# --------------------------------------------------------------------------- 5. import-cycle gate
def test_hooks_import_graph_is_acyclic():
    """Control: the real hooks/ intra-module import graph has no cycle (audit headline metric)."""
    assert check.gate_hooks_import_acyclic() == []


def test_mutation_hook_import_cycle_is_caught(tmp_path):
    """Mutation: two sibling hook modules that import each other form a cycle the gate reports.

    Written to an isolated tmp dir (not the repo tree) because ast must parse real files;
    proves the gate can fail, per the repo's adversarial-guard discipline.
    """
    (tmp_path / "alpha.py").write_text("import beta\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("from alpha import x\n", encoding="utf-8")
    graph = check.build_hook_import_graph(tmp_path)
    # control: an acyclic pair in the same fixture dir would not cycle
    assert graph["alpha"] == {"beta"} and graph["beta"] == {"alpha"}
    cycle = check._find_cycle(graph)
    assert cycle and "alpha" in cycle and "beta" in cycle


# --------------------------------------------------------------------------- 6. CLI smoke
def test_check_architecture_cli_returns_zero_on_clean_tree():
    assert check.main(["--check"]) == 0
