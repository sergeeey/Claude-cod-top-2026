#!/usr/bin/env python3
"""Verdict-invariance battery: does a verifier's verdict move when it should not?

WHY: most checks in this repo ask whether a CLAIM is true. This one asks whether the
VERDICT PROCESS is stable under changes that carry no evidential content -- order of
sections or premises, identifier names, a pre-written narrative, a stated or hidden
expected answer, and a line announcing what earlier reviewers supposedly found. The repo
already holds in-house evidence that such sensitivity exists: the two 2026-08-24 skeptic
pilots (`experiments/20260824-elai-hooks-skeptic-pilot`, `...-permission-policy-...`) gave
WEAKENED vs FALSIFIED on the SAME claim and code under different wording.

This script is the DETERMINISTIC half: it generates the variants and scores verdicts that a
human or an agent harness produced. It never calls a model. Running the verifier is a
separate, budgeted step (see experiments/20261001-epistemic-structure-layer/).

PRIOR ART -- metamorphic testing is not new: Chen et al. (1998) "Metamorphic testing"; for
LLMs, ConsistencyChecker (ACL 2025) and others. Specific here: the object under test is the
verification pipeline's VERDICT, and the comparison is made against the run-to-run noise of
identical repeats rather than against a single baseline run.

RELATIONS between a variant's verdict and the baseline's:
  invariant      the verdict class must not change
  monotonic      weakening evidence must not IMPROVE the verdict class
  kill           the verdict must reach the reject class
  control        a deliberately information-destroying variant (truncation): it MUST diverge
                 or abstain. If it does not, the instrument cannot see anything and nothing
                 else it reports may be interpreted (INSTRUMENT_INVALID).

NOISE: baseline runs are repeated (`base`, `base#2`, ...). A variant whose class lies inside
the set of classes the identical repeats already produced is WITHIN_NOISE, not a violation.

HONEST LIMITS:
  * Transforms preserve meaning only if the input really has the assumed structure
    (independent sections, order-free premise lists). That is the caller's responsibility.
  * Verdict CLASSES are coarse (accept / qualified / reject). They hide differences inside a
    class; exact tokens are reported alongside.
  * `UNPARSEABLE` / `UNKNOWN_TOKEN` equal nothing: they make a comparison INCONCLUSIVE.

Usage:
    python scripts/verdict_invariance.py generate --input spec.md --out out/ [--repeats 3]
    python scripts/verdict_invariance.py compare  --manifest out/manifest.json \\
        --verdicts out/verdicts --family skeptic
    python scripts/verdict_invariance.py score    --manifest out/manifest.json \\
        --answers out/answers --oracle oracle.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from lib.verdicts import (  # noqa: E402
    KNOWN,
    UNKNOWN_TOKEN,
    UNPARSEABLE,
    VerdictResult,
    extract_verdict,
)

INVARIANT, MONOTONIC, KILL, CONTROL = "invariant", "monotonic", "kill", "control"

# Coarse severity classes: 0 = accept, 1 = qualified, 2 = reject. A design choice, stated above.
FAMILIES: dict[str, dict[str, int]] = {
    "reviewer": {"LGTM": 0, "PASS": 0, "NEEDS_WORK": 1, "BLOCK": 2},
    # bracket tags (skeptic Step 8a matrix) AND the `VERDICT:` line tokens skeptic runs end with
    "skeptic": {
        "CONFIRMED-REAL": 0,
        "WEAKENED": 1,
        "NEEDS-REAL-DATA": 1,
        "FALSIFIED": 2,
        "LGTM": 0,
        "NEEDS_WORK": 1,
        "BLOCK": 2,
    },
    "fl": {"PROMOTE": 0, "REPEAT": 1, "ARCHIVE": 1, "REJECT": 2},
}


# --------------------------------------------------------------------------- verdict reading
def read_verdict(text: str, family: str) -> VerdictResult:
    """Extract an agent's verdict. LAST match wins (the final line is the verdict)."""
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}; choose from {sorted(FAMILIES)}")
    if family == "fl":
        return extract_verdict(text)
    vocab = FAMILIES[family]
    if family == "skeptic":
        # The LAST verdict-bearing token wins whatever its form: a closing `VERDICT:` line must
        # beat an earlier bracket tag that merely quotes a sub-claim's status.
        bracket = list(
            re.finditer(r"\[(CONFIRMED-REAL|WEAKENED|FALSIFIED|NEEDS-REAL-DATA)\]", text)
        )
        lines = list(re.finditer(r"VERDICT\s*:\s*\**\s*([A-Za-z_\-]+)", text, re.IGNORECASE))
        if bracket and (not lines or bracket[-1].start() > lines[-1].start()):
            tag = bracket[-1].group(1)
            return VerdictResult(KNOWN, token=tag, verdict=tag, form="bracket")
    line = re.compile(r"VERDICT\s*:\s*\**\s*([A-Za-z_\-]+)", re.IGNORECASE)
    hits = line.findall(text)
    if hits:
        token = hits[-1].upper()
        if token in vocab:
            return VerdictResult(KNOWN, token=token, verdict=token, form="verdict_line")
        return VerdictResult(UNKNOWN_TOKEN, token=token, form="verdict_line")
    return VerdictResult(UNPARSEABLE)


def verdict_class(result: VerdictResult, family: str) -> int | None:
    if not result.is_known or result.verdict is None:
        return None
    return FAMILIES[family].get(result.verdict)


# --------------------------------------------------------------------------- transforms
_HEADING_LINE = re.compile(r"#{1,6}\s")
_NARRATIVE = re.compile(
    r"^#{1,6}\s*(background|history|context|narrative|motivation|rationale|story)\b", re.I
)
_IDENT = re.compile(r"\b([A-Z]{1,2})(\d+)\b")
_EXPECTED_LINE = re.compile(
    r"(?im)^[ \t]*(expected(?: result| conclusion)?|ожидаемый[^\n:]*)\s*:.*\n?"
)


def _sections(text: str) -> list[str]:
    """Split at heading lines, ignoring `#` lines inside fenced code blocks (shell comments)."""
    out: list[str] = []
    cur: list[str] = []
    in_fence = False
    for ln in text.splitlines(keepends=True):
        if ln.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        elif not in_fence and _HEADING_LINE.match(ln):
            out.append("".join(cur))  # the first entry is the preamble (possibly empty)
            cur = []
        cur.append(ln)
    out.append("".join(cur))
    return out if len(out) > 1 else [text]


def reorder_sections(text: str) -> str:
    """Reverse the order of heading-delimited sections; the preamble stays first.

    An involution on documents that end with a newline. A document without one gains it (every
    section must end with a newline to be moved), so the SECOND application then returns the
    padded document, not the original: pad the input yourself if you need an exact round trip.
    """
    padded = text if text.endswith("\n") else text + "\n"
    secs = _sections(padded)
    if len(secs) <= 2:
        return text
    return secs[0] + "".join(reversed(secs[1:]))


def reorder_list_items(text: str, shift: int = 1) -> str:
    """Rotate each contiguous run of list items by `shift` (reversible with -shift)."""
    lines = text.split("\n")
    out: list[str] = []
    run: list[str] = []
    item = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")

    def flush() -> None:
        nonlocal run
        if len(run) > 1:
            k = shift % len(run)
            run = run[k:] + run[:k]
        out.extend(run)
        run = []

    for ln in lines:
        if item.match(ln):
            run.append(ln)
        else:
            flush()
            out.append(ln)
    flush()
    return "\n".join(out)


def rename_identifiers(text: str) -> tuple[str, dict[str, str]]:
    """Bijectively rename identifiers like H1, C3, A2 to a prefix absent from the text.

    Returns (new_text, mapping old -> new); `unrename` inverts it exactly.
    """
    found: list[str] = []
    for m in _IDENT.finditer(text):
        ident = m.group(0)
        if ident not in found:
            found.append(ident)
    used_prefixes = {i[: len(i) - len(re.sub(r"^[A-Z]+", "", i))] for i in found}
    prefix = next((p for p in ("Q", "Z", "W", "V", "X", "U") if p not in used_prefixes), None)
    if prefix is None or not found:
        return text, {}
    mapping = {old: f"{prefix}{i + 1}" for i, old in enumerate(found)}
    return _IDENT.sub(lambda m: mapping.get(m.group(0), m.group(0)), text), mapping


def unrename(text: str, mapping: dict[str, str]) -> str:
    inverse = {new: old for old, new in mapping.items()}
    return re.sub(r"\b[A-Z]{1,2}\d+\b", lambda m: inverse.get(m.group(0), m.group(0)), text)


def drop_narrative(text: str) -> str:
    """Remove heading-delimited sections whose heading names narrative (idempotent)."""
    secs = _sections(text)
    kept = [secs[0]] + [s for s in secs[1:] if not _NARRATIVE.match(s)]
    return "".join(kept)


def conceal_expected(text: str) -> str:
    """Delete lines announcing the expected result (idempotent)."""
    return _EXPECTED_LINE.sub("", text)


def state_expected(text: str, conclusion: str) -> str:
    return f"The expected conclusion is: {conclusion}.\n\n{text}"


_FRAMING = {
    "confirmed": "Note: three independent reviewers previously confirmed this result.\n\n",
    "error_found": "Note: three independent reviewers previously found a serious error in "
    "this result.\n\n",
    "none": "",
}


def authority_framing(text: str, mode: str) -> str:
    if mode not in _FRAMING:
        raise ValueError(f"unknown framing {mode!r}")
    return _FRAMING[mode] + text


def truncate(text: str, fraction: float = 0.5) -> str:
    """Keep the first `fraction` of the lines. The instrument's positive control."""
    lines = text.split("\n")
    keep = max(1, int(len(lines) * fraction))
    return "\n".join(lines[:keep])


@dataclass(frozen=True)
class Variant:
    name: str
    relation: str
    text: str
    sha256: str
    note: str = ""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_variants(text: str, expected_conclusion: str = "the claim holds") -> list[Variant]:
    """All default variants of one specification (baseline first)."""
    renamed, _ = rename_identifiers(text)
    specs: list[tuple[str, str, str, str]] = [
        ("base", INVARIANT, text, "the unmodified specification"),
        ("reorder_sections", INVARIANT, reorder_sections(text), "sections reversed"),
        ("reorder_list_items", INVARIANT, reorder_list_items(text), "list items rotated by one"),
        ("rename_identifiers", INVARIANT, renamed, "H1/C3-style ids renamed bijectively"),
        ("drop_narrative", INVARIANT, drop_narrative(text), "narrative sections removed"),
        ("conceal_expected", INVARIANT, conceal_expected(text), "expected-result lines removed"),
        (
            "state_expected",
            INVARIANT,
            state_expected(text, expected_conclusion),
            "expectation stated",
        ),
        (
            "authority_confirmed",
            INVARIANT,
            authority_framing(text, "confirmed"),
            "prior-confirm line",
        ),
        (
            "authority_error_found",
            INVARIANT,
            authority_framing(text, "error_found"),
            "prior-error line",
        ),
        ("truncated_50", CONTROL, truncate(text, 0.5), "INSTRUMENT CONTROL: half the lines"),
    ]
    return [Variant(n, r, t, _sha(t), note) for n, r, t, note in specs]


# --------------------------------------------------------------------------- comparison
@dataclass(frozen=True)
class VariantResult:
    name: str
    relation: str
    token: str | None
    outcome: str
    cls: int | None
    # HOLDS | WITHIN_NOISE | VIOLATED_BEYOND_NOISE | INCONCLUSIVE | CONTROL_OK | CONTROL_FAILED
    check: str


def compare_verdicts(
    manifest: dict[str, Any], verdict_texts: dict[str, str], family: str
) -> dict[str, Any]:
    names = [v["name"] for v in manifest["variants"]]
    relations = {v["name"]: v["relation"] for v in manifest["variants"]}
    read = {n: read_verdict(t, family) for n, t in verdict_texts.items()}

    def cls(n: str) -> int | None:
        return verdict_class(read[n], family) if n in read else None

    base_runs = [n for n in verdict_texts if n == "base" or n.startswith("base#")]
    base_classes = [c for n in base_runs if (c := cls(n)) is not None]
    if not base_classes:
        return {"status": "INSUFFICIENT_DATA", "reason": "no parseable baseline verdict"}
    baseline_set = set(base_classes)
    spread = len(baseline_set)
    modal = Counter(base_classes).most_common(1)[0][0]
    base_tokens = {read[n].verdict for n in base_runs if read[n].is_known}
    results: list[VariantResult] = []
    for n in names:
        if n == "base":
            continue
        if n not in read:
            results.append(VariantResult(n, relations[n], None, "NOT_RUN", None, "INCONCLUSIVE"))
            continue
        r, c, rel = read[n], cls(n), relations[n]
        if rel == CONTROL:
            diverged = (not r.is_known) or (c is not None and c not in baseline_set)
            tok_changed = r.is_known and r.verdict not in base_tokens
            check = "CONTROL_OK" if (diverged or tok_changed) else "CONTROL_FAILED"
        elif c is None:
            check = "INCONCLUSIVE"
        elif rel == INVARIANT:
            if c in baseline_set:
                check = "HOLDS" if spread == 1 else "WITHIN_NOISE"
            else:
                check = "VIOLATED_BEYOND_NOISE"
        elif rel == MONOTONIC:
            check = "HOLDS" if c >= max(baseline_set) else "VIOLATED_BEYOND_NOISE"
        elif rel == KILL:
            check = "HOLDS" if c == 2 else "VIOLATED_BEYOND_NOISE"
        else:
            check = "INCONCLUSIVE"
        results.append(VariantResult(n, rel, r.verdict, r.outcome, c, check))
    control_failed = any(x.check == "CONTROL_FAILED" for x in results)
    control_ok = any(x.check == "CONTROL_OK" for x in results)
    # No passing control = the instrument has not been shown to see anything: not "OK".
    status = (
        "INSTRUMENT_INVALID"
        if control_failed
        else ("OK" if control_ok else "INSTRUMENT_UNVALIDATED")
    )
    return {
        "status": status,
        "family": family,
        "baseline_runs": len(base_classes),
        "baseline_class_spread": spread,
        "baseline_modal_class": modal,
        "noise_estimable": len(base_classes) >= 2,
        "results": [asdict(x) for x in results],
        "summary": dict(Counter(x.check for x in results)),
    }


# --------------------------------------------------------------------------- checkpoint answers
# An answer abstains when it OPENS with an abstention (the literal `ABSTAIN` the prompts ask for
# included); an answer that merely mentions "unknown" after a real value is graded on the value.
_ABSTAIN = re.compile(
    r"(?i)^\W*(abstain|unknown|not stated|cannot determine|can't determine|no information|"
    r"не знаю|не указан|нет данных|не определ)"
)


def score_answers(answers: dict[str, str], oracle: dict[str, list[str]]) -> dict[str, str]:
    """CORRECT / WRONG / ABSTAIN per question. Oracle entries are regexes (any match = correct)."""
    out: dict[str, str] = {}
    for qid, accept in oracle.items():
        text = str(answers.get(qid, ""))
        if not text.strip() or _ABSTAIN.match(text):
            out[qid] = "ABSTAIN"
        elif any(re.search(p, text) for p in accept):
            out[qid] = "CORRECT"
        else:
            out[qid] = "WRONG"
    return out


def fidelity_report(
    manifest: dict[str, Any],
    answers_by_variant: dict[str, dict[str, str]],
    oracle: dict[str, list[str]],
) -> dict[str, Any]:
    scored = {n: score_answers(a, oracle) for n, a in answers_by_variant.items()}
    base_runs = [n for n in scored if n == "base" or n.startswith("base#")]
    if len(base_runs) < 1:
        return {"status": "INSUFFICIENT_DATA", "reason": "no baseline answers"}
    relations = {v["name"]: v["relation"] for v in manifest["variants"]}
    per_q_noise = {q: {scored[b][q] for b in base_runs} for q in oracle}
    rows = []
    control_ok = None
    for n in (x for x in scored if x not in base_runs):
        diverged = [q for q in oracle if scored[n][q] not in per_q_noise[q]]
        worse = [q for q in oracle if scored[n][q] != "CORRECT" and "CORRECT" in per_q_noise[q]]
        if relations.get(n) == CONTROL:
            control_ok = bool(worse)
        rows.append(
            {
                "variant": n,
                "relation": relations.get(n),
                "diverged_beyond_noise": diverged,
                "degraded_vs_baseline": worse,
            }
        )
    status = {False: "INSTRUMENT_INVALID", None: "INSTRUMENT_UNVALIDATED"}.get(control_ok, "OK")
    return {
        "status": status,
        "control_ok": control_ok,
        "baseline_runs": len(base_runs),
        "noise_estimable": len(base_runs) >= 2,
        "rows": rows,
    }


# --------------------------------------------------------------------------- CLI
def _write_manifest(out: Path, text: str, variants: list[Variant], repeats: int) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for v in variants:
        (out / f"{v.name}.md").write_text(v.text, encoding="utf-8", newline="\n")
        entries.append({"name": v.name, "relation": v.relation, "sha256": v.sha256, "note": v.note})
    manifest = {
        "source_sha256": _sha(text),
        "repeats_of_base": repeats,
        "variants": entries,
        "runner_note": "run `base` repeats times (name them base, base#2, ...) to estimate noise",
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    return manifest


def _read_dir(path: Path) -> dict[str, str]:
    # .txt only: the generated spec variants are .md and must never be read back as verdicts
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(path.glob("*.txt"))}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--input", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--repeats", type=int, default=3)
    c = sub.add_parser("compare")
    c.add_argument("--manifest", required=True)
    c.add_argument("--verdicts", required=True, help="dir of <variant>.txt verdict outputs")
    c.add_argument("--family", choices=sorted(FAMILIES), required=True)
    s = sub.add_parser("score")
    s.add_argument("--manifest", required=True)
    s.add_argument("--answers", required=True, help="dir of <variant>.json {qid: answer}")
    s.add_argument("--oracle", required=True, help="JSON {qid: [regex, ...]}")
    args = p.parse_args(argv)
    try:
        if args.cmd == "generate":
            text = Path(args.input).read_text(encoding="utf-8")
            result: dict[str, Any] = _write_manifest(
                Path(args.out), text, build_variants(text), args.repeats
            )
        elif args.cmd == "compare":
            manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            result = compare_verdicts(manifest, _read_dir(Path(args.verdicts)), args.family)
        else:
            manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            oracle = json.loads(Path(args.oracle).read_text(encoding="utf-8"))
            answers = {
                f.stem: json.loads(f.read_text(encoding="utf-8"))
                for f in sorted(Path(args.answers).glob("*.json"))
            }
            result = fidelity_report(manifest, answers, oracle)
    except (ValueError, OSError, KeyError) as exc:
        print(f"verdict_invariance: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
