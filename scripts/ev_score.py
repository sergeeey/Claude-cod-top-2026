#!/usr/bin/env python3
"""
EV Scorer — Expected Value scorer for research hypotheses.

Based on ResearchOps Lab v0.4 formula:
  EV_score = falsifiability*0.30 + novelty*0.20 + feasibility*0.20
             + expected_value*0.20 + self_deception_risk_inv*0.10

Gate: if falsifiability == 0.0 → EV_score = 0 (multiplicative kill)

Usage:
  python scripts/ev_score.py                              # interactive
  python scripts/ev_score.py experiments/20260515-foo/   # from experiment.yaml
  python scripts/ev_score.py --file scores.yaml          # batch mode
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# WHY: avoid external dependencies — project rule (no markdown/yaml libs)
# PyYAML is part of stdlib only in 3.11 via tomllib but not yaml; we use
# a lightweight hand-rolled parser for simple key: value YAML structures.


# ─────────────────────────────────────────────
# ANSI colours (no curses, no colorama)
# ─────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
DIM = "\033[2m"


def _color(text: str, code: str) -> str:
    """Wrap text in ANSI colour if stdout is a TTY."""
    if sys.stdout.isatty():
        return f"{code}{text}{RESET}"
    return text


# ─────────────────────────────────────────────
# Domain constants
# ─────────────────────────────────────────────

WEIGHTS: dict[str, float] = {
    "falsifiability": 0.30,
    "novelty": 0.20,
    "feasibility": 0.20,
    "expected_value": 0.20,
    "self_deception_risk_inv": 0.10,
}

DIMENSION_LABELS: dict[str, str] = {
    "falsifiability": "falsifiability    ",
    "novelty": "novelty           ",
    "feasibility": "feasibility       ",
    "expected_value": "expected_value    ",
    "self_deception_risk_inv": "self_deception_inv",
}

DIMENSION_HELP: dict[str, tuple[str, str, str]] = {
    # key: (question, 0.0 description, 1.0 description)
    "falsifiability": (
        "Can this be proven WRONG?",
        '0.0 = unfalsifiable ("X might exist")',
        "1.0 = clearly falsifiable with a specific test",
    ),
    "novelty": (
        "How new is this?",
        "0.0 = known/replicated result",
        "1.0 = genuinely novel contribution",
    ),
    "feasibility": (
        "Can we actually run this experiment?",
        "0.0 = impossible with current resources",
        "1.0 = simple/cheap experiment",
    ),
    "expected_value": (
        "Potential value if confirmed?",
        "0.0 = trivial/marginal impact",
        "1.0 = paradigm shift or major practical impact",
    ),
    "self_deception_risk_inv": (
        "How well protected against self-deception? (1 - risk)",
        "0.0 = very high risk (confirmation bias likely)",
        "1.0 = independent validation guaranteed",
    ),
}

THRESHOLD_REJECT = 0.40
THRESHOLD_REDESIGN = 0.60
THRESHOLD_PROCEED = 0.80

REDESIGN_ADVICE: dict[str, str] = {
    "falsifiability": "Define exact metric + threshold that would FALSIFY this",
    "novelty": "Check null_results/INDEX.md — may already be known",
    "feasibility": "Break into smaller sub-experiments",
    "expected_value": "Reconsider priority vs other experiments",
    "self_deception_risk_inv": "Add independent validator or external dataset",
}

BAR_WIDTH = 10  # characters in progress bar


# ─────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────


@dataclass
class EVScores:
    """Scores for all EV dimensions (each 0.0–1.0)."""

    falsifiability: float = 0.0
    novelty: float = 0.0
    feasibility: float = 0.0
    expected_value: float = 0.0
    self_deception_risk_inv: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "falsifiability": self.falsifiability,
            "novelty": self.novelty,
            "feasibility": self.feasibility,
            "expected_value": self.expected_value,
            "self_deception_risk_inv": self.self_deception_risk_inv,
        }


@dataclass
class EVResult:
    """Computed EV scoring result."""

    hypothesis: str
    scores: EVScores
    weighted: dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    gate_killed: bool = False
    verdict: str = ""
    weakest_dimension: str = ""


# ─────────────────────────────────────────────
# Lightweight YAML parser (no external deps)
# ─────────────────────────────────────────────


def _parse_simple_yaml(text: str) -> dict:
    """
    Parse simple flat-key YAML (key: value, no nesting beyond one level).

    WHY: avoid requiring pyyaml; experiment.yaml uses only simple structures.
    Supports: strings, floats, ints, lists (- item), booleans, null.
    Does NOT support: anchors, multi-document, complex nesting.
    """
    result: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        # top-level key: value
        if ":" in stripped and not stripped.startswith("-"):
            key, _, rest = stripped.partition(":")
            key = key.strip()
            rest = rest.strip()
            # multi-line block scalar (>) — collect following indented lines
            if rest in (">", "|", ">-", "|-", ">+", "|+", ""):
                collected: list[str] = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    # continuation: starts with whitespace
                    if next_line and (next_line[0] in (" ", "\t")):
                        collected.append(next_line.strip())
                        i += 1
                    else:
                        break
                result[key] = " ".join(collected)
                continue
            # list value on same line  [a, b]
            if rest.startswith("["):
                inner = rest.strip("[]")
                result[key] = [v.strip().strip('"').strip("'") for v in inner.split(",")]
                i += 1
                continue
            # plain scalar
            result[key] = _coerce_yaml_scalar(rest)
        i += 1
    return result


def _coerce_yaml_scalar(value: str) -> object:
    """Convert YAML scalar string to Python type."""
    stripped = value.strip().strip('"').strip("'")
    low = stripped.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", ""):
        return None
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return stripped


def _parse_batch_yaml(text: str) -> list[dict]:
    """
    Parse batch scores YAML with multiple hypothesis blocks.

    Expected format:
      hypotheses:
        - hypothesis: "Foo"
          falsifiability: 0.8
          novelty: 0.6
          ...
        - hypothesis: "Bar"
          ...
    """
    results: list[dict] = []
    # Extract hypotheses list (simple approach: split on "- hypothesis:")
    blocks = text.split("- hypothesis:")
    for block in blocks[1:]:  # skip preamble before first item
        lines = ["hypothesis: " + block.lstrip()]
        item_text = "\n".join(lines)
        parsed = _parse_simple_yaml(item_text)
        results.append(parsed)
    return results


# ─────────────────────────────────────────────
# Core calculation
# ─────────────────────────────────────────────


def compute_ev(hypothesis: str, scores: EVScores) -> EVResult:
    """Compute EV score applying weights and gate check."""
    result = EVResult(hypothesis=hypothesis, scores=scores)

    raw = scores.as_dict()

    # Clamp all scores to [0.0, 1.0]
    for k, v in raw.items():
        raw[k] = max(0.0, min(1.0, float(v)))

    # Gate: falsifiability == 0 → kill
    if raw["falsifiability"] == 0.0:
        result.gate_killed = True
        result.total = 0.0
        result.weighted = {k: 0.0 for k in WEIGHTS}
        result.verdict = "REJECT"
        result.weakest_dimension = "falsifiability"
        return result

    weighted: dict[str, float] = {}
    for dim, w in WEIGHTS.items():
        weighted[dim] = raw[dim] * w

    total = sum(weighted.values())

    result.weighted = weighted
    result.total = total

    # Find weakest (lowest raw score)
    result.weakest_dimension = min(raw, key=lambda k: raw[k])

    # Verdict
    if total < THRESHOLD_REJECT:
        result.verdict = "REJECT"
    elif total < THRESHOLD_REDESIGN:
        result.verdict = "REDESIGN"
    elif total < THRESHOLD_PROCEED:
        result.verdict = "PROCEED"
    else:
        result.verdict = "STRONG"

    return result


# ─────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────


def _bar(value: float, width: int = BAR_WIDTH) -> str:
    """Render a simple block progress bar."""
    filled = round(value * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def _verdict_color(verdict: str) -> str:
    """Map verdict string to ANSI colour."""
    mapping = {
        "REJECT": RED,
        "REDESIGN": YELLOW,
        "PROCEED": GREEN,
        "STRONG": CYAN,
    }
    return mapping.get(verdict, RESET)


def render_report(result: EVResult) -> str:
    """Build the human-readable EV scoring report string."""
    lines: list[str] = []
    sep = "═" * 54

    lines.append(_color(f"═══ EV Scoring Report {sep[:34]}", BOLD))
    lines.append(f"Hypothesis: {result.hypothesis}")
    lines.append("")
    lines.append("Dimension Scores:")

    raw = result.scores.as_dict()

    for dim, label in DIMENSION_LABELS.items():
        score = max(0.0, min(1.0, raw[dim]))
        weight = WEIGHTS[dim]
        contrib = result.weighted.get(dim, score * weight)
        bar = _bar(score)
        lines.append(
            f"  {label} [{bar}] {score:.2f}  (weight: {int(weight*100)}%)  "
            f"→ {_color(f'{contrib:.3f}', DIM)}"
        )

    lines.append("")

    # Gate check
    if result.gate_killed:
        lines.append(_color("Gate check: falsifiability == 0 ✗  → MULTIPLICATIVE KILL", RED))
    else:
        lines.append(_color("Gate check: falsifiability > 0 ✅ (no kill)", GREEN))

    lines.append("")
    lines.append(f"EV Score: {_color(f'{result.total:.3f}', BOLD)} / 1.000")
    lines.append(f"Threshold: {THRESHOLD_REDESIGN:.2f} (minimum to proceed)")
    lines.append("")

    # Verdict
    # WHY: _verdict_color reserved for potential future use (e.g. wrapping the full line)
    if result.verdict == "REJECT":
        verdict_line = _color("✗ REJECT — score too weak, do not run", RED)
    elif result.verdict == "REDESIGN":
        verdict_line = _color("⚠  REDESIGN — identify weakest dimension", YELLOW)
    elif result.verdict == "PROCEED":
        verdict_line = _color("✅ PROCEED — score above threshold", GREEN)
    else:
        verdict_line = _color("✅ STRONG hypothesis", CYAN)

    lines.append(f"Verdict: {verdict_line}")

    # Recommendation
    advice = REDESIGN_ADVICE.get(result.weakest_dimension, "")
    if result.verdict in ("REDESIGN", "REJECT") and advice:
        lines.append(f"Recommendation: [{result.weakest_dimension}] {advice}")
    elif result.verdict == "PROCEED" and advice:
        lines.append(
            f"Recommendation: Weakest dimension is [{result.weakest_dimension}] — {advice}"
        )

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Input: interactive
# ─────────────────────────────────────────────


def _prompt_float(prompt: str, dim: str) -> float:
    """Prompt user for a single dimension score with help text."""
    q, low, high = DIMENSION_HELP[dim]
    print(f"\n  {_color(q, BOLD)}")
    print(f"    {_color(low, DIM)}")
    print(f"    {_color(high, DIM)}")
    while True:
        try:
            raw = input(f"  {prompt} [0.0-1.0]: ").strip()
            value = float(raw)
            if 0.0 <= value <= 1.0:
                return value
            print("  Please enter a value between 0.0 and 1.0")
        except ValueError:
            print("  Invalid input — please enter a number like 0.7")


def collect_interactive(hypothesis: str = "") -> tuple[str, EVScores]:
    """Collect scores interactively from stdin."""
    if not hypothesis:
        hypothesis = input("\nHypothesis name/description: ").strip()
        if not hypothesis:
            hypothesis = "(unnamed)"

    print(f"\n{_color('Score each dimension 0.0 – 1.0:', BOLD)}")
    scores = EVScores(
        falsifiability=_prompt_float("falsifiability", "falsifiability"),
        novelty=_prompt_float("novelty", "novelty"),
        feasibility=_prompt_float("feasibility", "feasibility"),
        expected_value=_prompt_float("expected_value", "expected_value"),
        self_deception_risk_inv=_prompt_float("self_deception_inv", "self_deception_risk_inv"),
    )
    return hypothesis, scores


# ─────────────────────────────────────────────
# Input: experiment directory
# ─────────────────────────────────────────────


def _extract_ev_scores_from_yaml(data: dict) -> Optional[EVScores]:
    """
    Extract ev_scores block from parsed experiment.yaml dict.

    Returns None if ev_scores key absent or incomplete.
    """
    ev = data.get("ev_scores")
    if not ev or not isinstance(ev, dict):
        return None

    required = set(WEIGHTS.keys())
    if not required.issubset(ev.keys()):
        return None

    try:
        return EVScores(
            falsifiability=float(ev["falsifiability"]),
            novelty=float(ev["novelty"]),
            feasibility=float(ev["feasibility"]),
            expected_value=float(ev["expected_value"]),
            self_deception_risk_inv=float(ev["self_deception_risk_inv"]),
        )
    except (ValueError, KeyError):
        return None


def load_from_experiment_dir(exp_dir: Path) -> tuple[str, EVScores, Path]:
    """
    Load hypothesis + ev_scores from an experiment directory.

    Returns (hypothesis, scores, yaml_path).
    If ev_scores missing from YAML, falls back to interactive prompting.
    """
    yaml_path = exp_dir / "experiment.yaml"
    if not yaml_path.exists():
        print(f"  experiment.yaml not found in {exp_dir} — falling back to interactive mode.")
        hypothesis, scores = collect_interactive()
        return hypothesis, scores, yaml_path

    text = yaml_path.read_text(encoding="utf-8")
    data = _parse_simple_yaml(text)

    hypothesis = str(data.get("hypothesis", data.get("id", "(unnamed)")))

    existing_scores = _extract_ev_scores_from_yaml(data)
    if existing_scores:
        print(f"  Using existing ev_scores from {yaml_path}")
        return hypothesis, existing_scores, yaml_path

    # Fall back to interactive
    print(f"  No ev_scores in {yaml_path} — prompting for scores.")
    _, scores = collect_interactive(hypothesis)
    return hypothesis, scores, yaml_path


def write_ev_scores_to_yaml(yaml_path: Path, scores: EVScores, total: float) -> None:
    """
    Append/update ev_scores block in experiment.yaml.

    WHY: write back so the score is persisted alongside the experiment,
    enabling future re-reads without re-prompting.
    """
    if not yaml_path.exists():
        return

    text = yaml_path.read_text(encoding="utf-8")

    ev_block = (
        "\n# EV Scores (auto-written by ev_score.py)\n"
        "ev_scores:\n"
        f"  falsifiability: {scores.falsifiability}\n"
        f"  novelty: {scores.novelty}\n"
        f"  feasibility: {scores.feasibility}\n"
        f"  expected_value: {scores.expected_value}\n"
        f"  self_deception_risk_inv: {scores.self_deception_risk_inv}\n"
        f"  total: {total:.3f}\n"
    )

    # Remove existing ev_scores block if present
    if "ev_scores:" in text:
        # WHY: simple removal — find the block and strip it, not full re-parse
        lines = text.splitlines(keepends=True)
        out_lines: list[str] = []
        inside_block = False
        for line in lines:
            if line.strip().startswith("ev_scores:") or line.strip().startswith("# EV Scores"):
                inside_block = True
                continue
            if inside_block:
                # Block ends when we hit a non-indented non-comment line
                if line and line[0] not in (" ", "\t", "#", "\n"):
                    inside_block = False
                    out_lines.append(line)
                # else skip the block line
                continue
            out_lines.append(line)
        text = "".join(out_lines)

    yaml_path.write_text(text.rstrip() + ev_block, encoding="utf-8")
    print(f"  ev_scores written back to {yaml_path}")


# ─────────────────────────────────────────────
# Input: batch file
# ─────────────────────────────────────────────


def run_batch(scores_file: Path) -> list[EVResult]:
    """
    Parse a batch YAML file and compute EV for each hypothesis.

    Expected YAML structure:
      hypotheses:
        - hypothesis: "Foo"
          falsifiability: 0.8
          novelty: 0.6
          feasibility: 0.7
          expected_value: 0.5
          self_deception_risk_inv: 0.8
        - hypothesis: "Bar"
          ...
    """
    if not scores_file.exists():
        print(f"Error: file not found — {scores_file}", file=sys.stderr)
        sys.exit(1)

    text = scores_file.read_text(encoding="utf-8")
    items = _parse_batch_yaml(text)

    if not items:
        print(f"Error: no hypotheses found in {scores_file}", file=sys.stderr)
        sys.exit(1)

    results: list[EVResult] = []
    for item in items:
        hyp = str(item.get("hypothesis", "(unnamed)"))
        try:
            sc = EVScores(
                falsifiability=float(item.get("falsifiability", 0.0)),
                novelty=float(item.get("novelty", 0.0)),
                feasibility=float(item.get("feasibility", 0.0)),
                expected_value=float(item.get("expected_value", 0.0)),
                self_deception_risk_inv=float(item.get("self_deception_risk_inv", 0.0)),
            )
        except (ValueError, TypeError) as exc:
            print(f"Warning: skipping '{hyp}' — parse error: {exc}", file=sys.stderr)
            continue
        results.append(compute_ev(hyp, sc))

    return results


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EV Scorer — Expected Value scorer for research hypotheses",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "experiment_dir",
        nargs="?",
        type=Path,
        help="Path to experiment directory (must contain experiment.yaml)",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        metavar="YAML",
        help="Batch mode: YAML file with multiple hypotheses",
    )
    return parser


def main() -> None:
    """Main entry point."""
    parser = _build_arg_parser()
    args = parser.parse_args()

    try:
        if args.file:
            # ── Batch mode ──────────────────────────────────────
            results = run_batch(args.file)
            for r in results:
                print()
                print(render_report(r))
                print()

        elif args.experiment_dir:
            # ── Experiment directory mode ───────────────────────
            exp_dir = args.experiment_dir
            if not exp_dir.is_dir():
                print(f"Error: {exp_dir} is not a directory", file=sys.stderr)
                sys.exit(1)

            hypothesis, scores, yaml_path = load_from_experiment_dir(exp_dir)
            result = compute_ev(hypothesis, scores)

            print()
            print(render_report(result))

            # Write back
            write_ev_scores_to_yaml(yaml_path, scores, result.total)

        else:
            # ── Interactive mode ────────────────────────────────
            hypothesis, scores = collect_interactive()
            result = compute_ev(hypothesis, scores)

            print()
            print(render_report(result))

    except KeyboardInterrupt:
        # WHY: clean exit on Ctrl-C — no traceback shown to user
        print("\n\nAborted.", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
