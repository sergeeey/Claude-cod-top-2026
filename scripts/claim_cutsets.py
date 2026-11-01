#!/usr/bin/env python3
"""Minimal support sets and minimal cut sets of a claim's support logic.

WHY: a claim usually rests on several evidence paths. "What does it depend on?" (a
dependency list) is not the same question as "what is the smallest combination of
failures that destroys it?". `claim-decomposer` already declares `BLOCKING_ATOMS` -- a
model-written claim that "failing this atom kills the claim" -- but nothing computes it.
This script computes, from an explicit AND / OR support structure:

  * minimal support sets   (smallest evidence/assumption sets that suffice for the claim),
  * minimal cut sets       (smallest sets of failures that leave NO support),
  * kappa = size of the smallest cut ("how many independent errors to lose the claim"),
  * singleton failures     (single points of failure) and FALSE_INDEPENDENCE (a singleton
                            cut that sits under >=2 apparently independent paths),
  * cut participation      (how many minimal cuts contain each node),
  * dead nodes             (named but in no minimal support set: absorbed redundancy),
  * a heuristic "next verification target" and an `avoid_set` for a NEW proof path.

PRIOR ART -- not claimed as new:
  * Minimal cut sets of fault trees (reliability engineering).
  * Klamt & Gilles (2004), "Minimal cut sets in biochemical reaction networks",
    Bioinformatics 20(2):226-234.
  * de Kleer (1986), "An assumption-based TMS", Artificial Intelligence 28:127-162
    (minimal assumption sets that support a conclusion).
  Minimal cut sets are the minimal transversals (hitting sets) of the minimal support
  sets, and vice versa; this module computes each side independently by AND/OR duality
  and the tests cross-check them against a Berge transversal routine.

INPUTS:
  * `--logic "H = (A & B) | (C & D & E)"` : `&`/`AND`/`∧` and `|`/`OR`/`∨`, parentheses,
    no other syntax. Parsed by a small recursive-descent parser; nothing is ever eval'ed.
  * `--decomposer FILE` : the text of a `claim-decomposer` run (`Ci: ...` lines, `Ci → Cj`
    edges meaning "Cj relies on Ci", `BLOCKING_ATOMS`, `LOAD_BEARING`, `INDEPENDENT`).
    With no OR structure the claim is AND over the blocking atoms and everything they
    transitively rely on. That alone yields a mechanical consistency check of the skill's own
    output: a transitive dependency of a blocking atom MUST also be blocking.
    `--logic` may be added to override the default with a real OR structure.
  * `--nodes JSON|@file` : optional node metadata, {"A": {"kind": "infrastructure",
    "status": "weak", "cost": 2}}.

HONEST LIMITS:
  * Minimal cut sets can blow up combinatorially (15 OR-ed AND-pairs have 2^15 cuts). The
    cap is on OUTPUT size (`--max-sets`, default 5000, provisional); past it the result is
    `TRUNCATED` and NO kappa is reported (a partial cut family would give a wrong kappa).
  * The logic is only as good as whoever wrote it: this script does not read prose.
  * `status` weights in the "next verification target" ranking are an unvalidated
    heuristic, labelled `[WEAK]` in the output.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MAX_SETS = 5000
# Provisional: an intermediate family may be up to this many times the output cap before a parent
# absorbs it. Absorption is quadratic in the family size, so the factor stays small.
_INTERMEDIATE_FACTOR = 2
_MAX_PRODUCT = 250_000  # cross-product size guard, to stop memory blow-up before minimising
_MAX_DEPTH = 100


class LogicParseError(ValueError):
    """The support-logic string is not in the allowed grammar."""


class TooLarge(Exception):
    """A set family exceeded the output cap."""


# --------------------------------------------------------------------------- AST + parser
@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class And:
    children: tuple[Expr, ...]


@dataclass(frozen=True)
class Or:
    children: tuple[Expr, ...]


Expr = Var | And | Or

_TOKEN = re.compile(
    r"\s*(?:(?P<lp>\()|(?P<rp>\))|(?P<and>&|∧|\bAND\b)|(?P<or>\||∨|\bOR\b)"
    r"|(?P<id>[A-Za-z_][A-Za-z0-9_.]*))",
    re.IGNORECASE,
)


def _tokenize(text: str) -> list[tuple[str, str]]:
    pos, out = 0, []
    text = text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise LogicParseError(f"unexpected character at {pos}: {text[pos : pos + 12]!r}")
        pos = m.end()
        kind = m.lastgroup or ""
        value = m.group(kind)
        if kind in {"and", "or"}:
            out.append((kind, value))
        elif kind == "id" and value.upper() in {"AND", "OR"}:
            out.append((value.lower(), value))
        else:
            out.append((kind, value))
    return out


def parse_logic(text: str) -> Expr:
    """Parse `[H =] expr`. `&` binds tighter than `|`. Never evaluates anything."""
    body = text.strip()
    lhs = re.match(r"^\s*[A-Za-z_][A-Za-z0-9_.]*\s*=(?!=)", body)
    if lhs:
        body = body[lhs.end() :]
    tokens = _tokenize(body)
    if not tokens:
        raise LogicParseError("empty logic expression")
    pos = 0

    def peek() -> str | None:
        return tokens[pos][0] if pos < len(tokens) else None

    def expr(depth: int) -> Expr:
        nonlocal pos
        if depth > _MAX_DEPTH:
            raise LogicParseError("expression nested too deeply")
        parts = [term(depth)]
        while peek() == "or":
            pos += 1
            parts.append(term(depth))
        return parts[0] if len(parts) == 1 else Or(tuple(_flatten(Or, parts)))

    def term(depth: int) -> Expr:
        nonlocal pos
        parts = [factor(depth)]
        while peek() == "and":
            pos += 1
            parts.append(factor(depth))
        return parts[0] if len(parts) == 1 else And(tuple(_flatten(And, parts)))

    def factor(depth: int) -> Expr:
        nonlocal pos
        kind = peek()
        if kind == "id":
            name = tokens[pos][1]
            pos += 1
            return Var(name)
        if kind == "lp":
            pos += 1
            inner = expr(depth + 1)
            if peek() != "rp":
                raise LogicParseError("missing closing parenthesis")
            pos += 1
            return inner
        raise LogicParseError(f"expected a name or '(' but found {kind or 'end of input'}")

    result = expr(0)
    if pos != len(tokens):
        raise LogicParseError(f"unexpected token {tokens[pos][1]!r}")
    return result


def _flatten(kind: type[And] | type[Or], parts: list[Expr]) -> list[Expr]:
    out: list[Expr] = []
    for p in parts:
        if isinstance(p, And | Or) and isinstance(p, kind):
            out.extend(p.children)
        else:
            out.append(p)
    return out


def variables(e: Expr) -> list[str]:
    if isinstance(e, Var):
        return [e.name]
    seen: list[str] = []
    for c in e.children:
        for v in variables(c):
            if v not in seen:
                seen.append(v)
    return seen


# --------------------------------------------------------------------------- set algebra
Family = frozenset[frozenset[str]]


def minimize(family: set[frozenset[str]] | Family, cap: int) -> Family:
    """Drop duplicates and any set that strictly contains another (absorption)."""
    kept: list[frozenset[str]] = []
    for s in sorted(set(family), key=lambda x: (len(x), sorted(x))):
        if not any(k <= s for k in kept):
            kept.append(s)
            if len(kept) > cap:
                raise TooLarge(f"more than {cap} minimal sets")
    return frozenset(kept)


def _union(a: Family, b: Family, cap: int) -> Family:
    return minimize(set(a) | set(b), cap)


def _product(a: Family, b: Family, cap: int) -> Family:
    if len(a) * len(b) > _MAX_PRODUCT:
        raise TooLarge("intermediate cross product too large")
    return minimize({x | y for x in a for y in b}, cap)


def _supports(e: Expr, bound: int) -> Family:
    if isinstance(e, Var):
        return frozenset({frozenset({e.name})})
    fams = [_supports(c, bound) for c in e.children]
    acc = fams[0]
    for f in fams[1:]:
        acc = _union(acc, f, bound) if isinstance(e, Or) else _product(acc, f, bound)
    return acc


def _cuts(e: Expr, bound: int) -> Family:
    if isinstance(e, Var):
        return frozenset({frozenset({e.name})})
    fams = [_cuts(c, bound) for c in e.children]
    acc = fams[0]
    for f in fams[1:]:
        acc = _union(acc, f, bound) if isinstance(e, And) else _product(acc, f, bound)
    return acc


def _capped(fam: Family, cap: int) -> Family:
    if len(fam) > cap:
        raise TooLarge(f"more than {cap} minimal sets")
    return fam


def supports(e: Expr, cap: int = DEFAULT_MAX_SETS) -> Family:
    """Minimal sets whose truth suffices for `e` (OR = union, AND = cross product).

    `cap` bounds the FINAL family. Intermediate families may be larger (a parent can still absorb
    them: `A | (A & (B | C))` is just `A`); they are bounded by `cap * _INTERMEDIATE_FACTOR`.
    """
    return _capped(_supports(e, cap * _INTERMEDIATE_FACTOR), cap)


def cuts(e: Expr, cap: int = DEFAULT_MAX_SETS) -> Family:
    """Minimal sets whose failure destroys `e` -- the AND/OR dual of `supports`."""
    return _capped(_cuts(e, cap * _INTERMEDIATE_FACTOR), cap)


def minimal_transversals(family: Family, cap: int = DEFAULT_MAX_SETS) -> Family:
    """Berge's algorithm: minimal hitting sets of `family` (independent cross-check)."""
    current: Family = frozenset({frozenset()})
    for s in family:
        nxt: set[frozenset[str]] = set()
        for t in current:
            if t & s:
                nxt.add(t)
            else:
                for v in s:
                    nxt.add(t | {v})
        current = minimize(nxt, cap)
    return current


# --------------------------------------------------------------------------- analysis
_STATUS_WEIGHT = {
    "unverified": 1.0,
    "unknown": 1.0,
    "weak": 1.0,
    "partial": 0.5,
    "verified": 0.1,
    "strong": 0.1,
}


def analyze(
    expr: Expr,
    nodes: dict[str, dict[str, Any]] | None = None,
    max_sets: int = DEFAULT_MAX_SETS,
) -> dict[str, Any]:
    nodes = nodes or {}
    names = variables(expr)
    try:
        sup = supports(expr, max_sets)
        cut = cuts(expr, max_sets)
    except TooLarge as exc:
        return {
            "status": "TRUNCATED",
            "reason": str(exc),
            "max_sets": max_sets,
            "truncated": True,
            "note": "no kappa reported: a partial cut family would give a wrong kappa",
        }
    kappa = min(len(c) for c in cut)
    # Pure AND of distinct variables <=> the minimal cuts are exactly the singletons {v}. A root
    # And with an Or inside (A & (B | C)) is NOT only-AND: its cuts are {A} and {B, C}.
    only_and = set(cut) == {frozenset([v]) for v in names}
    singletons = sorted(next(iter(c)) for c in cut if len(c) == 1)
    in_supports = set().union(*sup)
    participation = Counter(v for c in cut for v in c)
    # A singleton cut {v} hits EVERY support by definition, so v is under all of them; with
    # >= 2 supports that is exactly "several apparently independent paths on one shared leg".
    false_indep = sorted(v for v in singletons if len(sup) >= 2)
    min_support_size = min(len(s) for s in sup)
    mses = sorted(sorted(s) for s in sup if len(s) == min_support_size)

    def weight(v: str) -> float:
        meta = nodes.get(v, {})
        status = str(meta.get("status", "unknown")).lower()
        cost = meta.get("cost")
        denom = float(cost) if isinstance(cost, (int, float)) and cost > 0 else 1.0
        low_order = sum(1 for c in cut if v in c and len(c) <= kappa + 1)
        return low_order * _STATUS_WEIGHT.get(status, 1.0) / denom

    ranked = sorted(((weight(v), v) for v in names), key=lambda t: (-t[0], t[1]))
    infra = {v for v, m in nodes.items() if str(m.get("kind", "")).lower() == "infrastructure"}
    cert = [sorted(c) for c in cut if not (set(c) & infra)]
    infra_only = [sorted(c) for c in cut if set(c) <= infra and infra]
    avoid = sorted({v for c in cut if len(c) <= kappa for v in c})
    return {
        "status": "OK",
        "truncated": False,
        "nodes": names,
        "only_and_logic": only_and,
        "note": (
            "logic is AND only: every node is a singleton cut, kappa = 1; no redundancy declared"
            if only_and and len(names) >= 1
            else None
        ),
        "minimal_support_sets": sorted(sorted(s) for s in sup),
        "minimal_cut_sets": sorted(sorted(c) for c in cut),
        "kappa": kappa,
        "singleton_failures": singletons,
        "false_independence": false_indep,
        "cut_participation": dict(sorted(participation.items())),
        "cut_order_histogram": dict(sorted(Counter(len(c) for c in cut).items())),
        "dead_nodes": sorted(set(names) - in_supports),
        "minimal_sufficient_evidence_sets": mses,
        "certification_cuts": sorted(cert),
        "infrastructure_only_cuts": sorted(infra_only),
        "next_verification_target": [
            {"node": v, "low_order_cut_weight": round(w, 3)} for w, v in ranked if w > 0
        ][:5],
        "next_verification_target_note": "[WEAK] heuristic: status weights are unvalidated",
        "avoid_set": avoid,
        "avoid_set_note": "a NEW proof path should avoid these nodes (minimum-order cuts)",
    }


# --------------------------------------------------------------------------- decomposer adapter
_ATOM = re.compile(r"^\s*(C\d+)\s*:\s*(.+)$", re.MULTILINE)
_LIST = r"{label}\s*:\s*\[([^\]]*)\]"
_CHAIN = re.compile(r"C\d+(?:\s*(?:→|->)\s*C\d+)+")


def _ids(label: str, text: str) -> list[str]:
    m = re.search(_LIST.format(label=label), text)
    return re.findall(r"C\d+", m.group(1)) if m else []


def parse_decomposer(text: str) -> dict[str, Any]:
    atoms = {m.group(1): m.group(2).strip() for m in _ATOM.finditer(text)}
    edges: list[tuple[str, str]] = []
    for chain in _CHAIN.finditer(text):
        ids = re.findall(r"C\d+", chain.group(0))
        edges.extend(zip(ids, ids[1:], strict=False))
    return {
        "atoms": atoms,
        "edges": sorted(set(edges)),
        "blocking": _ids("BLOCKING_ATOMS", text),
        "load_bearing": _ids("LOAD_BEARING", text),
        "independent": _ids("INDEPENDENT", text),
    }


def decomposer_analysis(text: str, logic: str | None, max_sets: int) -> dict[str, Any]:
    d = parse_decomposer(text)
    if not d["atoms"]:
        return {"status": "INSUFFICIENT_DATA", "reason": "no 'Ci: ...' atom lines found"}
    if not d["blocking"] and logic is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": "no BLOCKING_ATOMS declared and no --logic given: nothing to compute from",
        }
    relies_on: dict[str, set[str]] = {}
    for src, dst in d["edges"]:  # "src -> dst" means dst relies on src
        relies_on.setdefault(dst, set()).add(src)
    required: set[str] = set()
    stack = list(d["blocking"])
    while stack:
        n = stack.pop()
        if n in required:
            continue
        required.add(n)
        stack.extend(relies_on.get(n, ()))
    expr = parse_logic(logic) if logic else _and_of(sorted(required, key=_natural))
    nodes = {
        a: {"status": "unverified" if "[EVIDENCE: none]" in t else "cited"}
        for a, t in d["atoms"].items()
    }
    result = analyze(expr, nodes, max_sets)
    declared = set(d["blocking"])
    computed = set(result.get("singleton_failures", [])) if result["status"] == "OK" else set()
    result["declared_blocking_atoms"] = sorted(declared, key=_natural)
    result["computed_singleton_failures"] = sorted(computed, key=_natural)
    result["implied_but_undeclared"] = sorted(computed - declared, key=_natural)
    result["declared_but_not_singleton"] = sorted(declared - computed, key=_natural)
    result["independent_but_required"] = sorted(set(d["independent"]) & required, key=_natural)
    result["logic_source"] = (
        "--logic" if logic else "AND over blocking atoms and their dependencies"
    )
    return result


def _natural(c: str) -> tuple[int, str]:
    m = re.search(r"\d+", c)
    return (int(m.group(0)) if m else 0, c)


def _and_of(names: list[str]) -> Expr:
    if not names:
        raise LogicParseError("no atoms to build a logic from")
    vs = tuple(Var(n) for n in names)
    return vs[0] if len(vs) == 1 else And(vs)


# --------------------------------------------------------------------------- CLI
def _json_arg(raw: str) -> Any:
    text = Path(raw[1:]).read_text(encoding="utf-8") if raw.startswith("@") else raw
    return json.loads(text)


def _print(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    for key, value in result.items():
        print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--logic", help='support logic, e.g. "H = (A & B) | (C & D & E)" (or @file)')
    p.add_argument("--decomposer", help="file with a claim-decomposer run")
    p.add_argument("--nodes", help="JSON or @file with node metadata")
    p.add_argument("--max-sets", type=int, default=DEFAULT_MAX_SETS)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if not (args.logic or args.decomposer):
        p.error("give --logic or --decomposer")
    try:
        logic = args.logic
        if logic and logic.startswith("@"):
            logic = Path(logic[1:]).read_text(encoding="utf-8")
        if args.decomposer:
            text = Path(args.decomposer).read_text(encoding="utf-8")
            result = decomposer_analysis(text, logic, args.max_sets)
        else:
            nodes = _json_arg(args.nodes) if args.nodes else None
            result = analyze(parse_logic(logic or ""), nodes, args.max_sets)
    except (LogicParseError, ValueError, OSError) as exc:
        print(f"claim_cutsets: {exc}", file=sys.stderr)
        return 2
    _print(result, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
