#!/usr/bin/env python3
"""Scan and verify hypertarget/hyperlink numeric references in LaTeX files.

Two modes:
  --scan: Report all \\hypertarget and \\hyperlink usage in a .tex file
  --verify: Cross-reference targets vs links for integrity

Self-contained: uses only stdlib.

Extracted from data-to-paper's ref_numeric_values.py.

Usage:
    python ref_numeric_values.py --scan main.tex --output report.json
    python ref_numeric_values.py --verify main.tex --code-output results.txt
    python ref_numeric_values.py --scan main.tex
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from typing import Optional


TARGET = r"\hypertarget"
LINK = r"\hyperlink"


def get_numeric_value_pattern(must_follow: Optional[str] = None, allow_commas: bool = True) -> str:
    """Get a regex pattern for numeric values."""
    prefix = ""
    if must_follow is not None:
        prefix = f"(?<={must_follow})"
    if allow_commas:
        pattern = r"(?:[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:e[-+]?\d+)?|\d{1,3}(?:,\d{3})+)(?!\d)"
    else:
        pattern = r"[-+]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
    return prefix + pattern


NUMERIC_PATTERN = get_numeric_value_pattern(must_follow=r"[$,{<=\s\n\(\[]", allow_commas=True)


@dataclass
class ReferencedValue:
    """A numeric value with a reference label."""

    value: str
    label: Optional[str] = None
    is_target: bool = True
    line_num: int = 0

    @property
    def command(self) -> str:
        return TARGET if self.is_target else LINK


def get_hyperlink_pattern(is_target: bool = False) -> str:
    """Get regex pattern for \\hypertarget or \\hyperlink commands."""
    command = re.escape(TARGET if is_target else LINK)
    return rf"{command}\{{(?P<reference>[^}}]*)\}}\{{(?P<value>[^}}]*)\}}"


_COMMENT_RE = re.compile(r"(?<!\\)%.*$")


def _strip_comment(line: str) -> str:
    """Drop an unescaped LaTeX comment: a commented \\hypertarget creates no anchor."""
    return _COMMENT_RE.sub("", line)


def _parse_code_targets(code_output: str) -> dict[str, str]:
    """Collect every \\hypertarget in the code output; one line may hold several."""
    values: dict[str, str] = {}
    pattern = get_hyperlink_pattern(is_target=True)
    for line in code_output.splitlines():
        for match in re.finditer(pattern, _strip_comment(line)):
            values[match.group("reference")] = match.group("value")
    return values


def find_references(text: str, is_targets: bool = False) -> list[ReferencedValue]:
    """Find all hypertarget or hyperlink references in text."""
    pattern = get_hyperlink_pattern(is_targets)
    refs = []
    for i, line in enumerate(text.splitlines(), 1):
        for match in re.finditer(pattern, _strip_comment(line)):
            refs.append(
                ReferencedValue(
                    value=match.group("value"),
                    label=match.group("reference"),
                    is_target=is_targets,
                    line_num=i,
                )
            )
    return refs


def find_numeric_values(text: str, remove_hyperlinks: bool = True) -> list[str]:
    """Find all unreferenced numeric values in text."""
    text = " " + text + " "
    if remove_hyperlinks:
        text = re.sub(get_hyperlink_pattern(is_target=False), "", text)
        text = re.sub(get_hyperlink_pattern(is_target=True), "", text)
    return re.findall(NUMERIC_PATTERN, text)


def replace_hyperlinks_with_values(text: str, is_targets: bool = False) -> str:
    """Replace all hypertarget/hyperlink commands with just their values."""

    def replace_match(match):
        return match.group("value")

    pattern = get_hyperlink_pattern(is_targets)
    return re.sub(pattern, replace_match, text)


def scan_file(tex_content: str) -> dict:
    """Scan a .tex file and report all hypertarget/hyperlink usage."""
    targets = find_references(tex_content, is_targets=True)
    links = find_references(tex_content, is_targets=False)
    unreferenced = find_numeric_values(tex_content)

    return {
        "hypertargets": [asdict(t) for t in targets],
        "hyperlinks": [asdict(l) for l in links],
        "target_count": len(targets),
        "link_count": len(links),
        "target_labels": sorted(set(t.label for t in targets if t.label)),
        "link_labels": sorted(set(l.label for l in links if l.label)),
        "unreferenced_numeric_values": unreferenced[:50],
        "unreferenced_count": len(unreferenced),
    }


def verify_integrity(tex_content: str, code_output: str | None = None) -> dict:
    """Return a status: PASS, FAIL, INCONCLUSIVE or INVALID_INPUT.

    WHY fail-closed (audit P0): absence of evidence must never be PASS. code_output=None
    means the code check was not requested; any string means every target label must be
    present in it, otherwise the result is INCONCLUSIVE.
    """
    targets = find_references(tex_content, is_targets=True)
    links = find_references(tex_content, is_targets=False)

    target_labels = {t.label for t in targets if t.label}
    link_labels = {link.label for link in links if link.label}

    # SKILL.md Step 1: tags live in the code output, links in the paper; those tags resolve links.
    code_values = _parse_code_targets(code_output) if code_output is not None else {}
    resolvable = target_labels | set(code_values)

    unresolved_links = link_labels - resolvable
    unused_targets = target_labels - link_labels

    target_values = {}
    for t in targets:
        if t.label:
            target_values[t.label] = t.value

    # WHY: compare EVERY link with its target; keeping only the last one hid a wrong first link
    value_mismatches = []
    for link in links:
        tv = target_values.get(link.label, "")
        if tv and link.value and tv != link.value:
            value_mismatches.append(
                {
                    "label": link.label,
                    "target_value": tv,
                    "link_value": link.value,
                }
            )

    code_mismatches = []
    code_missing_labels = []
    if code_output is not None:
        # WHY: each tex target must be backed by the executed output; a missing label is
        # INCONCLUSIVE, not PASS (audit P0: a label absent from code-output gave PASS)
        code_missing_labels = sorted(target_labels - set(code_values))
        for label, code_val in code_values.items():
            tex_val = target_values.get(label)
            if tex_val and tex_val != code_val:
                code_mismatches.append(
                    {
                        "label": label,
                        "code_value": code_val,
                        "tex_value": tex_val,
                    }
                )
        # WHY: a link resolved only through the code output must carry the same value
        for link in links:
            code_val = code_values.get(link.label)
            if code_val is not None and link.value and link.label not in target_values:
                if link.value != code_val:
                    code_mismatches.append(
                        {
                            "label": link.label,
                            "code_value": code_val,
                            "tex_value": link.value,
                        }
                    )

    # WHY: a label defined twice is ambiguous, whatever the values (audit P1)
    target_counts: dict[str, int] = {}
    for t in targets:
        if t.label:
            target_counts[t.label] = target_counts.get(t.label, 0) + 1
    duplicate_targets = sorted(label for label, n in target_counts.items() if n > 1)
    # WHY: an empty reference text carries nothing to check (audit P1)
    empty_links = sorted({link.label for link in links if link.label and not link.value.strip()})
    empty_targets = sorted({t.label for t in targets if t.label and not t.value.strip()})

    if duplicate_targets or empty_links or empty_targets:
        status = "INVALID_INPUT"
    elif unresolved_links or value_mismatches or code_mismatches:
        status = "FAIL"
    elif code_missing_labels:
        status = "INCONCLUSIVE"
    else:
        status = "PASS"

    result = {
        "status": status,
        "total_targets": len(targets),
        "total_links": len(links),
        "unresolved_links": sorted(unresolved_links),
        "unused_targets": sorted(unused_targets),
        "value_mismatches": value_mismatches,
        "code_mismatches": code_mismatches,
        "code_missing_labels": code_missing_labels,
        "duplicate_targets": duplicate_targets,
        "empty_links": empty_links,
        "empty_targets": empty_targets,
        "integrity_ok": status == "PASS",
    }
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Scan and verify hypertarget/hyperlink references in LaTeX"
    )
    parser.add_argument("tex_file", help="LaTeX file to analyze")
    parser.add_argument(
        "--scan", action="store_true", help="Scan mode: report all hypertarget/hyperlink usage"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify mode: check cross-reference integrity"
    )
    parser.add_argument("--code-output", help="Code output file for cross-referencing")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    if not args.scan and not args.verify:
        args.scan = True  # Default to scan mode

    if not os.path.exists(args.tex_file):
        print(f"Error: {args.tex_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(args.tex_file, encoding="utf-8", errors="replace") as f:
        tex_content = f.read()

    code_output = None
    if args.code_output:
        # WHY: a named but missing code-output file is an error, never a silent PASS
        if not os.path.exists(args.code_output):
            print(f"Error: --code-output {args.code_output} not found", file=sys.stderr)
            sys.exit(2)
        with open(args.code_output, encoding="utf-8", errors="replace") as f:
            code_output = f.read()

    if args.scan:
        result = scan_file(tex_content)
        print(
            f"Targets: {result['target_count']}, Links: {result['link_count']}, "
            f"Unreferenced numbers: {result['unreferenced_count']}",
            file=sys.stderr,
        )
    else:
        result = verify_integrity(tex_content, code_output)
        print(f"Integrity: {result['status']}", file=sys.stderr)
        if result["duplicate_targets"] or result["empty_links"] or result["empty_targets"]:
            print(
                f"  Invalid input: duplicates={result['duplicate_targets']} "
                f"empty_links={result['empty_links']} empty_targets={result['empty_targets']}",
                file=sys.stderr,
            )
        if result["code_missing_labels"]:
            print(f"  Missing from code output: {result['code_missing_labels']}", file=sys.stderr)
        if result["unresolved_links"]:
            print(f"  Unresolved links: {result['unresolved_links']}", file=sys.stderr)
        if result["value_mismatches"]:
            print(f"  Value mismatches: {len(result['value_mismatches'])}", file=sys.stderr)
        if result["code_mismatches"]:
            print(f"  Code mismatches: {len(result['code_mismatches'])}", file=sys.stderr)

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    if args.verify and not result["integrity_ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
