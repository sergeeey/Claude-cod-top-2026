#!/usr/bin/env python3
"""Keep the private settings overlay across an install that replaces settings.json.

WHY: `install.sh --force-replace` writes the shipped settings.json over the user's file (with a
backup). The ownership model (docs/GLOBAL_VS_PROJECT_OVERLAY.md) keeps the private overlay --
personal hooks, env and permissions -- in that same user file, so an upgrade silently drops it.
Found in the RC 1.0 install rehearsal (2026-11-27). This tool extracts the overlay before the
install and puts it back after.

    python scripts/settings_overlay.py extract --live L.json --template T.json --out O.json
    python scripts/settings_overlay.py extract --live L.json --template T.json --dry-run
    python scripts/settings_overlay.py apply   --installed I.json --overlay O.json
    python scripts/settings_overlay.py verify  --installed I.json --overlay O.json

Hooks are matched by (event, matcher, script file name), not by full command, because the home
path differs between machines and installs. Output names keys and counts only, never values: the
overlay can hold secrets, so keep O.json outside any repository.
Exit codes: 0 ok, 1 verify found missing items, 2 usage or missing file.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

PERMISSION_LISTS = ("allow", "deny", "ask")


def _scripts(group: dict) -> tuple[str, ...]:
    names = []
    for h in group.get("hooks", []):
        for m in re.findall(r"([A-Za-z0-9_.-]+\.(?:py|sh|ps1))", h.get("command", "")):
            names.append(m)
    return tuple(sorted(names))


def _hook_keys(settings: dict) -> set[tuple[str, str, tuple[str, ...]]]:
    keys = set()
    for event, groups in settings.get("hooks", {}).items():
        for g in groups:
            keys.add((event, g.get("matcher", ""), _scripts(g)))
    return keys


def extract(live: dict, template: dict) -> dict:
    overlay: dict = {"hooks": {}, "env": {}, "permissions": {}, "other": {}}
    tkeys = _hook_keys(template)
    for event, groups in live.get("hooks", {}).items():
        for g in groups:
            if (event, g.get("matcher", ""), _scripts(g)) not in tkeys:
                overlay["hooks"].setdefault(event, []).append(g)
    tenv = template.get("env", {})
    overlay["env"] = {k: v for k, v in live.get("env", {}).items() if tenv.get(k) != v}
    tperm = template.get("permissions", {})
    for name in PERMISSION_LISTS:
        extra = [
            x for x in live.get("permissions", {}).get(name, []) if x not in tperm.get(name, [])
        ]
        if extra:
            overlay["permissions"][name] = extra
    for k, v in live.items():
        if k not in ("hooks", "env", "permissions") and template.get(k) != v:
            overlay["other"][k] = v
    return overlay


def apply(installed: dict, overlay: dict) -> dict:
    out: dict = json.loads(json.dumps(installed))
    have = _hook_keys(out)
    for event, groups in overlay.get("hooks", {}).items():
        for g in groups:
            if (event, g.get("matcher", ""), _scripts(g)) not in have:
                out.setdefault("hooks", {}).setdefault(event, []).append(g)
    out.setdefault("env", {}).update(overlay.get("env", {}))
    for name, items in overlay.get("permissions", {}).items():
        lst = out.setdefault("permissions", {}).setdefault(name, [])
        lst.extend(x for x in items if x not in lst)
    for k, v in overlay.get("other", {}).items():
        out[k] = v
    return out


def missing(installed: dict, overlay: dict) -> list[str]:
    problems = []
    have = _hook_keys(installed)
    for event, groups in overlay.get("hooks", {}).items():
        for g in groups:
            key = (event, g.get("matcher", ""), _scripts(g))
            if key not in have:
                problems.append(f"hook {event} {'/'.join(key[2]) or '?'}")
    for k, v in overlay.get("env", {}).items():
        if installed.get("env", {}).get(k) != v:
            problems.append(f"env {k}")
    for name, items in overlay.get("permissions", {}).items():
        lst = installed.get("permissions", {}).get(name, [])
        problems += [f"permissions.{name} item {i}" for i, x in enumerate(items) if x not in lst]
    for k, v in overlay.get("other", {}).items():
        if installed.get(k) != v:
            problems.append(f"key {k}")
    return problems


def summary(overlay: dict) -> str:
    hooks = sum(len(v) for v in overlay["hooks"].values())
    perms = sum(len(v) for v in overlay["permissions"].values())
    return (
        f"hooks={hooks} env_keys={sorted(overlay['env'])} permission_items={perms} "
        f"other_keys={sorted(overlay['other'])}"
    )


def _read(p: Path) -> dict:
    data: dict = json.loads(p.read_text(encoding="utf-8"))
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("extract", "apply", "verify"))
    ap.add_argument("--live", type=Path)
    ap.add_argument("--template", type=Path)
    ap.add_argument("--installed", type=Path)
    ap.add_argument("--overlay", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.command == "extract":
            ov = extract(_read(a.live), _read(a.template))
            print("overlay:", summary(ov))
            if not a.dry_run:
                if a.out is None:
                    print("--out is required unless --dry-run")
                    return 2
                a.out.write_text(json.dumps(ov, ensure_ascii=False, indent=2), encoding="utf-8")
            return 0
        ov = _read(a.overlay)
        inst = _read(a.installed)
        if a.command == "apply":
            stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            shutil.copy2(
                a.installed, a.installed.with_name(a.installed.name + f".bak-overlay-{stamp}")
            )
            merged = apply(inst, ov)
            a.installed.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print("applied:", summary(ov))
            return 0
        problems = missing(inst, ov)
        print(f"overlay items missing: {len(problems)}")
        for p in problems:
            print("  -", p)
        return 1 if problems else 0
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
