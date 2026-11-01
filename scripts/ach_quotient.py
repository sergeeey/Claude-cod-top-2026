#!/usr/bin/env python3
"""Quotient view over an ACH matrix: which hypotheses are one empirical object?

WHY: `experiments/_template/ach_matrix.md` and `skills/extensions/hypothesis-arbiter`
both assume the rival hypotheses are already *distinct*. The template only flags a
**row** whose symbol is the same across every column ("non-diagnostic"); nothing asks
the dual question about **columns** -- do two hypotheses give the same predictions on
every available test? If they do, they are one hypothesis under the current probe set,
and every minute spent separating them is wasted. This script computes that, plus the
related quantities that fall out of the same table (see Outputs).

PRIOR ART -- nothing here is claimed as new mathematics:
  * Equivalence-class determination in active learning: Golovin, Krause & Ray,
    "Near-Optimal Bayesian Active Learning with Noisy Observations" (NeurIPS 2010).
  * Observational equivalence / Markov equivalence in causal discovery.
  * Distinguishing / teaching sets: Goldman & Kearns (1995), "On the complexity of
    teaching".
  * The `decode` step is symbol-level erasure/error decoding from coding theory
    (unique decoding iff 2e + s < d).
  What is specific to this repo is wiring them to the ACH table the arbiter already
  produces, with this repo's own `UNKNOWN is not EQUAL` discipline.

DEFINITIONS (fixed after an adversarial review of the first design -- see
experiments/20261001-epistemic-structure-layer/claim.md):
  * Symbols are `C` (consistent), `I` (inconsistent) and `NA` (this hypothesis takes
    no commitment on this test). They are three DIFFERENT values: `NA` is never equal to
    `C` or `I`. "Equal where both are known" is NOT transitive (a tolerance relation, not
    an equivalence), so a class is defined only as **identical full vectors**.
  * Two classes that agree on every test where both are known but differ somewhere in
    `NA`-vs-known are `COMPATIBLE_UNRESOLVED` -- reported, never merged.
  * `d_certain(a, b)` = number of tests where both are known and differ. This is the only
    separation an *observation* can actually use (an observed outcome cannot discriminate
    against a class that made no prediction).
  * A class of >=2 hypotheses is `EQUIVALENT` only if at least COVERAGE_THRESHOLD of its
    cells are known. Below that the matrix says too little to call anything equivalent
    (`UNRESOLVED_LOW_COVERAGE`). The 0.50 value is provisional and mirrors
    `hooks/independence_scorer.py`'s evidence_coverage threshold; it is not calibrated.

OUTPUTS (subcommands): classes | identify | refine | place | decode | floor.
Insufficient input is reported as `INSUFFICIENT_DATA`, never as a reassuring number.

Usage:
    python scripts/ach_quotient.py classes experiments/<id>/ach_matrix.md
    python scripts/ach_quotient.py classes --json-matrix matrix.json --json
    python scripts/ach_quotient.py floor  <matrix> --trials 10000 --seed 7
    python scripts/ach_quotient.py refine <matrix> --candidate '{"H1":"C","H2":"I"}'
    python scripts/ach_quotient.py decode <matrix> --observation '{"T1":"C","T2":"I"}'
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

KNOWN = frozenset({"C", "I"})
VALID = frozenset({"C", "I", "NA"})
# Provisional (not calibrated): same value and meaning as independence_scorer's
# evidence_coverage threshold -- a majority of cells must be known before "equivalent"
# is allowed to mean anything.
COVERAGE_THRESHOLD = 0.50
EXACT_SEARCH_MAX_ROWS = 12

_NA_TOKENS = frozenset({"N/A", "NA", "N.A.", "-", "—", ""})


class MatrixParseError(ValueError):
    """The input is not a usable ACH matrix (distinct from "too little data")."""


@dataclass(frozen=True)
class Matrix:
    hypotheses: tuple[str, ...]
    tests: tuple[str, ...]
    costs: tuple[float | None, ...]
    cells: tuple[tuple[str, ...], ...]  # cells[row][col], symbols in VALID
    skipped_placeholder_rows: int = 0

    @property
    def n_rows(self) -> int:
        return len(self.tests)

    def column(self, j: int, rows: list[int] | None = None) -> tuple[str, ...]:
        idx = range(self.n_rows) if rows is None else rows
        return tuple(self.cells[i][j] for i in idx)


# --------------------------------------------------------------------------- parsing
def normalize_symbol(raw: str) -> str | None:
    """Map a raw table cell to C / I / NA, or None if it is not a symbol at all."""
    t = raw.strip().strip("`*_ ").upper()
    if t == "C":
        return "C"
    if t == "I":
        return "I"
    if t in _NA_TOKENS:
        return "NA"
    return None


def _split_row(line: str) -> list[str]:
    parts = line.strip().split("|")
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c != "")


def parse_ach_markdown(text: str) -> Matrix:
    """Parse the `## Matrix` table of an ach_matrix.md document.

    Placeholder rows (the template's `C / I / N/A` hint row, or a fully blank row) are
    skipped and counted, not treated as data; any other unreadable cell is an error --
    silently skipping a typo would shrink the matrix and change the classes.
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Matrix\b", line.strip(), flags=re.IGNORECASE):
            start = i + 1
            break
    if start is None:
        raise MatrixParseError("no '## Matrix' section found")
    table: list[list[str]] = []
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("|"):
            table.append(_split_row(s))
        elif table and s == "":
            continue
        elif table:
            break
    table = [r for r in table if not _is_separator(r)]
    if not table:
        raise MatrixParseError("'## Matrix' has no table")
    header, body = table[0], table[1:]
    low = [h.lower() for h in header]
    cost_idx = next((k for k, h in enumerate(low) if h.startswith("cost")), None)
    end_idx = next(
        (k for k, h in enumerate(low) if h.startswith("diagnostic") or h.startswith("priority")),
        len(header),
    )
    first_h = (cost_idx + 1) if cost_idx is not None else 1
    cols = list(range(first_h, end_idx))
    if len(cols) < 1:
        raise MatrixParseError("no hypothesis columns between the Cost and Diagnostic? headers")
    hyps = tuple(header[k] for k in cols)
    if len(set(hyps)) != len(hyps):
        raise MatrixParseError(f"duplicate hypothesis ids: {hyps}")
    tests: list[str] = []
    costs: list[float | None] = []
    rows: list[tuple[str, ...]] = []
    skipped = 0
    for n, r in enumerate(body, start=1):
        r = r + [""] * (len(header) - len(r))
        raw = [r[k] for k in cols]
        # A TEMPLATE placeholder row has a non-symbol like `C/I/N/A` in EVERY hypothesis cell (or is
        # empty). A row that mixes valid symbols with an unparseable cell is a typo and must raise:
        # silently skipping it would shrink the matrix.
        placeholder = [("/" in c) and normalize_symbol(c) is None for c in raw]
        if all(placeholder) or (all(c == "" for c in raw) and r[0] == ""):
            skipped += 1
            continue
        syms: list[str] = []
        for h, c in zip(hyps, raw, strict=True):
            sym = normalize_symbol(c)
            if sym is None:
                raise MatrixParseError(f"row {n}: cell {c!r} for {h} is not C / I / N/A")
            syms.append(sym)
        tests.append(r[0] or f"row{n}")
        costs.append(_to_float(r[cost_idx]) if cost_idx is not None else None)
        rows.append(tuple(syms))
    if len(set(tests)) != len(tests):
        raise MatrixParseError(f"duplicate test ids: {tests}")
    return Matrix(hyps, tuple(tests), tuple(costs), tuple(rows), skipped)


def _to_float(raw: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", raw)
    return float(m.group(0)) if m else None


def parse_json_matrix(obj: dict[str, Any]) -> Matrix:
    """JSON form: {"hypotheses": [...], "tests": [{"id":..,"cost":..,"cells":{H: sym}}]}."""
    try:
        hyps = tuple(str(h) for h in obj["hypotheses"])
        tests_in = obj["tests"]
    except (KeyError, TypeError) as exc:
        raise MatrixParseError("JSON matrix needs 'hypotheses' and 'tests'") from exc
    if len(set(hyps)) != len(hyps):
        raise MatrixParseError(f"duplicate hypothesis ids: {hyps}")
    tests: list[str] = []
    costs: list[float | None] = []
    rows: list[tuple[str, ...]] = []
    for t in tests_in:
        cells = t.get("cells", {})
        extra = set(cells) - set(hyps)
        if extra:
            raise MatrixParseError(f"test {t.get('id')!r} names unknown hypotheses {sorted(extra)}")
        syms = []
        for h in hyps:
            sym = normalize_symbol(str(cells.get(h, "NA")))
            if sym is None:
                raise MatrixParseError(f"test {t.get('id')!r}: bad cell {cells.get(h)!r} for {h}")
            syms.append(sym)
        tests.append(str(t.get("id", f"row{len(tests) + 1}")))
        c = t.get("cost")
        costs.append(float(c) if isinstance(c, (int, float)) else None)
        rows.append(tuple(syms))
    if len(set(tests)) != len(tests):
        raise MatrixParseError(f"duplicate test ids: {tests}")
    return Matrix(hyps, tuple(tests), tuple(costs), tuple(rows))


def load_matrix(path: Path) -> Matrix:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return parse_json_matrix(json.loads(text))
    return parse_ach_markdown(text)


# --------------------------------------------------------------------------- classes
@dataclass(frozen=True)
class EquivClass:
    members: tuple[str, ...]
    vector: tuple[str, ...]
    known_fraction: float
    status: str  # SINGLETON | EQUIVALENT | UNRESOLVED_LOW_COVERAGE


def insufficient(m: Matrix) -> str | None:
    """Reason the matrix cannot support any statement, or None if it can."""
    if len(m.hypotheses) < 2:
        return "need >= 2 hypotheses"
    if m.n_rows < 1:
        return "no test rows (template placeholders only?)"
    if not any(s in KNOWN for row in m.cells for s in row):
        return "no known (C / I) cell anywhere"
    return None


def compute_classes(m: Matrix, rows: list[int] | None = None) -> list[EquivClass]:
    groups: dict[tuple[str, ...], list[str]] = {}
    for j, h in enumerate(m.hypotheses):
        groups.setdefault(m.column(j, rows), []).append(h)
    out: list[EquivClass] = []
    for vec, members in groups.items():
        kf = sum(1 for s in vec if s in KNOWN) / len(vec) if vec else 0.0
        if len(members) == 1:
            status = "SINGLETON"
        elif kf >= COVERAGE_THRESHOLD:
            status = "EQUIVALENT"
        else:
            status = "UNRESOLVED_LOW_COVERAGE"
        out.append(EquivClass(tuple(members), vec, kf, status))
    return out


def d_certain(a: tuple[str, ...], b: tuple[str, ...]) -> int:
    """Tests where BOTH vectors are known and differ -- the separation an observation can use."""
    return sum(1 for x, y in zip(a, b, strict=True) if x in KNOWN and y in KNOWN and x != y)


@dataclass(frozen=True)
class PairRelation:
    a: tuple[str, ...]
    b: tuple[str, ...]
    d_certain: int
    relation: str  # SEPARATED | FRAGILE_SEPARATION | COMPATIBLE_UNRESOLVED


def pair_relations(classes: list[EquivClass]) -> list[PairRelation]:
    out = []
    for x, y in itertools.combinations(classes, 2):
        d = d_certain(x.vector, y.vector)
        rel = (
            "COMPATIBLE_UNRESOLVED" if d == 0 else ("FRAGILE_SEPARATION" if d == 1 else "SEPARATED")
        )
        out.append(PairRelation(x.members, y.members, d, rel))
    return out


def summarize(m: Matrix) -> dict[str, Any]:
    why = insufficient(m)
    if why:
        return {"status": "INSUFFICIENT_DATA", "reason": why}
    classes = compute_classes(m)
    pairs = pair_relations(classes)
    resolved = [c for c in classes if c.status == "EQUIVALENT"]
    d_min = min((p.d_certain for p in pairs), default=None)
    return {
        "status": "OK",
        "n_hypotheses": len(m.hypotheses),
        "n_tests": m.n_rows,
        "skipped_placeholder_rows": m.skipped_placeholder_rows,
        "n_classes": len(classes),
        "qc": len(m.hypotheses) / len(classes),
        "n_nonsingleton_resolved": len(resolved),
        "classes": [asdict(c) for c in classes],
        "d_min": d_min,
        "pair_relations": [asdict(p) for p in pairs],
    }


# --------------------------------------------------------------------------- identify
def _separating_rows(m: Matrix, classes: list[EquivClass]) -> dict[int, set[int]]:
    """row -> set of class-pair indices that this row separates with certainty."""
    pairs = list(itertools.combinations(range(len(classes)), 2))
    sep: dict[int, set[int]] = {i: set() for i in range(m.n_rows)}
    for pi, (x, y) in enumerate(pairs):
        for i in range(m.n_rows):
            a, b = classes[x].vector[i], classes[y].vector[i]
            if a in KNOWN and b in KNOWN and a != b:
                sep[i].add(pi)
    return sep


def identify(m: Matrix) -> dict[str, Any]:
    """Cheapest set of tests that certainly separates every separable pair of classes."""
    why = insufficient(m)
    if why:
        return {"status": "INSUFFICIENT_DATA", "reason": why}
    classes = compute_classes(m)
    pairs = list(itertools.combinations(range(len(classes)), 2))
    sep = _separating_rows(m, classes)
    coverable = set().union(*sep.values()) if sep else set()
    unseparable = [pi for pi in range(len(pairs)) if pi not in coverable]
    universe = coverable
    unknown_cost = any(c is None for c in m.costs)
    cost = [1.0 if c is None else c for c in m.costs]
    if m.n_rows <= EXACT_SEARCH_MAX_ROWS:
        best: tuple[float, int, tuple[int, ...]] | None = None
        for r in range(m.n_rows + 1):
            for subset in itertools.combinations(range(m.n_rows), r):
                got = set().union(*(sep[i] for i in subset)) if subset else set()
                if got >= universe:
                    key = (sum(cost[i] for i in subset), len(subset), subset)
                    if best is None or key < best:
                        best = key
        chosen = list(best[2]) if best else []
        method = "exact"
    else:
        chosen = []
        covered: set[int] = set()

        def ratio(k: int, done: set[int]) -> float:
            gain = len(sep[k] - done)
            if cost[k] > 0:
                return gain / cost[k]
            return float("inf") if gain else 0.0  # a free test that separates something wins

        while covered < universe:
            i = max(range(m.n_rows), key=lambda k: (ratio(k, covered), -k))
            if not (sep[i] - covered):
                break
            chosen.append(i)
            covered |= sep[i]
        method = "greedy"
    return {
        "status": "OK",
        "method": method,
        "tests": [m.tests[i] for i in chosen],
        "total_cost": sum(cost[i] for i in chosen),
        "cost_unknown_assumed_1": unknown_cost,
        "unseparable_class_pairs": [
            [list(classes[pairs[pi][0]].members), list(classes[pairs[pi][1]].members)]
            for pi in unseparable
        ],
    }


# --------------------------------------------------------------------------- refine
def _candidate_vector(m: Matrix, cells: dict[str, str]) -> dict[str, str]:
    extra = set(cells) - set(m.hypotheses)
    if extra:
        raise ValueError(f"candidate test names unknown hypotheses {sorted(extra)}")
    out = {}
    for h in m.hypotheses:
        sym = normalize_symbol(str(cells.get(h, "NA")))
        if sym is None:
            raise ValueError(f"candidate cell {cells.get(h)!r} for {h} is not C / I / N/A")
        out[h] = sym
    return out


def candidate_refines(m: Matrix, cells: dict[str, str]) -> dict[str, Any]:
    """Would a NOT-YET-RUN test (its predicted cells) refine the current partition?

    Refinement means: split a multi-member class (two members get different KNOWN
    symbols), or certainly separate two classes that were only COMPATIBLE_UNRESOLVED.
    A test that does neither has zero expected epistemic gain for the current question.
    """
    why = insufficient(m)
    if why:
        return {"status": "INSUFFICIENT_DATA", "reason": why}
    cand = _candidate_vector(m, cells)
    classes = compute_classes(m)
    splits = []
    for c in classes:
        syms = {cand[h] for h in c.members}
        if len(c.members) > 1 and len(syms & KNOWN) == 2:
            splits.append(list(c.members))
    resolves, reinforces = [], []
    for x, y in itertools.combinations(classes, 2):
        rep_x, rep_y = cand[x.members[0]], cand[y.members[0]]
        if not (len({cand[h] for h in x.members}) == 1 and len({cand[h] for h in y.members}) == 1):
            continue
        if rep_x in KNOWN and rep_y in KNOWN and rep_x != rep_y:
            d = d_certain(x.vector, y.vector)
            if d == 0:
                resolves.append([list(x.members), list(y.members)])
            elif d == 1:
                reinforces.append([list(x.members), list(y.members)])
    refines = bool(splits or resolves)
    return {
        "status": "OK",
        "refines": refines,
        "verdict": "ACCEPT" if refines else "TEST REJECTED: cannot refine",
        "splits_classes": splits,
        "resolves_compatible_pairs": resolves,
        "reinforces_fragile_pairs": reinforces,
    }


def row_essential(m: Matrix) -> dict[str, bool]:
    """Leave-one-out: is each existing test needed to keep the current classes apart?"""
    why = insufficient(m)
    if why:
        return {}
    full = len(compute_classes(m))
    out = {}
    for i in range(m.n_rows):
        rest = [k for k in range(m.n_rows) if k != i]
        out[m.tests[i]] = len(compute_classes(m, rest)) < full
    return out


# --------------------------------------------------------------------------- place / decode
def place_candidate(m: Matrix, cells: dict[str, str]) -> dict[str, Any]:
    """Where does a NEW hypothesis (a full column) land: existing class, compatible, or new?

    The share of candidates that land in an EXISTING_CLASS is the False Novelty Rate.
    """
    why = insufficient(m)
    if why:
        return {"status": "INSUFFICIENT_DATA", "reason": why}
    unknown = set(cells) - set(m.tests)
    if unknown:  # a typo would otherwise make the candidate all-NA and compatible with everything
        raise ValueError(f"candidate names unknown tests {sorted(unknown)}")
    vec = []
    for t in m.tests:
        sym = normalize_symbol(str(cells.get(t, "NA")))
        if sym is None:
            raise ValueError(f"candidate cell {cells.get(t)!r} for test {t} is not C / I / N/A")
        vec.append(sym)
    v = tuple(vec)
    classes = compute_classes(m)
    for c in classes:
        if c.vector == v:
            return {"status": "OK", "placement": "EXISTING_CLASS", "class": list(c.members)}
    comp = [list(c.members) for c in classes if d_certain(c.vector, v) == 0]
    if comp:
        return {"status": "OK", "placement": "COMPATIBLE_UNRESOLVED", "compatible_with": comp}
    return {"status": "OK", "placement": "NEW_CLASS"}


def decode(m: Matrix, observation: dict[str, str]) -> dict[str, Any]:
    """Nearest class to an observed outcome vector, with erasure-aware unique decoding.

    `observation` maps test id -> C / I; a missing or NA test is an ERASURE (unobserved).
    Uniqueness test for the best class k against every competitor j, over the tests that
    certainly separate them (set S, |S| = d): with e observed disagreements with k on S and
    s unobserved positions on S, k is told apart from j iff 2e + s < d. If the best class
    is still farther from the observation than the correctable radius floor((d_best-1)/2) on
    ALL its known positions (d_best = smallest d_certain from the best class to any other),
    the observation is not a corrupted copy of any known class: `UNCORRECTABLE` (the "none of
    the above" case) -- the caller must NOT pick the nearest.
    """
    why = insufficient(m)
    if why:
        return {"status": "INSUFFICIENT_DATA", "reason": why}
    unknown = set(observation) - set(m.tests)
    if unknown:
        raise ValueError(f"observation names unknown tests {sorted(unknown)}")
    obs = []
    for t in m.tests:
        sym = normalize_symbol(str(observation.get(t, "NA")))
        if sym is None:
            raise ValueError(f"observation cell {observation.get(t)!r} for {t} is not C / I / N/A")
        obs.append(sym)
    classes = compute_classes(m)
    if len(classes) < 2:
        return {"status": "OK", "decision": "SINGLE_CLASS", "class": list(classes[0].members)}

    def disagreements(vec: tuple[str, ...]) -> int:
        return sum(1 for o, c in zip(obs, vec, strict=True) if o in KNOWN and c in KNOWN and o != c)

    order = sorted(range(len(classes)), key=lambda k: (disagreements(classes[k].vector), k))
    best = order[0]
    ties = [
        k for k in order if disagreements(classes[k].vector) == disagreements(classes[best].vector)
    ]
    d_min = min(d_certain(x.vector, y.vector) for x, y in itertools.combinations(classes, 2))
    best_vec = classes[best].vector
    d_best = None  # smallest d_certain between the best class and any other class
    e_total = disagreements(best_vec)
    worst_pair: dict[str, Any] | None = None
    for k, other in enumerate(classes):
        if k == best:
            continue
        sep = [
            i
            for i in range(m.n_rows)
            if best_vec[i] in KNOWN and other.vector[i] in KNOWN and best_vec[i] != other.vector[i]
        ]
        d = len(sep)
        d_best = d if d_best is None else min(d_best, d)
        e = sum(1 for i in sep if obs[i] in KNOWN and obs[i] != best_vec[i])
        s = sum(1 for i in sep if obs[i] not in KNOWN)
        if d == 0:
            return {
                "status": "OK",
                "decision": "AMBIGUOUS_COMPATIBLE",
                "class": list(classes[best].members),
                "compatible_with": list(other.members),
            }
        if not (2 * e + s < d) and worst_pair is None:
            worst_pair = {"vs": list(other.members), "d": d, "e": e, "s": s}
    # The correctable radius belongs to the BEST class: an unrelated close pair elsewhere in the
    # matrix must not make every observation UNCORRECTABLE (reported `d_min` stays global).
    radius = ((d_best or 0) - 1) // 2
    common = {
        "status": "OK",
        "class": list(classes[best].members),
        "errors_vs_class": e_total,
        "d_min": d_min,
        "d_best": d_best,
        "radius": radius,
    }
    if len(ties) > 1:
        return {
            **common,
            "decision": "AMBIGUOUS_TIE",
            "tied": [list(classes[k].members) for k in ties],
        }
    if e_total > radius or worst_pair is not None:
        return {**common, "decision": "UNCORRECTABLE", "failed_pair": worst_pair}
    return {**common, "decision": "DECODED"}


# --------------------------------------------------------------------------- floor (null)
def floor_null(m: Matrix, trials: int = 10000, seed: int = 0) -> dict[str, Any]:
    """Row-wise shuffle null: how many non-singleton classes does chance alone produce?

    Each test's cells are shuffled across hypotheses (every test keeps its own symbol
    distribution; hypothesis identity is destroyed), then classes are recomputed. Few-row
    matrices merge columns by construction, so the real count only means something
    relative to this number for the SAME shape. Add-one p-value; descriptive, not a test of
    effect.
    """
    if trials < 1:
        raise ValueError("--trials must be >= 1")
    why = insufficient(m)
    if why:
        return {"status": "INSUFFICIENT_DATA", "reason": why}
    observed = sum(1 for c in compute_classes(m) if c.status == "EQUIVALENT")
    rng = random.Random(seed)
    counts = []
    for _ in range(trials):
        shuffled = []
        for row in m.cells:
            r = list(row)
            rng.shuffle(r)
            shuffled.append(tuple(r))
        sm = Matrix(m.hypotheses, m.tests, m.costs, tuple(shuffled))
        counts.append(sum(1 for c in compute_classes(sm) if c.status == "EQUIVALENT"))
    ge = sum(1 for c in counts if c >= observed)
    counts_sorted = sorted(counts)
    return {
        "status": "OK",
        "observed_nonsingleton_resolved": observed,
        "null_mean": sum(counts) / len(counts),
        "null_p95": counts_sorted[min(len(counts_sorted) - 1, int(0.95 * len(counts_sorted)))],
        "trials": trials,
        "seed": seed,
        "p_ge_observed": (1 + ge) / (1 + trials),
        "exceeds_floor": observed > 0 and (1 + ge) / (1 + trials) <= 0.05,
    }


# --------------------------------------------------------------------------- CLI
def _load_json_arg(raw: str) -> dict[str, str]:
    text = Path(raw[1:]).read_text(encoding="utf-8") if raw.startswith("@") else raw
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("expected a JSON object")
    return {str(k): str(v) for k, v in obj.items()}


def _print(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    for key, value in result.items():
        print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("command", choices=["classes", "identify", "refine", "place", "decode", "floor"])
    p.add_argument("matrix", nargs="?", help="ach_matrix.md (or .json) path")
    p.add_argument("--json-matrix", dest="json_matrix", help="JSON matrix path")
    p.add_argument("--candidate", help="JSON object or @file (refine: test->cells; place: cells)")
    p.add_argument("--observation", help="JSON object or @file mapping test id -> C/I")
    p.add_argument("--trials", type=int, default=10000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    path = args.json_matrix or args.matrix
    if not path:
        p.error("a matrix path is required")
    try:
        m = load_matrix(Path(path))
        if args.command == "classes":
            result = summarize(m)
        elif args.command == "identify":
            result = identify(m)
        elif args.command == "floor":
            result = floor_null(m, args.trials, args.seed)
        elif args.command == "refine":
            if not args.candidate:
                p.error("refine needs --candidate")
            result = candidate_refines(m, _load_json_arg(args.candidate))
        elif args.command == "place":
            if not args.candidate:
                p.error("place needs --candidate")
            result = place_candidate(m, _load_json_arg(args.candidate))
        else:
            if not args.observation:
                p.error("decode needs --observation")
            result = decode(m, _load_json_arg(args.observation))
    except (MatrixParseError, ValueError, OSError) as exc:
        print(f"ach_quotient: {exc}", file=sys.stderr)
        return 2
    _print(result, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
