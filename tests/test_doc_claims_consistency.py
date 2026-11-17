"""Doc claims that describe enforcement must match the code/settings they describe.

Each test ties one prose claim to the artifact that makes it true or false, so the
claim cannot silently outlive the mechanism (found 2026-11-07: root CLAUDE.md said
PostToolUse blocks via exit(1); rules/permissions.md listed a test-edit deny that
settings.json never had; CLAUDE.md called a generated file hand-maintained).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_root_claude_md_does_not_claim_posttooluse_blocks() -> None:
    """PostToolUse runs after the tool; hooks/lib/runtime.py documents that no exit code blocks."""
    text = _read("CLAUDE.md")
    section = text.split("### PreToolUse vs PostToolUse blocking", 1)[1].split("###", 1)[0]
    post = section.split("**PostToolUse**", 1)[1]
    assert not re.search(r"blocks\s+via\s+`sys\.exit\(1\)`", post)
    assert "cannot block" in post
    # the source of truth must still say the same thing, or this test guards nothing
    assert "no exit code can undo or block it" in _read("hooks/lib/runtime.py")


def test_permissions_doc_edit_denies_exist_in_settings() -> None:
    """Every `Edit ...` bullet under Auto-Denied must have an Edit(...) rule in settings deny."""
    doc = _read("rules/permissions.md")
    denied = doc.split("## Auto-Denied", 1)[1].split("\n## ", 1)[0]
    claimed_edit_denies = [ln for ln in denied.splitlines() if re.match(r"-\s+Edit\b", ln)]
    deny = json.loads(_read("hooks/settings.json"))["permissions"]["deny"]
    has_test_edit_deny = any(d.startswith("Edit(") and "test" in d.lower() for d in deny)
    if claimed_edit_denies:
        assert has_test_edit_deny, (
            "rules/permissions.md lists Edit denies that hooks/settings.json does not define: "
            f"{claimed_edit_denies}"
        )
    # real protection against test weakening lives in a hook, and the doc must name it
    assert "weakened_test_guard" in doc


def test_hooks_json_is_documented_as_generated() -> None:
    """hooks/hooks.json is produced by scripts/sync_plugin_hooks.py; docs must not call it manual."""
    text = _read("CLAUDE.md")
    assert "kept in sync manually" not in text
    assert "generated from" in text
    assert (ROOT / "scripts" / "sync_plugin_hooks.py").is_file()


# --------------------------------------------------------------------------- semantic checks
def _registry() -> dict:
    import yaml

    reg = yaml.safe_load(_read("hooks/registry.yaml"))
    return reg.get("hooks", reg)


def _registered_events() -> dict[str, set[str]]:
    """hook file stem -> events it is wired under in hooks/settings.json."""
    out: dict[str, set[str]] = {}
    for event, groups in json.loads(_read("hooks/settings.json"))["hooks"].items():
        for group in groups:
            for h in group.get("hooks", []):
                m = re.search(r"(\w+)\.py", h.get("command", ""))
                if m:
                    out.setdefault(m.group(1), set()).add(event)
    return out


def test_no_hook_claims_to_block_where_blocking_is_impossible() -> None:
    """H1, behavioural: a hook wired only to events after the action (PostToolUse etc.) may not
    be registered with escalation: block -- that is exactly what the old doc line implied."""
    events = _registered_events()
    after_only = {"PostToolUse", "PostToolUseFailure", "Stop", "SubagentStop", "SessionStart"}
    offenders = [
        name
        for name, fields in _registry().items()
        if fields.get("escalation") == "block"
        and events.get(name)
        and events[name] <= after_only
    ]
    assert offenders == []


def test_weakened_test_guard_is_wired_before_the_edit() -> None:
    """H2, behavioural: the real protection against weakened tests must run on PreToolUse."""
    assert "PreToolUse" in _registered_events().get("weakened_test_guard", set())
    assert _registry()["weakened_test_guard"]["event"] == "PreToolUse"


def test_hooks_json_matches_what_the_generator_produces() -> None:
    """H4, behavioural: not just a doc sentence -- hooks.json must equal the generator output."""
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_plugin_hooks.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_rules_that_name_a_dormant_hook_say_it_is_dormant() -> None:
    """H5: available != active. A rule file naming a hook the registry marks `class: dormant`
    (not wired, owner decision) must say so, or it presents a disabled hook as protection."""
    dormant = [n for n, f in _registry().items() if f.get("class") == "dormant"]
    assert dormant, "registry has no dormant hooks -- the test would guard nothing"
    stale = []
    for rule in sorted((ROOT / "rules").glob("*.md")):
        text = rule.read_text(encoding="utf-8")
        named = [n for n in dormant if re.search(rf"\b{re.escape(n)}\b", text)]
        if named and "dormant" not in text.lower():
            stale.append((rule.name, named))
    assert stale == []
