#!/usr/bin/env python3
"""PostToolUse hook: compute independence_score from dependency_graph.yaml.

WHY: ELAI axis I (Independence) is the main gap in our verification stack.
Two paths that share model family, dataset, and key libraries can have
correlated blind spots — the same wrong assumption silently passes both.
This hook makes the overlap explicit and warns when paths are too similar.

Fires on: PostToolUse(Write|Edit) matching **/experiments/**/dependency_graph.yaml

Algorithm:
  Each dependency dimension carries a weight (sums to 1.0).
  A dimension contributes its full weight to the score when paths DIFFER on it,
  zero weight when they SHARE the same non-null value.
  Null in both paths → dimension skipped (not counted either way).
  Null in only one path → treated as a difference (can't verify overlap).

Thresholds:
  HIGH   (≥ 0.70) — paths are genuinely independent; soft pass
  MEDIUM (0.40–0.69) — partial independence; warn, note shared dimensions
  LOW    (< 0.40) — correlated paths; promotion blocked if claimed as independent

Enforcement: soft nudge (additionalContext). Hard block would require a
promotion_gate_guard integration — added as a future step.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# WHY: sys.path injection instead of installed package — consistent with
# every other hook in this repo (see hooks/CLAUDE.md, "Adding a New Hook").
sys.path.insert(0, str(Path(__file__).parent))

from lib.runtime import emit_hook_result

# ---------------------------------------------------------------------------
# Dimension weights — must sum to 1.0
# ---------------------------------------------------------------------------

_WEIGHTS: dict[str, float] = {
    "model_family": 0.30,  # correlated training data / biases
    "dataset": 0.25,  # shared measurement space
    "code_commit": 0.20,  # identical bugs / conventions
    "libraries": 0.15,  # numeric / algorithmic choices
    "retrieval_snapshot": 0.07,  # shared knowledge gaps
    "definition_of_metric": 0.03,  # shared operationalisation bias
}

assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

_TIER_HIGH = 0.70
_TIER_MEDIUM = 0.40

_WARN_THRESHOLD = _TIER_MEDIUM  # below this → explicit warning
_MSG_HOOK = "independence-scorer"


# ---------------------------------------------------------------------------
# Core logic (pure functions, tested independently)
# ---------------------------------------------------------------------------


def _normalise(val: object) -> str | None:
    """Coerce a YAML scalar to a canonical string for comparison, or None."""
    if val is None:
        return None
    s = str(val).strip().lower()
    return s if s not in {"", "null", "none", "~"} else None


def _library_major_set(libs: list | None) -> set[str]:
    """Return a set of 'package==major' tokens from a list of version specs.

    WHY major only: minor patch differences (numpy==1.26.0 vs 1.26.4) are
    irrelevant to algorithmic behaviour; major differences are.
    """
    if not libs:
        return set()
    result: set[str] = set()
    for entry in libs:
        s = str(entry).strip().lower()
        # "numpy==1.26.0"  → "numpy==1"
        m = re.match(r"([a-z0-9_\-]+)==(\d+)", s)
        if m:
            result.add(f"{m.group(1)}=={m.group(2)}")
        elif s:
            result.add(s.split("==")[0])
    return result


def compute_independence(
    path_a: dict,
    path_b: dict,
) -> tuple[float, list[dict], list[dict]]:
    """Return (score, shared_deps, dimension_detail).

    shared_deps: list of {field, value} dicts for shared non-null dimensions.
    dimension_detail: list of {dimension, a_val, b_val, shared, weight, contribution}
      for every dimension that was evaluated.

    Score is the sum of weights for dimensions where A and B differ.
    Fully null dimensions (both null) are excluded from numerator AND denominator
    so that missing data doesn't inflate the score.
    """
    shared_deps: list[dict] = []
    detail: list[dict] = []
    active_weight = 0.0
    score_numerator = 0.0

    for dim, weight in _WEIGHTS.items():
        if dim == "libraries":
            a_val_raw = path_a.get("libraries") or []
            b_val_raw = path_b.get("libraries") or []
            a_set = _library_major_set(a_val_raw if isinstance(a_val_raw, list) else [])
            b_set = _library_major_set(b_val_raw if isinstance(b_val_raw, list) else [])

            # Both empty → skip dimension
            if not a_set and not b_set:
                detail.append(
                    {
                        "dimension": dim,
                        "a_val": None,
                        "b_val": None,
                        "shared": False,
                        "weight": weight,
                        "contribution": 0.0,
                        "skipped": True,
                    }
                )
                continue

            overlap = a_set & b_set
            # Jaccard-weighted: overlap / union
            union = a_set | b_set
            overlap_ratio = len(overlap) / len(union) if union else 0.0
            contribution = weight * (1.0 - overlap_ratio)

            if overlap:
                shared_deps.extend({"field": "libraries", "value": v} for v in sorted(overlap))

            detail.append(
                {
                    "dimension": dim,
                    "a_val": sorted(a_set),
                    "b_val": sorted(b_set),
                    "shared": bool(overlap),
                    "overlap_ratio": round(overlap_ratio, 3),
                    "weight": weight,
                    "contribution": round(contribution, 4),
                    "skipped": False,
                }
            )
            active_weight += weight
            score_numerator += contribution
            continue

        a_raw = _normalise(path_a.get(dim))
        b_raw = _normalise(path_b.get(dim))

        # Both null → skip dimension entirely
        if a_raw is None and b_raw is None:
            detail.append(
                {
                    "dimension": dim,
                    "a_val": None,
                    "b_val": None,
                    "shared": False,
                    "weight": weight,
                    "contribution": 0.0,
                    "skipped": True,
                }
            )
            continue

        active_weight += weight
        is_shared = a_raw is not None and b_raw is not None and a_raw == b_raw
        contribution = 0.0 if is_shared else weight

        if is_shared:
            shared_deps.append({"field": dim, "value": a_raw})

        detail.append(
            {
                "dimension": dim,
                "a_val": a_raw,
                "b_val": b_raw,
                "shared": is_shared,
                "weight": weight,
                "contribution": round(contribution, 4),
                "skipped": False,
            }
        )
        score_numerator += contribution

    # Normalise against active (non-skipped) weight
    score = score_numerator / active_weight if active_weight > 0 else 1.0
    return round(score, 3), shared_deps, detail


def tier(score: float) -> str:
    if score >= _TIER_HIGH:
        return "HIGH"
    if score >= _TIER_MEDIUM:
        return "MEDIUM"
    return "LOW"


def _parse_yaml_paths(content: str) -> tuple[dict, dict] | None:
    """Minimal YAML extractor — avoids PyYAML dependency.

    WHY: hooks run without package installs; only stdlib is available.
    This covers the simple flat+list structure in dependency_graph.yaml.
    Returns (path_a_dict, path_b_dict) or None if file is template/unparseable.
    """
    import re as _re

    # Quick check: unfilled template — placeholder string present
    if "<YYYYMMDD-short-slug>" in content:
        return None

    # Find path_a and path_b blocks by indented section
    def _extract_block(name: str) -> dict:
        pattern = _re.compile(rf"^  {_re.escape(name)}:\s*\n((?:    .*\n?)*)", _re.MULTILINE)
        m = pattern.search(content)
        if not m:
            return {}
        block = m.group(1)
        result: dict = {}
        for line in block.splitlines():
            kv = _re.match(r"    (\w+):\s*(.*)", line)
            if not kv:
                continue
            key = kv.group(1)
            raw = kv.group(2).strip()
            if raw.startswith("[") and raw.endswith("]"):
                # Parse inline list: [a, b, c] or []
                inner = raw[1:-1].strip()
                result[key] = (
                    [x.strip().strip("\"'") for x in inner.split(",") if x.strip()] if inner else []
                )
            elif raw.lower() in ("null", "~", ""):
                result[key] = None
            else:
                result[key] = raw.strip("\"'")
        return result

    a = _extract_block("path_a")
    b = _extract_block("path_b")
    if not a and not b:
        return None
    return a, b


# ---------------------------------------------------------------------------
# YAML write-back helpers
# ---------------------------------------------------------------------------


def _yaml_list(items: list[dict]) -> str:
    if not items:
        return "[]"
    lines = []
    for item in items:
        parts = ", ".join(f'{k}: "{v}"' for k, v in item.items())
        lines.append(f"  - {{{parts}}}")
    return "\n" + "\n".join(lines)


def _update_score_in_content(content: str, score: float, tier_val: str, shared: list[dict]) -> str:
    """Rewrite independence_score, independence_tier, shared_dependencies lines."""

    def _replace(pattern: str, replacement: str, text: str) -> str:
        return re.sub(pattern, replacement, text, count=1, flags=re.MULTILINE)

    content = _replace(
        r"^independence_score:.*$",
        f"independence_score: {score}",
        content,
    )
    content = _replace(
        r"^independence_tier:.*$",
        f"independence_tier: {tier_val}",
        content,
    )
    content = _replace(
        r"^shared_dependencies:.*$",
        f"shared_dependencies:{_yaml_list(shared)}",
        content,
    )
    return content


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------


def _is_dependency_graph(file_path: str) -> bool:
    p = Path(file_path)
    return p.name == "dependency_graph.yaml" and "experiments" in set(p.parts)


def main() -> None:
    # WHY: recursion guard — avoid loops inside Agent SDK sub-invocations.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    if data.get("tool_name", "") not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_dependency_graph(file_path):
        sys.exit(0)

    # Get written content
    content = tool_input.get("content") or ""
    if not content:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            sys.exit(0)

    parsed = _parse_yaml_paths(content)
    if parsed is None:
        sys.exit(0)  # template or malformed — skip silently

    path_a, path_b = parsed
    score, shared, detail = compute_independence(path_a, path_b)
    t = tier(score)

    # Write score back to file
    try:
        updated = _update_score_in_content(content, score, t, shared)
        Path(file_path).write_text(updated, encoding="utf-8")
    except OSError:
        pass  # WHY: best-effort write-back; don't break the hook on FS errors

    # Build message
    lines = [
        f"[{_MSG_HOOK}] Independence score: {score:.3f} → tier: {t}",
    ]
    if shared:
        labels = ", ".join(d.get("field", "?") for d in shared)
        lines.append(f"  Shared dimensions: {labels}")
    if t == "LOW":
        lines.append(
            "  ⚠️  LOW independence — paths likely share correlated blind spots. "
            "Use a genuinely different model family, dataset, and code path before "
            "counting this as an independent reconstruction."
        )
    elif t == "MEDIUM":
        lines.append(
            "  ⚠️  MEDIUM independence — some shared dimensions. Consider diversifying "
            f"the higher-weight fields: {[d for d, w in _WEIGHTS.items() if w >= 0.15]}."
        )
    else:
        lines.append("  ✓ HIGH independence — paths are sufficiently differentiated.")

    msg = "\n".join(lines)
    emit_hook_result(msg, is_error=(t == "LOW"))


if __name__ == "__main__":
    main()
