#!/usr/bin/env python3
"""Project state snapshot: one Markdown + one JSON file describing the repo and the live install.

Read-only. Two sources are described side by side and then compared:
  * the repository (skills/agents/rules/hooks/commands/scripts/tests, registries)
  * the live install (~/.claude: the same artifacts as actually deployed, settings wiring)

Usage:
    python scripts/snapshot_state.py --out DIR [--live ~/.claude] [--tests-passed N]
    python scripts/snapshot_state.py --compare OLD.json NEW.json

Privacy: only names, counts and short hashes are recorded. Never values from settings.json,
~/.claude.json or memory files (env values, tokens, permission strings, note names). Home paths
are written as "~". A final scan of the output refuses to write a file that matches a secret shape.
"""

# ruff: noqa: E501  (report prose lines are kept readable instead of wrapped)
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]  # types-PyYAML intentionally not a dep

SCHEMA_VERSION = 1
LISTING_CAP = 1536  # chars of description per skill in the Claude Code listing

SECRET_SHAPES = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9/+_-]{16,}"),
]


# --------------------------------------------------------------------------- helpers


def sha(path: Path) -> str:
    """Short content hash; line endings normalised so CRLF checkouts match LF ones."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:12]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")


def frontmatter(path: Path) -> dict:
    text = read_text(path).replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    try:
        data = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def first_heading(path: Path) -> str:
    for line in read_text(path).splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()[:120]
    return ""


def hook_scripts(command: object) -> list[str]:
    """Python script names in a hook command; async_wrapper.py is a launcher, not the hook."""
    names = re.findall(r"([\w.-]+\.py)\b", str(command))
    real = [n for n in names if n != "async_wrapper.py"]
    return real or names


def north_star(root: Path) -> str:
    """Section 1 of PRODUCT_CONSTITUTION.md, quoted, so the goal is never paraphrased from memory."""
    try:
        text = read_text(root / "PRODUCT_CONSTITUTION.md").replace("\r\n", "\n")
    except OSError:
        return ""
    m = re.search(r"^## 1\. [^\n]*\n(.*?)(?=^## )", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def repo_name(root: Path) -> str:
    url = run(["git", "remote", "get-url", "origin"], root)
    m = re.search(r"([\w.-]+?)(?:\.git)?$", url)
    return m.group(1) if m else root.name


def skill_files(base: Path) -> list[Path]:
    """Every SKILL.md under base, following directory symlinks.

    WHY not rglob (Codex review of PR 557): `install.sh --link` links each skill directory, and
    Path.rglob does not descend into directory symlinks, so linked skills were not counted.
    A visited-set on real paths guards against symlink loops.
    """
    found: list[Path] = []
    seen: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(base, followlinks=True):
        real = os.path.realpath(dirpath)
        if real in seen:
            dirnames[:] = []
            continue
        seen.add(real)
        if "SKILL.md" in filenames:
            found.append(Path(dirpath) / "SKILL.md")
    return sorted(found)


def run(cmd: list[str], cwd: Path) -> str:
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip()


def short(text: object, n: int = 110) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(read_text(path))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- repo side


def skill_entries(registry: dict) -> list[dict]:
    out: list[dict] = []
    for section, items in registry.items():
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict) and it.get("name"):
                    out.append({**it, "_section": section})
    return out


def collect_skills(root: Path) -> dict:
    entries = skill_entries(load_yaml(root / "skills" / "registry.yaml"))
    folders: dict[str, Path] = {}
    for md in skill_files(root / "skills"):
        folders[md.parent.name] = md
    skills = []
    for e in entries:
        cap: dict = e["capability"] if isinstance(e.get("capability"), dict) else {}
        found = folders.get(e["name"])
        desc = str(e.get("description") or "")
        skills.append(
            {
                "name": e["name"],
                "section": e["_section"],
                "kind": e.get("kind", ""),
                "maturity": e.get("maturity", ""),
                "pack": e.get("pack", ""),
                "risk_tier": cap.get("risk_tier", ""),
                "has_capability": bool(cap),
                "triggers": len(e.get("triggers") or []),
                "tokens": str(e.get("tokens", "")),
                "description_chars": len(desc),
                "description": short(desc),
                "hash": sha(found) if found else "",
                "has_folder": found is not None,
            }
        )
    names = {s["name"] for s in skills}
    return {
        "items": sorted(skills, key=lambda s: s["name"]),
        "folders_without_registry": sorted(set(folders) - names),
        "registry_without_folder": sorted(s["name"] for s in skills if not s["has_folder"]),
    }


def collect_agents(directory: Path) -> list[dict]:
    out = []
    for md in sorted(directory.glob("*.md")):
        fm = frontmatter(md)
        out.append(
            {
                "file": md.name,
                "name": str(fm.get("name") or md.stem),
                "model": str(fm.get("model") or ""),
                "tools": short(fm.get("tools"), 80),
                "description": short(fm.get("description")),
                "hash": sha(md),
            }
        )
    return out


def collect_rules(directory: Path) -> list[dict]:
    out = []
    for md in sorted(directory.rglob("*.md")):
        rel = md.relative_to(directory).as_posix()
        out.append(
            {
                "file": rel,
                "title": first_heading(md),
                "bytes": md.stat().st_size,
                "hash": sha(md),
            }
        )
    return out


def collect_hooks(root: Path) -> dict:
    registry = load_yaml(root / "hooks" / "registry.yaml").get("hooks") or {}
    settings_path = root / "hooks" / "settings.json"
    wired: set[str] = set()
    try:
        settings = json.loads(read_text(settings_path))
    except (OSError, ValueError):
        settings = {}
    for groups in (settings.get("hooks") or {}).values():
        for group in groups:
            for h in group.get("hooks", []):
                wired.update(hook_scripts(h.get("command", "")))
    items = []
    for name, meta in sorted(registry.items()):
        meta = meta if isinstance(meta, dict) else {}
        file = f"{name}.py"
        path = root / "hooks" / file
        items.append(
            {
                "name": name,
                "class": meta.get("class", ""),
                "event": meta.get("event", ""),
                "fail_mode": meta.get("fail_mode", ""),
                "escalation": meta.get("escalation", ""),
                "wired": file in wired,
                "hash": sha(path) if path.exists() else "",
            }
        )
    on_disk = {p.name for p in (root / "hooks").glob("*.py")}
    return {
        "items": items,
        "py_files_not_in_registry": sorted(
            on_disk - {f"{i['name']}.py" for i in items} - {"utils.py", "__init__.py"}
        ),
    }


def count_tests(root: Path) -> dict:
    files = sorted((root / "tests").rglob("test_*.py"))
    funcs = 0
    for f in files:
        funcs += len(re.findall(r"^\s*(?:async\s+)?def test_", read_text(f), re.M))
    return {"test_files": len(files), "test_functions": funcs}


def collect_repo(root: Path) -> dict:
    skills = collect_skills(root)
    return {
        "git": {
            "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root),
            "head": run(["git", "rev-parse", "--short=12", "HEAD"], root),
            "head_date": run(["git", "log", "-1", "--format=%cs"], root),
            "uncommitted_files": len(
                [ln for ln in run(["git", "status", "--porcelain"], root).splitlines() if ln]
            ),
        },
        "skills": skills,
        "agents": collect_agents(root / "agents"),
        "rules": collect_rules(root / "rules"),
        "hooks": collect_hooks(root),
        "commands": sorted(p.name for p in (root / "commands").glob("*.md")),
        "scripts": sorted(p.name for p in (root / "scripts").glob("*.*")),
        "workflows": sorted(p.name for p in (root / ".github" / "workflows").glob("*.yml")),
        "tests": count_tests(root),
    }


# --------------------------------------------------------------------------- live side


def mcp_server_names(home: Path) -> list[str]:
    """Names only. ~/.claude.json holds secrets, so no other key is ever read out."""
    for cand in (home.parent / ".claude.json", home / ".claude.json"):
        try:
            data = json.loads(read_text(cand))
        except (OSError, ValueError):
            continue
        names = set(data.get("mcpServers") or {})
        for proj in (data.get("projects") or {}).values():
            names |= set((proj or {}).get("mcpServers") or {})
        return sorted(names)
    return []


def collect_live(home: Path) -> dict:
    if not home.is_dir():
        return {"present": False}
    try:
        settings = json.loads(read_text(home / "settings.json"))
    except (OSError, ValueError):
        settings = {}
    events: dict[str, list[str]] = {}
    for ev, groups in (settings.get("hooks") or {}).items():
        names = []
        for group in groups:
            for h in group.get("hooks", []):
                names.extend(hook_scripts(h.get("command", "")) or ["(non-python command)"])
        events[ev] = sorted(names)
    perms = settings.get("permissions") or {}
    skill_md: dict[str, Path] = {}
    dup: Counter[str] = Counter()
    for md in skill_files(home / "skills"):
        dup[md.parent.name] += 1
        skill_md.setdefault(md.parent.name, md)
    disabled = []
    dh = home / "disabled_hooks.txt"
    if dh.exists():
        disabled = sorted(
            ln.strip() for ln in read_text(dh).splitlines() if ln.strip() and ln[0] != "#"
        )
    backups = [
        p.name
        for p in home.iterdir()
        if re.search(r"\.(bak|backup)|^_deploy_backup|^skills-backup|^hooks_disabled", p.name)
    ]
    memory_dir = home / "memory"
    return {
        "present": True,
        "settings": {
            "model": settings.get("model"),
            "advisorModel": settings.get("advisorModel"),
            "top_level_keys": sorted(settings),
            "env_keys": sorted(settings.get("env") or {}),
            "permissions_allow_count": len(perms.get("allow") or []),
            "permissions_deny_count": len(perms.get("deny") or []),
            "enabled_plugins": sorted(settings.get("enabledPlugins") or {}),
            "hook_events": {k: v for k, v in sorted(events.items())},
        },
        "mcp_servers": mcp_server_names(home),
        "claude_md": {
            "bytes": (home / "CLAUDE.md").stat().st_size if (home / "CLAUDE.md").exists() else 0,
            "hash": sha(home / "CLAUDE.md") if (home / "CLAUDE.md").exists() else "",
        },
        "agents": collect_agents(home / "agents"),
        "agents_disabled": len(list((home / "agents-disabled").glob("*.md")))
        if (home / "agents-disabled").is_dir()
        else 0,
        "rules": collect_rules(home / "rules"),
        "hooks_files": sorted(p.name for p in (home / "hooks").glob("*.py")),
        "hooks_disabled_list": disabled,
        "commands": sorted(p.name for p in (home / "commands").glob("*.md")),
        "skills": {
            "folders_with_skill_md": len(skill_md),
            "duplicate_names": sorted(n for n, c in dup.items() if c > 1),
            "hashes": {n: sha(p) for n, p in sorted(skill_md.items())},
        },
        "skills_disabled": len({p.parent.name for p in skill_files(home / "skills-disabled")})
        if (home / "skills-disabled").is_dir()
        else 0,
        "backup_clutter_entries": len(backups),
        "memory": {
            "files": sum(1 for p in memory_dir.rglob("*") if p.is_file())
            if memory_dir.is_dir()
            else 0
        },
    }


# --------------------------------------------------------------------------- drift + metrics


def drift(repo: dict, live: dict, root: Path) -> dict:
    if not live.get("present"):
        return {}

    def cmp(repo_map: dict[str, str], live_map: dict[str, str]) -> dict:
        both = repo_map.keys() & live_map.keys()
        return {
            "same": sum(1 for k in both if repo_map[k] == live_map[k]),
            "differ": sorted(k for k in both if repo_map[k] != live_map[k]),
            "only_repo": sorted(repo_map.keys() - live_map.keys()),
            "only_live": sorted(live_map.keys() - repo_map.keys()),
        }

    repo_skill_hash = {s["name"]: s["hash"] for s in repo["skills"]["items"] if s["hash"]}
    hook_repo = {i["name"] + ".py": i["hash"] for i in repo["hooks"]["items"] if i["hash"]}
    hook_live = {n: sha(Path(live["_home"]) / "hooks" / n) for n in live["hooks_files"]}
    return {
        "skills": cmp(repo_skill_hash, live["skills"]["hashes"]),
        "agents": cmp(
            {a["file"]: a["hash"] for a in repo["agents"]},
            {a["file"]: a["hash"] for a in live["agents"]},
        ),
        "rules": cmp(
            {r["file"]: r["hash"] for r in repo["rules"]},
            {r["file"]: r["hash"] for r in live["rules"]},
        ),
        "hooks": cmp(hook_repo, hook_live),
    }


def metrics(repo: dict, live: dict, dr: dict, tests_passed: int | None) -> dict:
    items = repo["skills"]["items"]
    m: dict = {
        "repo.skills": len(items),
        "repo.skills_with_capability": sum(1 for s in items if s["has_capability"]),
        "repo.skills_description_over_cap": sum(
            1 for s in items if s["description_chars"] > LISTING_CAP
        ),
        "repo.skills_description_chars_total": sum(s["description_chars"] for s in items),
        "repo.skill_folders_without_registry": len(repo["skills"]["folders_without_registry"]),
        "repo.registry_without_folder": len(repo["skills"]["registry_without_folder"]),
        "repo.agents": len(repo["agents"]),
        "repo.rules": len(repo["rules"]),
        "repo.hooks_registered": len(repo["hooks"]["items"]),
        "repo.hooks_wired": sum(1 for h in repo["hooks"]["items"] if h["wired"]),
        "repo.hooks_py_not_in_registry": len(repo["hooks"]["py_files_not_in_registry"]),
        "repo.test_files": repo["tests"]["test_files"],
        "repo.test_functions": repo["tests"]["test_functions"],
        "repo.uncommitted_files": repo["git"]["uncommitted_files"],
    }
    for level, n in Counter(s["maturity"] or "(none)" for s in items).items():
        m[f"repo.maturity.{level}"] = n
    for tier, n in Counter(s["risk_tier"] or "(none)" for s in items).items():
        m[f"repo.risk_tier.{tier}"] = n
    if tests_passed is not None:
        m["tests.passed_last_full_run"] = tests_passed
    if live.get("present"):
        m["live.skill_folders"] = live["skills"]["folders_with_skill_md"]
        m["live.skill_duplicate_names"] = len(live["skills"]["duplicate_names"])
        m["live.agents"] = len(live["agents"])
        m["live.agents_disabled"] = live["agents_disabled"]
        m["live.rules"] = len(live["rules"])
        m["live.hook_files"] = len(live["hooks_files"])
        m["live.hooks_disabled_declared"] = len(live["hooks_disabled_list"])
        m["live.hook_events"] = len(live["settings"]["hook_events"])
        m["live.hook_registrations"] = sum(len(v) for v in live["settings"]["hook_events"].values())
        m["live.mcp_servers"] = len(live["mcp_servers"])
        m["live.backup_clutter_entries"] = live["backup_clutter_entries"]
        m["live.memory_files"] = live["memory"]["files"]
        m["live.claude_md_bytes"] = live["claude_md"]["bytes"]
        for part, d in dr.items():
            m[f"drift.{part}.differ"] = len(d["differ"])
            m[f"drift.{part}.only_repo"] = len(d["only_repo"])
            m[f"drift.{part}.only_live"] = len(d["only_live"])
    return m


# --------------------------------------------------------------------------- rendering


def table(headers: list[str], rows: list[list[object]]) -> str:
    def cell(v: object) -> str:
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def render_md(snap: dict) -> str:
    repo, live, dr, m = snap["repo"], snap["live"], snap["drift"], snap["metrics"]
    L: list[str] = []
    a = L.append
    a(f"# Project snapshot — {snap['date']}")
    a("")
    a(
        f"Repository `{snap['repo_name']}` at `{repo['git']['head']}` ({repo['git']['head_date']}, "
        f"branch `{repo['git']['branch']}`, {repo['git']['uncommitted_files']} uncommitted files), "
        f"plus the live install `~/.claude`. Generated by `scripts/snapshot_state.py` "
        f"(schema {SCHEMA_VERSION}); the JSON file next to this one holds the same data for diffing."
    )
    a("")
    if snap.get("north_star"):
        a("## What this project is (from `PRODUCT_CONSTITUTION.md`, section 1)")
        a("")
        a(snap["north_star"])
        a("")
    a("## Index")
    a("")
    for i, t in enumerate(
        [
            "Metrics (the numbers to compare between snapshots)",
            "Skills",
            "Agents",
            "Rules",
            "Hooks",
            "Commands, scripts, CI",
            "Live install",
            "Drift: repository vs live install",
            "How to use this snapshot",
        ],
        1,
    ):
        a(f"{i}. [{t}](#{i}-{re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')})")
    a("")
    a("## 1. Metrics")
    a("")
    a(table(["Metric", "Value"], [[k, v] for k, v in sorted(m.items())]))
    a("")
    items = repo["skills"]["items"]
    a("## 2. Skills")
    a("")
    a(
        f"{len(items)} registry entries. Folders without a registry entry: "
        f"{', '.join(repo['skills']['folders_without_registry']) or 'none'}. "
        f"Registry entries without a folder: "
        f"{', '.join(repo['skills']['registry_without_folder']) or 'none'}."
    )
    a("")
    a(
        "Maturity: "
        + ", ".join(
            f"{k} {v}" for k, v in sorted(Counter(s["maturity"] or "(none)" for s in items).items())
        )
        + "."
    )
    a("")
    a(
        table(
            ["Skill", "Kind", "Maturity", "Pack", "Tier", "Triggers", "Description"],
            [
                [
                    s["name"],
                    s["kind"],
                    s["maturity"],
                    s["pack"],
                    s["risk_tier"] or "–",
                    s["triggers"],
                    s["description"],
                ]
                for s in items
            ],
        )
    )
    a("")
    a("## 3. Agents")
    a("")
    a(
        table(
            ["Agent", "Model", "Tools", "Description"],
            [[x["name"], x["model"] or "–", x["tools"], x["description"]] for x in repo["agents"]],
        )
    )
    a("")
    a("## 4. Rules")
    a("")
    a(
        table(
            ["File", "Title", "Bytes"], [[r["file"], r["title"], r["bytes"]] for r in repo["rules"]]
        )
    )
    a("")
    a("## 5. Hooks")
    a("")
    hooks = repo["hooks"]
    a(
        f"{len(hooks['items'])} registered, {m['repo.hooks_wired']} wired in `hooks/settings.json` "
        "(the `async_wrapper` launcher and `statusline` are not counted here; "
        "`docs/hook-control-matrix.md` counts them, hence its 89). "
        f"Python files not in the registry: {', '.join(hooks['py_files_not_in_registry']) or 'none'}."
    )
    a("")
    a(
        table(
            ["Hook", "Class", "Event", "Fail mode", "Escalation", "Wired"],
            [
                [
                    h["name"],
                    h["class"],
                    h["event"],
                    h["fail_mode"],
                    h["escalation"],
                    "yes" if h["wired"] else "no",
                ]
                for h in hooks["items"]
            ],
        )
    )
    a("")
    a("## 6. Commands, scripts, CI")
    a("")
    a(f"- Commands ({len(repo['commands'])}): {', '.join(repo['commands'])}")
    a(f"- CI workflows: {', '.join(repo['workflows'])}")
    a(
        f"- Tests: {repo['tests']['test_files']} files, {repo['tests']['test_functions']} test functions"
        + (
            f"; last full run: {m['tests.passed_last_full_run']} passed"
            if "tests.passed_last_full_run" in m
            else ""
        )
    )
    a(f"- Scripts ({len(repo['scripts'])}): {', '.join(repo['scripts'])}")
    a("")
    a("## 7. Live install")
    a("")
    if not live.get("present"):
        a("Not found on this machine.")
    else:
        s = live["settings"]
        a(f"- Model `{s['model']}`, advisor `{s['advisorModel']}`.")
        a(
            f"- Global `CLAUDE.md`: {live['claude_md']['bytes']} bytes, hash `{live['claude_md']['hash']}`."
        )
        a(
            f"- Permissions: {s['permissions_allow_count']} allow, {s['permissions_deny_count']} deny (counts only)."
        )
        a(
            f"- Settings keys: {', '.join(s['top_level_keys'])}. Env keys (names only): {', '.join(s['env_keys']) or 'none'}."
        )
        a(f"- Enabled plugins: {', '.join(s['enabled_plugins']) or 'none'}.")
        a(f"- MCP servers (names only): {', '.join(live['mcp_servers']) or 'none found'}.")
        a(
            f"- Agents {len(live['agents'])} (+{live['agents_disabled']} disabled), rules {len(live['rules'])}, "
            f"hook files {len(live['hooks_files'])}, commands {len(live['commands'])}, "
            f"skill folders {live['skills']['folders_with_skill_md']} (+{live['skills_disabled']} disabled), "
            f"memory files {live['memory']['files']}."
        )
        a(
            f"- Hooks declared disabled in `disabled_hooks.txt` ({len(live['hooks_disabled_list'])}): "
            f"{', '.join(live['hooks_disabled_list']) or 'none'}."
        )
        a(f"- Backup and leftover entries in `~/.claude`: {live['backup_clutter_entries']}.")
        a("")
        a("Hook wiring in `settings.json` (script names per event):")
        a("")
        a(
            table(
                ["Event", "Registered"],
                [[ev, ", ".join(names)] for ev, names in s["hook_events"].items()],
            )
        )
        if live["skills"]["duplicate_names"]:
            a("")
            a(
                "Skill names that exist more than once under `~/.claude/skills`: "
                + ", ".join(live["skills"]["duplicate_names"])
            )
    a("")
    a("## 8. Drift: repository vs live install")
    a("")
    if dr:
        a(
            table(
                ["Part", "Same", "Differ", "Only in repo", "Only live"],
                [
                    [p, d["same"], len(d["differ"]), len(d["only_repo"]), len(d["only_live"])]
                    for p, d in dr.items()
                ],
            )
        )
        for p, d in dr.items():
            for key, label in (
                ("differ", "differ"),
                ("only_repo", "only in repo"),
                ("only_live", "only live"),
            ):
                if d[key]:
                    a("")
                    a(
                        f"**{p}, {label} ({len(d[key])}):** {', '.join(d[key][:80])}"
                        + (" …" if len(d[key]) > 80 else "")
                    )
    else:
        a("No live install to compare.")
    a("")
    a("## 9. How to use this snapshot")
    a("")
    a(
        "- To see change since a past snapshot: "
        "`python scripts/snapshot_state.py --compare OLD.json NEW.json`. It lists added, removed and "
        "changed components and the metric deltas."
    )
    a(
        "- A component's `hash` is the first 12 hex characters of the SHA-256 of its file with line endings normalised."
    )
    a(
        "- Counts are not quality. Maturity, tier and drift numbers say more than the number of skills."
    )
    a("- No secret values are recorded: only names, counts and hashes.")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- compare


def compare(old: dict, new: dict) -> str:
    L = [f"# Snapshot comparison: {old['date']} -> {new['date']}", ""]

    def named(snap: dict, key: str) -> dict[str, str]:
        r = snap["repo"]
        if key == "skills":
            return {s["name"]: s["hash"] for s in r["skills"]["items"]}
        if key == "agents":
            return {a["file"]: a["hash"] for a in r["agents"]}
        if key == "rules":
            return {x["file"]: x["hash"] for x in r["rules"]}
        return {h["name"]: h["hash"] for h in r["hooks"]["items"]}

    rows: list[list[object]] = []
    for key in ("skills", "agents", "rules", "hooks"):
        o, n = named(old, key), named(new, key)
        rows.append(
            [
                key,
                ", ".join(sorted(n.keys() - o.keys())) or "–",
                ", ".join(sorted(o.keys() - n.keys())) or "–",
                ", ".join(sorted(k for k in o.keys() & n.keys() if o[k] != n[k])) or "–",
            ]
        )
    L.append(table(["Part", "Added", "Removed", "Content changed"], rows))
    L.append("")
    om, nm = old["metrics"], new["metrics"]
    mrows = []
    for k in sorted(om.keys() | nm.keys()):
        a, b = om.get(k), nm.get(k)
        if a != b:
            delta = b - a if isinstance(a, (int, float)) and isinstance(b, (int, float)) else ""
            mrows.append(
                [
                    k,
                    "–" if a is None else a,
                    "–" if b is None else b,
                    f"{delta:+}" if delta != "" else "",
                ]
            )
    L.append("## Metric changes")
    L.append("")
    L.append(
        table(["Metric", "Before", "After", "Delta"], mrows) if mrows else "No metric changed."
    )
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- main


def secret_hits(text: str) -> list[str]:
    return [p.pattern[:30] for p in SECRET_SHAPES if p.search(text)]


def anonymise(text: str, home: Path) -> str:
    """Replace the live directory and its parent by "~".

    WHY resolve first (Codex review of PR 557): with a relative `--live .claude` the parent is
    `.`, and replacing "." would rewrite every dot in names such as `repo.skills`.
    """
    home = home.resolve()
    variants = set()
    for base in (home, home.parent):
        variants.add(str(base))
        variants.add(str(base).replace("\\", "/"))
    # Only absolute, non-trivial prefixes: never "." or a drive root.
    for variant in sorted(
        (v for v in variants if len(v) > 3 and v not in {".", ".."}), key=len, reverse=True
    ):
        text = text.replace(variant, "~")
    return text


def build(root: Path, home: Path, tests_passed: int | None) -> dict:
    repo = collect_repo(root)
    live = collect_live(home)
    if live.get("present"):
        live["_home"] = str(home)
    dr = drift(repo, live, root)
    live.pop("_home", None)
    return {
        "schema": SCHEMA_VERSION,
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo_name": repo_name(root),
        "north_star": north_star(root),
        "repo": repo,
        "live": live,
        "drift": dr,
        "metrics": metrics(repo, live, dr, tests_passed),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--live", default=str(Path.home() / ".claude"))
    ap.add_argument("--out", help="directory for snapshot-YYYY-MM-DD.md and .json")
    ap.add_argument("--tests-passed", type=int, help="record the result of the last full test run")
    ap.add_argument("--compare", nargs=2, metavar=("OLD", "NEW"))
    args = ap.parse_args(argv)

    if args.compare:
        old = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        new = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        sys.stdout.write(compare(old, new))
        return 0
    if not args.out:
        ap.error("--out is required unless --compare is used")

    home = Path(args.live).expanduser()
    snap = build(Path(args.repo).resolve(), home, args.tests_passed)
    md = anonymise(render_md(snap), home)
    js = anonymise(json.dumps(snap, indent=2, ensure_ascii=False, sort_keys=True), home)
    hits = secret_hits(md) + secret_hits(js)
    if hits:
        print(f"refusing to write: secret-shaped text in output ({hits})", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"snapshot-{snap['date']}.md").write_text(md, encoding="utf-8", newline="\n")
    (out / f"snapshot-{snap['date']}.json").write_text(js + "\n", encoding="utf-8", newline="\n")
    print(
        f"written: {out / ('snapshot-' + snap['date'] + '.md')} and .json "
        f"({len(snap['metrics'])} metrics)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
