#!/usr/bin/env python3
"""Keep the private settings overlay across an install that replaces settings.json.

WHY: `install.sh --force-replace` writes the shipped settings.json over the user's file (with a
backup). The ownership model (docs/GLOBAL_VS_PROJECT_OVERLAY.md) keeps the private overlay --
personal hooks, env and permissions -- in that same user file, so an upgrade silently drops it.
Found in the RC 1.0 install rehearsal (2026-11-27). This tool extracts the overlay before the
install and puts it back after.

    python scripts/settings_overlay.py extract --live L.json --template NEW.json \
        [--old-template OLD.json] --out O.json        # O.json must be outside any git repository
    python scripts/settings_overlay.py extract --live L.json --template NEW.json --dry-run
    python scripts/settings_overlay.py apply   --installed I.json --overlay O.json
    python scripts/settings_overlay.py verify  --installed I.json --overlay O.json

A hook group is identified by event, matcher and its full commands and timeouts, with the home
directory part of any `.../.claude/` path normalised, so the same shipped hook under another home
matches, while a private variant with other arguments, another timeout or an inline command does
not. Pass the previously shipped settings as --old-template so items removed from the new release
are not carried back as "private". Output names keys and counts only, never values.
Exit codes: 0 ok, 1 verify found missing items, 2 usage, missing file or unsafe output path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_HOME_CLAUDE_RE = re.compile(r"[^\s\"']*?[/\\]\.claude[/\\]")


def _norm(cmd: str) -> str:
    return _HOME_CLAUDE_RE.sub("~/.claude/", cmd.replace("\\\\", "/").replace("\\", "/"))


def _hook_id(h: dict) -> tuple:
    return (h.get("type", ""), _norm(h.get("command", "")), h.get("timeout"))


def _group_key(event: str, group: dict) -> tuple:
    hooks = tuple(_hook_id(h) for h in group.get("hooks", []))
    return (event, group.get("matcher", ""), hooks)


def _shipped_hooks_by_slot(*settings: dict | None) -> dict[tuple, dict]:
    """{(event, matcher): {"ids": hook ids, "scripts": script names}} over the shipped files."""
    slots: dict[tuple, dict] = {}
    for s in settings:
        for event, groups in (s or {}).get("hooks", {}).items():
            for g in groups:
                slot = slots.setdefault(
                    (event, g.get("matcher", "")), {"ids": set(), "scripts": set()}
                )
                for h in g.get("hooks", []):
                    slot["ids"].add(_hook_id(h))
                    slot["scripts"].update(_SCRIPT_RE.findall(h.get("command", "")))
    return slots


def _hook_keys(settings: dict) -> set[tuple]:
    return {_group_key(ev, g) for ev, groups in settings.get("hooks", {}).items() for g in groups}


_SCRIPT_RE = re.compile(r"([A-Za-z0-9_.-]+\.(?:py|sh|ps1))")


def _script_key(event: str, group: dict) -> tuple | None:
    """(event, matcher, script names), or None for a group of inline commands only."""
    names = tuple(
        sorted(n for h in group.get("hooks", []) for n in _SCRIPT_RE.findall(h.get("command", "")))
    )
    return (event, group.get("matcher", ""), names) if names else None


def _script_keys(settings: dict) -> set[tuple]:
    keys = {_script_key(ev, g) for ev, groups in settings.get("hooks", {}).items() for g in groups}
    return {k for k in keys if k is not None}


def _differs(key: str, value: object, new: dict, old: dict | None) -> bool:
    """True if the live value is the user's own: not the new shipped value, not the old one."""
    if new.get(key) == value:
        return False
    return not (old is not None and old.get(key) == value)


def extract(live: dict, template: dict, old_template: dict | None = None) -> dict:
    for name, d in (("live", live), ("template", template), ("old template", old_template)):
        if d is not None and not isinstance(d, dict):
            raise TypeError(f"{name} settings must be a JSON object")
    overlay: dict = {"hooks": {}, "variants": {}, "env": {}, "permissions": {}, "other": {}}
    shipped = _hook_keys(template) | (_hook_keys(old_template) if old_template else set())
    shipped_scripts = _script_keys(template) | (
        _script_keys(old_template) if old_template else set()
    )
    shipped_by_slot = _shipped_hooks_by_slot(template, old_template)
    for event, groups in live.get("hooks", {}).items():
        for g in groups:
            if _group_key(event, g) in shipped:
                continue
            # WHY: the same shipped script with other arguments or a timeout is a live VARIANT,
            # not a private hook. Adding it next to the shipped group would run the hook twice;
            # it is reported and only applied on request, replacing the shipped group.
            if _script_key(event, g) in shipped_scripts:
                overlay["variants"].setdefault(event, []).append(g)
                continue
            # WHY (Codex review, PR #583): a private hook added INSIDE a shipped group used to
            # make the whole group "private", so apply appended a second copy and the shipped
            # hook ran twice. Only the hooks whose script is not shipped in this event+matcher
            # slot are restored, as a group of their own.
            slot = shipped_by_slot.get((event, g.get("matcher", "")))
            if slot:
                private = [
                    h
                    for h in g.get("hooks", [])
                    if not set(_SCRIPT_RE.findall(h.get("command", ""))) & slot["scripts"]
                    and _hook_id(h) not in slot["ids"]
                ]
                if len(private) < len(g.get("hooks", [])):
                    overlay["mixed_groups_split"] = overlay.get("mixed_groups_split", 0) + 1
                    if private:
                        part = {k: v for k, v in g.items() if k != "hooks"}
                        part["hooks"] = private
                        overlay["hooks"].setdefault(event, []).append(part)
                    continue
            overlay["hooks"].setdefault(event, []).append(g)
    tenv, oenv = template.get("env", {}), (old_template or {}).get("env") if old_template else None
    overlay["env"] = {k: v for k, v in live.get("env", {}).items() if _differs(k, v, tenv, oenv)}
    tperm = template.get("permissions", {})
    operm = (old_template or {}).get("permissions", {}) if old_template else None
    for name, value in live.get("permissions", {}).items():
        if isinstance(value, list):
            shipped_items = list(tperm.get(name, [])) + list((operm or {}).get(name, []))
            extra = [x for x in value if x not in shipped_items]
            if extra:
                overlay["permissions"][name] = extra
        elif _differs(name, value, tperm, operm):
            overlay["permissions"][name] = value
    for k, v in live.items():
        if k not in ("hooks", "env", "permissions") and _differs(k, v, template, old_template):
            overlay["other"][k] = v
    return overlay


def apply(installed: dict, overlay: dict, with_variants: bool = False) -> dict:
    out: dict = json.loads(json.dumps(installed))
    have = _hook_keys(out)
    for event, groups in overlay.get("hooks", {}).items():
        for g in groups:
            if _group_key(event, g) not in have:
                out.setdefault("hooks", {}).setdefault(event, []).append(g)
                have.add(_group_key(event, g))
    if with_variants:
        for event, groups in overlay.get("variants", {}).items():
            lst = out.setdefault("hooks", {}).setdefault(event, [])
            for g in groups:
                key = _script_key(event, g)
                same = [i for i, x in enumerate(lst) if _script_key(event, x) == key]
                if same:
                    lst[same[0]] = g
                    for i in reversed(same[1:]):
                        del lst[i]
                else:
                    lst.append(g)
    out.setdefault("env", {}).update(overlay.get("env", {}))
    perms = out.setdefault("permissions", {})
    for name, value in overlay.get("permissions", {}).items():
        if isinstance(value, list):
            lst = perms.setdefault(name, [])
            lst.extend(x for x in value if x not in lst)
        else:
            perms[name] = value
    for k, v in overlay.get("other", {}).items():
        out[k] = v
    return out


def missing(installed: dict, overlay: dict, with_variants: bool = False) -> list[str]:
    problems = []
    have = _hook_keys(installed)
    buckets = ("hooks", "variants") if with_variants else ("hooks",)
    for bucket in buckets:
        for event, groups in overlay.get(bucket, {}).items():
            for i, g in enumerate(groups):
                if _group_key(event, g) not in have:
                    problems.append(f"{bucket[:-1]} {event} #{i}")
    for k, v in overlay.get("env", {}).items():
        if installed.get("env", {}).get(k) != v:
            problems.append(f"env {k}")
    perms = installed.get("permissions", {})
    for name, value in overlay.get("permissions", {}).items():
        if isinstance(value, list):
            lst = perms.get(name, [])
            problems += [
                f"permissions.{name} item {i}" for i, x in enumerate(value) if x not in lst
            ]
        elif perms.get(name) != value:
            problems.append(f"permissions.{name}")
    for k, v in overlay.get("other", {}).items():
        if installed.get(k) != v:
            problems.append(f"key {k}")
    return problems


def summary(overlay: dict) -> str:
    hooks = sum(len(v) for v in overlay["hooks"].values())
    variants = sum(len(v) for v in overlay.get("variants", {}).values())
    perm_items = sum(len(v) if isinstance(v, list) else 1 for v in overlay["permissions"].values())
    return (
        f"hooks={hooks} variants_of_shipped={variants} "
        f"mixed_groups_split={overlay.get('mixed_groups_split', 0)} "
        f"env_keys={sorted(overlay['env'])} "
        f"permission_items={perm_items} "
        f"permission_keys={sorted(overlay['permissions'])} other_keys={sorted(overlay['other'])}"
    )


def _inside_git_repo(path: Path) -> bool:
    """True if `path` would be committable: inside a git work tree and not ignored there.

    WHY: the overlay can hold private values; it must never land where `git add` can pick it up.
    A home directory that is itself a repository but ignores its temp folders is fine.
    """
    target = path.resolve()
    try:
        top = subprocess.run(
            ["git", "-C", str(target.parent), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if top.returncode != 0:
            return False
        ignored = subprocess.run(
            ["git", "-C", top.stdout.strip(), "check-ignore", "-q", str(target)],
            capture_output=True,
            timeout=10,
        )
        return ignored.returncode != 0
    except (OSError, subprocess.TimeoutExpired):
        # Without git, be conservative: any .git above the path counts as a repository.
        return any((p / ".git").exists() for p in target.parents)


def _read(p: Path) -> dict:
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("settings must be a JSON object")
    return data


def _write_private(path: Path, text: str) -> None:
    """Write `text` to a file readable by its owner only (0600 on POSIX)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, 0o600)  # O_CREAT mode does not apply to an existing file


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("extract", "apply", "verify"))
    ap.add_argument("--live", type=Path)
    ap.add_argument("--template", type=Path)
    ap.add_argument("--old-template", type=Path)
    ap.add_argument("--installed", type=Path)
    ap.add_argument("--overlay", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--with-variants",
        action="store_true",
        help="apply/verify: also replace shipped hook groups with the live variants",
    )
    a = ap.parse_args(argv)
    try:
        if a.command == "extract":
            if a.live is None or a.template is None:
                print("--live and --template are required")
                return 2
            old = _read(a.old_template) if a.old_template else None
            ov = extract(_read(a.live), _read(a.template), old)
            print("overlay:", summary(ov))
            if old is None:
                print(
                    "note: no --old-template; items removed from the new release count as private"
                )
            if not a.dry_run:
                if a.out is None:
                    print("--out is required unless --dry-run")
                    return 2
                if _inside_git_repo(a.out):
                    print("refused: --out is inside a git repository")
                    return 2
                _write_private(a.out, json.dumps(ov, ensure_ascii=False, indent=2))
            return 0
        if a.overlay is None or a.installed is None:
            print("--installed and --overlay are required")
            return 2
        ov = _read(a.overlay)
        inst = _read(a.installed)
        if a.command == "apply":
            stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            shutil.copy2(
                a.installed, a.installed.with_name(a.installed.name + f".bak-overlay-{stamp}")
            )
            merged = apply(inst, ov, with_variants=a.with_variants)
            tmp = a.installed.with_name(a.installed.name + ".tmp-overlay")
            # WHY (Codex review, PR #583): the temp file is created owner-only and then gets the
            # original file's mode, so replacing a 0600 settings.json never widens it to 0644.
            _write_private(tmp, json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
            shutil.copymode(a.installed, tmp)
            tmp.replace(a.installed)
            print("applied:", summary(ov))
            return 0
        problems = missing(inst, ov, with_variants=a.with_variants)
        print(f"overlay items missing: {len(problems)}")
        for p in problems:
            print("  -", p)
        return 1 if problems else 0
    except (OSError, TypeError, AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
