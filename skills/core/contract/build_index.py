"""Build index.json for the contract router from cards, SKILL.md files and agent files.

The index is a build artefact, like skills/registry.yaml's trigger index: whatever
reads it at run time should not tokenise, so all tokenising happens here, once. Rebuild with

    python skills/core/contract/contract.py build-index           # repo skills
    # the live install, including personal skills:
    python skills/core/contract/contract.py build-index --skills-dir ~/.claude/skills \\
        --agents-dir ~/.claude/agents

Stdlib only; PyYAML is used to join kind/maturity from skills/registry.yaml when importable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contracts_lib import _WORD_RE, INDEX_VERSION, tokenize

_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
MAX_STEMS_PER_SKILL = 80


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse the small YAML subset these files use. Returns (fields, body)."""
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    head, body = text[3:end].strip("\r\n"), text[end + 4 :].lstrip("\r\n")
    fields: dict[str, Any] = {}
    lines = head.splitlines()
    i = 0
    while i < len(lines):
        m = _KEY_RE.match(lines[i])
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        block: list[str] = []
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or lines[j][:1] in " \t-"):
            block.append(lines[j])
            j += 1
        if value in (">", "|", ">-", "|-") or (not value and block):
            if block and all(b.strip().startswith("- ") or not b.strip() for b in block):
                fields[key] = [_scalar(b.strip()[2:]) for b in block if b.strip()]
            else:
                fields[key] = " ".join(b.strip() for b in block if b.strip())
        else:
            fields[key] = _scalar(value)
        i = j
    return fields, body


def _scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        return [_scalar(p) for p in _split_list(inner) if p.strip()]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _split_list(inner: str) -> list[str]:
    parts, cur, quote = [], "", ""
    for ch in inner:
        if quote:
            cur += ch
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch == ",":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def iter_skill_files(root: Path) -> list[Path]:
    """root/<skill>/SKILL.md and root/<group>/<skill>/SKILL.md (repo nests, installs flatten)."""
    found = list(root.glob("*/SKILL.md")) + list(root.glob("*/*/SKILL.md"))
    return sorted(set(found))


def _registry_join(registry_path: Path | None) -> dict[str, dict[str, Any]]:
    if registry_path is None or not registry_path.is_file():
        return {}
    try:
        import yaml  # optional: CI has it, a user machine may not

        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 - any parse problem just means no join
        return {}
    joined: dict[str, dict[str, Any]] = {}
    for section in ("core", "extensions", "community"):
        for entry in data.get(section) or []:
            if isinstance(entry, dict) and entry.get("name"):
                cap = entry.get("capability") or {}
                joined[entry["name"]] = {
                    "kind": entry.get("kind"),
                    "maturity": entry.get("maturity"),
                    "risk_tier": cap.get("risk_tier") if isinstance(cap, dict) else None,
                }
    return joined


def load_cards(cards_dir: Path) -> list[dict[str, Any]]:
    cards = []
    for path in sorted(cards_dir.glob("*.md")):
        if path.name.startswith("_") or path.name.lower() == "readme.md":
            continue
        fields, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fields.get("id"):
            raise ValueError(f"{path}: card has no id")
        triggers = [str(t) for t in fields.get("triggers", [])]
        phrases = [str(p).lower() for p in fields.get("phrases", [])]
        for phrase in phrases:
            # A phrase bypasses the stem and request-verb gates, so it must be specific.
            if len(_WORD_RE.findall(phrase)) < 2:
                raise ValueError(f"{path.name}: phrase {phrase!r} must be at least two words")
        stems = sorted({s for t in triggers for s in tokenize(t)})
        cards.append(
            {
                "id": fields["id"],
                "catalog": fields.get("catalog"),
                "title": fields.get("title", fields["id"]),
                "family": fields.get("family", ""),
                "triggers": triggers,
                "phrases": phrases,
                "stems": stems,
                "risk_tier": fields.get("risk_tier", "Green"),
                "budget_turns": fields.get("budget_turns", 30),
                "skills": list(fields.get("skills", [])),
                "agents": list(fields.get("agents", [])),
                "verifier": fields.get("verifier", ""),
                "statuses": list(fields.get("statuses", [])),
                "baseline_first": bool(fields.get("baseline_first", False)),
                "gap": str(fields.get("gap", "")),
                "body": body.strip(),
                "file": path.name,
            }
        )
    return cards


def build_index(
    cards_dir: Path,
    skills_dirs: list[Path],
    agents_dir: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    joined = _registry_join(registry_path)
    skills: dict[str, dict[str, Any]] = {}
    for root in skills_dirs:
        for path in iter_skill_files(root):
            fields, _ = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            name = str(fields.get("name") or path.parent.name)
            text = " ".join(
                [name.replace("-", " "), str(fields.get("description", ""))]
                + [str(t) for t in fields.get("triggers", [])]
            )
            stems = sorted(set(tokenize(text)))[:MAX_STEMS_PER_SKILL]
            extra = joined.get(name, {})
            skills[name] = {
                "name": name,
                "desc": str(fields.get("description", ""))[:160],
                "stems": stems,
                "kind": extra.get("kind"),
                "maturity": extra.get("maturity"),
                "risk_tier": extra.get("risk_tier"),
            }
    agents: dict[str, dict[str, Any]] = {}
    if agents_dir is not None and agents_dir.is_dir():
        for path in sorted(agents_dir.glob("*.md")):
            fields, _ = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            name = str(fields.get("name") or path.stem)
            agents[name] = {
                "name": name,
                "stems": sorted(set(tokenize(str(fields.get("description", ""))))),
            }
    cards = load_cards(cards_dir)
    # Document frequencies, so that rare stems weigh more than common ones at route time.
    # A stem present in many cards ("проверь") says little about WHICH card is meant; a stem
    # present in many skills says little about which skill is meant. Computed once, here.
    card_df: dict[str, int] = {}
    for card in cards:
        for s in card["stems"]:
            card_df[s] = card_df.get(s, 0) + 1
    skill_df: dict[str, int] = {}
    for skill in skills.values():
        for s in skill["stems"]:
            skill_df[s] = skill_df.get(s, 0) + 1
    common_cut = max(8, int(0.10 * max(1, len(skills))))
    return {
        "version": INDEX_VERSION,
        "n_cards": len(cards),
        "card_df": {k: card_df[k] for k in sorted(card_df)},
        "common_stems": sorted(s for s, n in skill_df.items() if n >= common_cut),
        "cards": cards,
        "skills": [skills[k] for k in sorted(skills)],
        "agents": [agents[k] for k in sorted(agents)],
    }


def unresolved_routes(index: dict[str, Any]) -> list[str]:
    """Card routes that name a skill or agent absent from this index (for `doctor`)."""
    skills = {s["name"] for s in index.get("skills", [])}
    agents = {a["name"] for a in index.get("agents", [])}
    out = []
    for card in index.get("cards", []):
        out += [f"{card['id']}: skill {n}" for n in card["skills"] if n not in skills]
        out += [f"{card['id']}: agent {n}" for n in card["agents"] if n not in agents]
    return out


def dumps(index: dict[str, Any]) -> str:
    return json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
