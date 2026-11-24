#!/usr/bin/env python3
"""Read-only skill health report.

WHY (2026-11-24): the existing gates check the registry, not how Claude Code reads the files.
32 SKILL.md files carried a `<!-- BSV -->` comment before the YAML frontmatter and passed every
gate for months, although Claude Code reads the frontmatter only when `---` is the first line
of the file (docs: code.claude.com/docs/en/skills, read 2026-11-24). This script gathers, in
one place, the checks that sit between "the registry is consistent" and "the skill works":

  BLOCK  frontmatter_not_first   `---` must be the first line (the only check that fails CI)
  WARN   frontmatter_yaml_error  the frontmatter does not parse
  WARN   no_description          nothing for the skill listing to show
  WARN   name_mismatch           frontmatter `name` differs from the folder name
  WARN   listing_text_over_cap   description + when_to_use is cut at 1,536 characters in the
                                 listing (docs); the cap is configurable with --desc-cap
  WARN   body_too_long           more than --max-lines lines (advisory, not checked against docs)
  WARN   trigger_collision       the same trigger phrase in more than one registry entry
  WARN   registry_no_folder      registry entry without a SKILL.md folder
  WARN   folder_no_registry      SKILL.md folder without a registry entry
  INFO   totals, listing size against example budgets, registry `tokens` against file size

Only BLOCK findings change the exit code. Nothing is written. Usage:

    python scripts/skill_health.py                    # repo skills, human report
    python scripts/skill_health.py --json             # machine-readable
    python scripts/skill_health.py --live ~/.claude/skills   # also scan an installed copy
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DESC_CAP = 1536  # docs: description + when_to_use is cut here in the skill listing
DEFAULT_MAX_LINES = 500  # advisory
CHARS_PER_TOKEN = 4  # rough, an assumption used only for the INFO estimates
_FRONT_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


@dataclass
class Finding:
    severity: str  # BLOCK | WARN | INFO
    check: str
    skill: str
    detail: str


@dataclass
class SkillFile:
    folder: str
    path: Path
    text: str
    front: dict | None
    findings: list[Finding]


def read_skill(path: Path, desc_cap: int, max_lines: int) -> SkillFile:
    folder = path.parent.name
    text = path.read_bytes().decode("utf-8", errors="replace").lstrip("﻿")
    findings: list[Finding] = []
    front: dict | None = None
    if not text.startswith("---"):
        opener = text[:16].replace("\n", " ").replace("\r", " ")
        findings.append(
            Finding(
                "BLOCK",
                "frontmatter_not_first",
                folder,
                f"file starts with {opener!r}, not '---'; Claude Code ignores the frontmatter",
            )
        )
    else:
        m = _FRONT_RE.match(text)
        if not m:
            findings.append(
                Finding("WARN", "frontmatter_yaml_error", folder, "no closing '---' found")
            )
        else:
            try:
                loaded = yaml.safe_load(m.group(1))
            except yaml.YAMLError as exc:
                findings.append(
                    Finding("WARN", "frontmatter_yaml_error", folder, str(exc).split("\n")[0])
                )
                loaded = None
            if isinstance(loaded, dict):
                front = loaded
            elif loaded is not None:
                findings.append(
                    Finding("WARN", "frontmatter_yaml_error", folder, "frontmatter is not a map")
                )
    if front is not None:
        if not str(front.get("description") or "").strip():
            findings.append(Finding("WARN", "no_description", folder, "description is empty"))
        name = front.get("name")
        if name is not None and str(name) != folder:
            findings.append(
                Finding("WARN", "name_mismatch", folder, f"name {str(name)!r} != folder {folder!r}")
            )
        size = len(listing_text(front))
        if size > desc_cap:
            findings.append(
                Finding(
                    "WARN",
                    "listing_text_over_cap",
                    folder,
                    f"description + when_to_use is {size} chars, cut at {desc_cap} in the listing",
                )
            )
    lines = text.count("\n") + 1
    if lines > max_lines:
        findings.append(
            Finding("WARN", "body_too_long", folder, f"{lines} lines, advisory limit {max_lines}")
        )
    return SkillFile(folder, path, text, front, findings)


def listing_text(front: dict) -> str:
    return f"{front.get('description') or ''} {front.get('when_to_use') or ''}".strip()


def iter_skill_files(skills_dir: Path) -> list[Path]:
    """core/*/SKILL.md and extensions/*/SKILL.md, or a flat <name>/SKILL.md layout."""
    found = sorted(skills_dir.glob("*/*/SKILL.md")) + sorted(skills_dir.glob("*/SKILL.md"))
    return sorted(set(found))


def load_registry(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries: list[dict] = []
    for section in ("core", "extensions"):
        entries.extend(s for s in (data.get(section) or []) if isinstance(s, dict))
    return entries


def trigger_collisions(entries: list[dict]) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        for trig in entry.get("triggers") or []:
            key = str(trig).lower().strip()
            if key and entry["name"] not in seen[key]:
                seen[key].append(entry["name"])
    return {k: v for k, v in seen.items() if len(v) > 1}


def token_ratios(entries: list[dict], files: dict[str, SkillFile]) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for entry in entries:
        sf = files.get(entry["name"])
        raw = re.sub(r"[^\d]", "", str(entry.get("tokens", "")))
        if sf and raw:
            out.append((entry["name"], int(raw), len(sf.text) // CHARS_PER_TOKEN))
    return out


def analyse(
    skills_dir: Path,
    registry_path: Path,
    desc_cap: int = DEFAULT_DESC_CAP,
    max_lines: int = DEFAULT_MAX_LINES,
) -> dict:
    files = {
        sf.folder: sf
        for sf in (read_skill(p, desc_cap, max_lines) for p in iter_skill_files(skills_dir))
    }
    entries = load_registry(registry_path)
    findings = [f for sf in files.values() for f in sf.findings]
    names = {e["name"] for e in entries}
    for name in sorted(names - set(files)):
        findings.append(Finding("WARN", "registry_no_folder", name, "no SKILL.md folder"))
    for name in sorted(set(files) - names) if entries else []:
        findings.append(Finding("WARN", "folder_no_registry", name, "not in the registry"))
    collisions = trigger_collisions(entries)
    for trig, owners in sorted(collisions.items()):
        findings.append(Finding("WARN", "trigger_collision", ", ".join(owners), repr(trig)))
    listing = [min(len(listing_text(sf.front)), desc_cap) for sf in files.values() if sf.front]
    ratios = token_ratios(entries, files)
    dogfooded = sum(1 for e in entries if e.get("maturity") == "dogfooded")
    ratio_values = [actual / declared for _, declared, actual in ratios if declared]
    totals = {
        "skill_folders": len(files),
        "registry_entries": len(entries),
        "dogfooded": dogfooded,
        "listing_chars_total": sum(listing),
        "listing_tokens_estimate": sum(listing) // CHARS_PER_TOKEN,
        "median_actual_over_declared_tokens": (
            round(statistics.median(ratio_values), 2) if ratio_values else None
        ),
    }
    return {"totals": totals, "findings": findings}


def render(result: dict) -> str:
    t = result["totals"]
    lines = [
        "Skill health report (read-only)",
        f"  skill folders with SKILL.md : {t['skill_folders']}",
        f"  registry entries            : {t['registry_entries']}",
        f"  dogfooded entries           : {t['dogfooded']}",
        f"  listing text, capped        : {t['listing_chars_total']} chars "
        f"(about {t['listing_tokens_estimate']} tokens at {CHARS_PER_TOKEN} chars/token, an "
        f"assumption); the docs say the listing budget is 1% of the context window",
        f"  median actual/declared size : {t['median_actual_over_declared_tokens']} "
        f"(file size / {CHARS_PER_TOKEN} against the registry `tokens` field)",
        "",
    ]
    by_check: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in result["findings"]:
        by_check[(f.severity, f.check)].append(f)
    if not by_check:
        lines.append("No findings.")
    for (sev, check), items in sorted(
        by_check.items(), key=lambda kv: (kv[0][0] != "BLOCK", kv[0])
    ):
        lines.append(f"{sev} {check}: {len(items)}")
        lines.extend(f"    {f.skill}: {f.detail}" for f in items[:40])
        if len(items) > 40:
            lines.append(f"    ... and {len(items) - 40} more")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--skills-dir", type=Path, default=ROOT / "skills")
    ap.add_argument("--registry", type=Path, default=ROOT / "skills" / "registry.yaml")
    ap.add_argument("--live", type=Path, help="also scan an installed skills directory")
    ap.add_argument("--desc-cap", type=int, default=DEFAULT_DESC_CAP)
    ap.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    result = analyse(args.skills_dir, args.registry, args.desc_cap, args.max_lines)
    live = None
    if args.live:
        live = analyse(args.live, args.live / "registry.yaml", args.desc_cap, args.max_lines)
        repo_names = {f.skill for f in result["findings"] if f.check == "frontmatter_not_first"}
        live_names = {f.skill for f in live["findings"] if f.check == "frontmatter_not_first"}
        live["only_in_repo_broken"] = sorted(repo_names - live_names)
    blocking = any(f.severity == "BLOCK" for f in result["findings"])
    if args.json:
        payload = {"repo": result, "live": live, "blocking": blocking}
        print(json.dumps(payload, default=lambda o: asdict(o), ensure_ascii=False, indent=2))
    else:
        print(render(result))
        if live:
            print("\n--- installed copy:", args.live)
            print(render(live))
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
