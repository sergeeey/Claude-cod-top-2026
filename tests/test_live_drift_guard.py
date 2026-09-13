"""Tests for live_drift_guard.py -- SessionStart hook warning when the
installed ~/.claude copy has diverged from what this repo ships: hooks/
(content + event wiring) and rules/ (content + personal-install-only files).

WHY: this hook exists because a real merged fix (PR #296, the circuit-
breaker lock race) sat undeployed on the live install with nothing to
catch it. It must fire only inside this repo's own checkout, only warn
(never block), and never crash session start on any I/O error.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

import live_drift_guard as ldg

# ── is_this_repo ─────────────────────────────────────────────────────────────


class TestIsThisRepo:
    def test_true_when_both_registries_present(self, tmp_path):
        (tmp_path / "hooks").mkdir()
        (tmp_path / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        assert ldg.is_this_repo(tmp_path) is True

    def test_false_when_only_one_registry_present(self, tmp_path):
        (tmp_path / "hooks").mkdir()
        (tmp_path / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        assert ldg.is_this_repo(tmp_path) is False

    def test_false_for_unrelated_directory(self, tmp_path):
        assert ldg.is_this_repo(tmp_path) is False


# ── find_drift ───────────────────────────────────────────────────────────────


class TestFindDrift:
    def test_no_drift_when_content_matches(self, tmp_path):
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        repo.mkdir()
        live.mkdir()
        (repo / "a.py").write_text("same", encoding="utf-8")
        (live / "a.py").write_text("same", encoding="utf-8")
        assert ldg.find_drift(repo, live) == []

    def test_reports_drift_when_content_differs(self, tmp_path):
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        repo.mkdir()
        live.mkdir()
        (repo / "a.py").write_text("new version", encoding="utf-8")
        (live / "a.py").write_text("old version", encoding="utf-8")
        assert ldg.find_drift(repo, live) == ["a.py"]

    def test_ignores_file_missing_from_live(self, tmp_path):
        """Not yet deployed is a different fact than drifted -- must not conflate."""
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        repo.mkdir()
        live.mkdir()
        (repo / "brand_new_hook.py").write_text("content", encoding="utf-8")
        assert ldg.find_drift(repo, live) == []

    def test_ignores_file_only_in_live(self, tmp_path):
        """A personal-only hook that isn't in the repo at all is not drift."""
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        repo.mkdir()
        live.mkdir()
        (live / "personal_hook.py").write_text("content", encoding="utf-8")
        assert ldg.find_drift(repo, live) == []

    def test_ignores_pycache(self, tmp_path):
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        (repo / "__pycache__").mkdir(parents=True)
        (live / "__pycache__").mkdir(parents=True)
        (repo / "__pycache__" / "a.cpython-311.pyc.py").write_text("x", encoding="utf-8")
        (live / "__pycache__" / "a.cpython-311.pyc.py").write_text("y", encoding="utf-8")
        assert ldg.find_drift(repo, live) == []

    def test_finds_drift_in_nested_lib_directory(self, tmp_path):
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        (repo / "lib").mkdir(parents=True)
        (live / "lib").mkdir(parents=True)
        (repo / "lib" / "state.py").write_text("new", encoding="utf-8")
        (live / "lib" / "state.py").write_text("old", encoding="utf-8")
        assert ldg.find_drift(repo, live) == [os.path.join("lib", "state.py")]


# ── find_event_registration_drift ───────────────────────────────────────────


class TestFindEventRegistrationDrift:
    """Regression suite for the exact real incident that motivated this
    check (2026-09-02): permission_policy.py was byte-identical between
    repo and live, but registered under PermissionRequest in live vs
    PreToolUse in the repo -- content hashing (find_drift) structurally
    cannot see this class of bug, because the .py file never differed."""

    def _write_settings(self, path, hooks: dict) -> None:
        import json

        path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")

    def test_no_finding_when_same_event_in_both(self, tmp_path):
        repo = tmp_path / "repo_settings.json"
        live = tmp_path / "live_settings.json"
        self._write_settings(
            repo, {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "python x/a.py"}]}]}
        )
        self._write_settings(
            live, {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "py.exe y/a.py"}]}]}
        )
        assert ldg.find_event_registration_drift(repo, live) == []

    def test_finds_the_real_permission_policy_incident_shape(self, tmp_path):
        """Reproduces the exact 2026-09-02 case: same script, PreToolUse in
        repo, PermissionRequest in live."""
        repo = tmp_path / "repo_settings.json"
        live = tmp_path / "live_settings.json"
        self._write_settings(
            repo,
            {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"command": "python x/permission_policy.py"}]}
                ]
            },
        )
        self._write_settings(
            live,
            {
                "PermissionRequest": [
                    {"matcher": "", "hooks": [{"command": "py.exe y/permission_policy.py"}]}
                ]
            },
        )
        findings = ldg.find_event_registration_drift(repo, live)
        assert len(findings) == 1
        assert "permission_policy.py" in findings[0]
        assert "PreToolUse" in findings[0]
        assert "PermissionRequest" in findings[0]

    def test_ignores_hook_not_deployed_live_at_all(self, tmp_path):
        """Not deployed is find_drift's territory (content), not this
        check's (wiring) -- must not double-report the same underlying gap
        under two different messages."""
        repo = tmp_path / "repo_settings.json"
        live = tmp_path / "live_settings.json"
        self._write_settings(
            repo, {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "python x/new.py"}]}]}
        )
        self._write_settings(live, {})
        assert ldg.find_event_registration_drift(repo, live) == []

    def test_hook_on_multiple_events_matches_when_sets_equal(self, tmp_path):
        """A hook legitimately registered under two events (e.g. PostToolUse
        AND Stop) must compare as SETS, not fail on ordering."""
        repo = tmp_path / "repo_settings.json"
        live = tmp_path / "live_settings.json"
        self._write_settings(
            repo,
            {
                "Stop": [{"matcher": "", "hooks": [{"command": "python x/gate.py"}]}],
                "PostToolUse": [{"matcher": "Bash", "hooks": [{"command": "python x/gate.py"}]}],
            },
        )
        self._write_settings(
            live,
            {
                "PostToolUse": [{"matcher": "Bash", "hooks": [{"command": "py.exe y/gate.py"}]}],
                "Stop": [{"matcher": "", "hooks": [{"command": "py.exe y/gate.py"}]}],
            },
        )
        assert ldg.find_event_registration_drift(repo, live) == []

    def test_finds_missing_event_when_hook_registered_on_fewer_events_live(self, tmp_path):
        """Reproduces the second real finding from the same session:
        commit_test_gate.py registered on PreToolUse+PostToolUse+Stop in the
        repo, but only PreToolUse+PostToolUse live -- a partial deregistration,
        not a full one, so find_drift's "not deployed" carve-out must not
        swallow it."""
        repo = tmp_path / "repo_settings.json"
        live = tmp_path / "live_settings.json"
        self._write_settings(
            repo,
            {
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "python x/gate.py"}]}],
                "PostToolUse": [{"matcher": "Bash", "hooks": [{"command": "python x/gate.py"}]}],
                "Stop": [{"matcher": "", "hooks": [{"command": "python x/gate.py"}]}],
            },
        )
        self._write_settings(
            live,
            {
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "py.exe y/gate.py"}]}],
                "PostToolUse": [{"matcher": "Bash", "hooks": [{"command": "py.exe y/gate.py"}]}],
            },
        )
        findings = ldg.find_event_registration_drift(repo, live)
        assert len(findings) == 1
        assert "gate.py" in findings[0]
        assert "Stop" in findings[0]

    def test_malformed_json_returns_no_findings_not_a_crash(self, tmp_path):
        repo = tmp_path / "repo_settings.json"
        live = tmp_path / "live_settings.json"
        repo.write_text("{not valid json", encoding="utf-8")
        self._write_settings(live, {})
        assert ldg.find_event_registration_drift(repo, live) == []


# ── main (end-to-end, via monkeypatch) ───────────────────────────────────────


class TestMain:
    def test_silent_outside_this_repo(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        ldg.main()
        assert capsys.readouterr().out == ""

    def test_silent_when_claude_home_missing(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "hooks").mkdir()
        (tmp_path / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "does_not_exist"))
        ldg.main()
        assert capsys.readouterr().out == ""

    def test_warns_on_real_drift(self, tmp_path, monkeypatch, capsys):
        repo_root = tmp_path / "repo"
        (repo_root / "hooks").mkdir(parents=True)
        (repo_root / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "skills").mkdir()
        (repo_root / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "hooks" / "some_hook.py").write_text("new", encoding="utf-8")

        claude_home = tmp_path / "claude_home"
        (claude_home / "hooks").mkdir(parents=True)
        (claude_home / "hooks" / "some_hook.py").write_text("old", encoding="utf-8")

        monkeypatch.chdir(repo_root)
        monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
        ldg.main()
        out = capsys.readouterr().out
        assert "live-drift-guard" in out
        assert "some_hook.py" in out

    def test_real_drift_points_at_the_direction_aware_redeploy(self, tmp_path, monkeypatch, capsys):
        """Wiring, not logic: scripts/redeploy_drift.py only helps if the person
        reading this hook's output learns it exists -- and learns NOT to reach for
        the two scripts that overwrite without checking direction."""
        repo_root = tmp_path / "repo"
        (repo_root / "hooks").mkdir(parents=True)
        (repo_root / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "skills").mkdir()
        (repo_root / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "hooks" / "some_hook.py").write_text("new", encoding="utf-8")
        claude_home = tmp_path / "claude_home"
        (claude_home / "hooks").mkdir(parents=True)
        (claude_home / "hooks" / "some_hook.py").write_text("old", encoding="utf-8")
        monkeypatch.chdir(repo_root)
        monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
        ldg.main()
        out = capsys.readouterr().out
        assert "scripts/redeploy_drift.py" in out
        assert "sync_config.py" in out

    def test_no_redeploy_pointer_when_hooks_match(self, tmp_path, monkeypatch, capsys):
        repo_root = tmp_path / "repo"
        (repo_root / "hooks").mkdir(parents=True)
        (repo_root / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "skills").mkdir()
        (repo_root / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "hooks" / "some_hook.py").write_text("same", encoding="utf-8")
        claude_home = tmp_path / "claude_home"
        (claude_home / "hooks").mkdir(parents=True)
        (claude_home / "hooks" / "some_hook.py").write_text("same", encoding="utf-8")
        monkeypatch.chdir(repo_root)
        monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
        ldg.main()
        assert "redeploy_drift" not in capsys.readouterr().out

    def test_silent_when_live_hooks_is_same_path_as_repo_hooks(self, tmp_path, monkeypatch, capsys):
        """A --link install (or --target pointing at the repo itself) can't drift."""
        repo_root = tmp_path / "repo"
        (repo_root / "hooks").mkdir(parents=True)
        (repo_root / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "skills").mkdir()
        (repo_root / "skills" / "registry.yaml").write_text("x", encoding="utf-8")

        monkeypatch.chdir(repo_root)
        monkeypatch.setenv("CLAUDE_HOME", str(repo_root))
        ldg.main()
        assert capsys.readouterr().out == ""

    def test_never_raises_on_unreadable_file(self, tmp_path, monkeypatch, capsys):
        repo_root = tmp_path / "repo"
        (repo_root / "hooks").mkdir(parents=True)
        (repo_root / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "skills").mkdir()
        (repo_root / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "hooks" / "some_hook.py").write_text("content", encoding="utf-8")

        claude_home = tmp_path / "claude_home"
        (claude_home / "hooks").mkdir(parents=True)
        (claude_home / "hooks" / "some_hook.py").write_text("content", encoding="utf-8")

        monkeypatch.chdir(repo_root)
        monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
        # Must not raise even if main()'s internals hit an unexpected error.
        ldg.main()
        assert "Traceback" not in capsys.readouterr().err


# -- rules drift (added 2026-09-09) -----------------------------------------


class TestLiveRuleFiles:
    """`_live_rule_files` must see the nested rules/pearl_registry/ case and
    must NOT see a live install's runtime junk or its backup files."""

    def test_finds_flat_and_nested_markdown(self, tmp_path):
        (tmp_path / "a.md").write_text("x", encoding="utf-8")
        (tmp_path / "pearl_registry").mkdir()
        (tmp_path / "pearl_registry" / "INDEX.md").write_text("x", encoding="utf-8")
        found = {p.relative_to(tmp_path).as_posix() for p in ldg._live_rule_files(tmp_path)}
        assert found == {"a.md", "pearl_registry/INDEX.md"}

    def test_skips_dot_directories(self, tmp_path):
        """The live install really did grow rules/pearl_registry/.claude/ from
        a hook that ran with that cwd -- nothing in there is a rule."""
        (tmp_path / "a.md").write_text("x", encoding="utf-8")
        junk = tmp_path / "pearl_registry" / ".claude" / "state"
        junk.mkdir(parents=True)
        (junk / "note.md").write_text("x", encoding="utf-8")
        found = {p.relative_to(tmp_path).as_posix() for p in ldg._live_rule_files(tmp_path)}
        assert found == {"a.md"}

    def test_ignores_personal_backup_files(self, tmp_path):
        """`<name>.md.backup.<stamp>` / `<name>.md.bak-<stamp>` do not end in
        .md, so the glob excludes them with no special-casing."""
        (tmp_path / "a.md").write_text("x", encoding="utf-8")
        (tmp_path / "a.md.backup.20260603_205259").write_text("old", encoding="utf-8")
        (tmp_path / "a.md.bak-20260729-144938").write_text("old", encoding="utf-8")
        found = {p.relative_to(tmp_path).as_posix() for p in ldg._live_rule_files(tmp_path)}
        assert found == {"a.md"}


class TestFindRulesDrift:
    def test_nothing_when_trees_match(self, tmp_path):
        repo, live = tmp_path / "repo", tmp_path / "live"
        repo.mkdir()
        live.mkdir()
        (repo / "a.md").write_text("same", encoding="utf-8")
        (live / "a.md").write_text("same", encoding="utf-8")
        assert ldg.find_rules_drift(repo, live) == ([], [])

    def test_reports_rule_missing_from_the_distribution(self, tmp_path):
        """The real 2026-09-09 shape: a rule that is live and load-bearing for
        its author but was never in the repo at all."""
        repo, live = tmp_path / "repo", tmp_path / "live"
        repo.mkdir()
        live.mkdir()
        (live / "autonomy-budget.md").write_text("real content", encoding="utf-8")
        missing, drifted = ldg.find_rules_drift(repo, live)
        assert missing == ["autonomy-budget.md"]
        assert drifted == []

    def test_reports_nested_rule_missing_from_the_distribution(self, tmp_path):
        repo, live = tmp_path / "repo", tmp_path / "live"
        repo.mkdir()
        live.mkdir()
        (live / "pearl_registry").mkdir()
        (live / "pearl_registry" / "INDEX.md").write_text("pearls", encoding="utf-8")
        missing, drifted = ldg.find_rules_drift(repo, live)
        assert missing == ["pearl_registry/INDEX.md"]
        assert drifted == []

    def test_reports_content_drift(self, tmp_path):
        repo, live = tmp_path / "repo", tmp_path / "live"
        repo.mkdir()
        live.mkdir()
        (repo / "a.md").write_text("old text", encoding="utf-8")
        (live / "a.md").write_text("new text", encoding="utf-8")
        missing, drifted = ldg.find_rules_drift(repo, live)
        assert missing == []
        assert drifted == ["a.md"]

    def test_line_ending_difference_alone_is_not_drift(self, tmp_path):
        """.gitattributes pins *.md to LF while a personal copy on Windows can
        be CRLF or mixed -- byte comparison would report permanent, unfixable
        drift on identical content. pearl_registry/INDEX.md really was mixed
        (21 CR against 23 LF)."""
        repo, live = tmp_path / "repo", tmp_path / "live"
        repo.mkdir()
        live.mkdir()
        (repo / "a.md").write_bytes(b"line one\nline two\nline three\n")
        (live / "a.md").write_bytes(b"line one\r\nline two\nline three\r\n")
        assert ldg.find_rules_drift(repo, live) == ([], [])

    def test_repo_only_rule_is_not_reported(self, tmp_path):
        """Shipped here but not installed live is an un-run redeploy, not a
        distribution gap -- find_drift() declines the same direction."""
        repo, live = tmp_path / "repo", tmp_path / "live"
        repo.mkdir()
        live.mkdir()
        (repo / "evidence-markers.md").write_text("x", encoding="utf-8")
        assert ldg.find_rules_drift(repo, live) == ([], [])


class TestMainRulesHalf:
    def _make_repo(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "hooks").mkdir(parents=True)
        (repo / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo / "skills").mkdir()
        (repo / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo / "rules").mkdir()
        return repo

    def test_warns_on_rule_missing_from_distribution(self, tmp_path, monkeypatch, capsys):
        repo = self._make_repo(tmp_path)
        home = tmp_path / "home"
        (home / "hooks").mkdir(parents=True)
        (home / "rules").mkdir()
        (home / "rules" / "pearl_registry").mkdir()
        (home / "rules" / "pearl_registry" / "INDEX.md").write_text("p", encoding="utf-8")
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_HOME", str(home))
        ldg.main()
        out = capsys.readouterr().out
        assert "NOT shipped by this repo" in out
        assert "pearl_registry/INDEX.md" in out

    def test_silent_when_live_install_has_no_rules_dir(self, tmp_path, monkeypatch, capsys):
        """A hooks-only or minimal install, and the clean-CI-runner case: the
        absence of a personal rules/ tree is normal, not a finding."""
        repo = self._make_repo(tmp_path)
        (repo / "rules" / "a.md").write_text("x", encoding="utf-8")
        home = tmp_path / "home"
        (home / "hooks").mkdir(parents=True)
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_HOME", str(home))
        ldg.main()
        assert capsys.readouterr().out == ""

    def test_silent_when_rules_trees_are_the_same_path(self, tmp_path, monkeypatch, capsys):
        """A --link style install pointing straight at this repo can never
        drift; comparing a tree to itself would only ever report zero."""
        repo = self._make_repo(tmp_path)
        (repo / "rules" / "a.md").write_text("x", encoding="utf-8")
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_HOME", str(repo))
        ldg.main()
        assert capsys.readouterr().out == ""

    def test_never_raises_when_rules_tree_is_unreadable(self, tmp_path, monkeypatch, capsys):
        repo = self._make_repo(tmp_path)
        home = tmp_path / "home"
        (home / "hooks").mkdir(parents=True)
        (home / "rules").mkdir()
        (home / "rules" / "a.md").write_text("x", encoding="utf-8")
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_HOME", str(home))

        def boom(*_args, **_kwargs):
            raise OSError("unreadable")

        monkeypatch.setattr(ldg.Path, "rglob", boom)
        ldg.main()  # must not raise
        assert "skipped" in capsys.readouterr().err


# ── the event-wiring check actually running (2026-09-10) ────────────────────
class TestEventCheckActuallyRuns:
    """Two bugs found the same day, both in the check written to catch dead hooks.

    1. main() read live settings from `<claude_home>/hooks/settings.json`, but
       install.sh copies the template to `<claude_home>/settings.json`. That path
       never exists, so the `is_file()` guard was always False and the entire
       event-wiring check was dead code -- the function added to catch hooks that
       are installed but never run was itself installed and never run.
    2. Even with the path fixed, a hook whose FILE is deployed live but which is
       registered under no event at all was skipped by a `continue` that assumed
       "no live registration" implies "not deployed". It does not, and that is
       exactly how model_switch_tracker.py sat deployed and inert.
    """

    @staticmethod
    def _settings(events: dict[str, str]) -> str:
        return json.dumps(
            {
                "hooks": {
                    ev: [{"matcher": "", "hooks": [{"type": "command", "command": f"py {name}"}]}]
                    for ev, name in events.items()
                }
            }
        )

    def test_deployed_but_unregistered_hook_is_reported(self, tmp_path):
        repo = tmp_path / "repo_settings.json"
        live = tmp_path / "live_settings.json"
        repo.write_text(self._settings({"PostModelSwitch": "hooks/tracker.py"}), encoding="utf-8")
        live.write_text(self._settings({}), encoding="utf-8")

        live_hooks = tmp_path / "live_hooks"
        live_hooks.mkdir()
        (live_hooks / "tracker.py").write_text("deployed", encoding="utf-8")

        findings = ldg.find_event_registration_drift(repo, live, live_hooks)
        assert len(findings) == 1
        assert "tracker.py" in findings[0]
        assert "NO event" in findings[0]

    def test_hook_absent_from_live_is_still_not_reported_here(self, tmp_path):
        """An un-run redeploy stays find_drift's territory, as originally reasoned.

        This is the half of the old `continue` that was correct, and it must not
        regress into noise now that the other half reports.
        """
        repo = tmp_path / "repo_settings.json"
        live = tmp_path / "live_settings.json"
        repo.write_text(self._settings({"PostModelSwitch": "hooks/tracker.py"}), encoding="utf-8")
        live.write_text(self._settings({}), encoding="utf-8")

        live_hooks = tmp_path / "live_hooks"
        live_hooks.mkdir()  # tracker.py deliberately NOT created

        assert ldg.find_event_registration_drift(repo, live, live_hooks) == []

    def test_omitting_live_hooks_disables_only_the_new_sub_check(self, tmp_path):
        repo = tmp_path / "repo_settings.json"
        live = tmp_path / "live_settings.json"
        repo.write_text(self._settings({"PostModelSwitch": "hooks/tracker.py"}), encoding="utf-8")
        live.write_text(self._settings({}), encoding="utf-8")
        assert ldg.find_event_registration_drift(repo, live) == []

    def test_main_reads_live_settings_from_claude_home_root(self, tmp_path, monkeypatch, capsys):
        """The path bug: settings.json lives at the install root, not under hooks/."""
        repo_root = tmp_path / "repo"
        (repo_root / "hooks").mkdir(parents=True)
        (repo_root / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "skills").mkdir()
        (repo_root / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "hooks" / "tracker.py").write_text("same", encoding="utf-8")
        (repo_root / "hooks" / "settings.json").write_text(
            self._settings({"PostModelSwitch": "hooks/tracker.py"}), encoding="utf-8"
        )

        claude_home = tmp_path / "claude_home"
        (claude_home / "hooks").mkdir(parents=True)
        # byte-identical, so find_drift correctly stays silent
        (claude_home / "hooks" / "tracker.py").write_text("same", encoding="utf-8")
        # at the ROOT, where install.sh actually puts it -- and with no event
        (claude_home / "settings.json").write_text(self._settings({}), encoding="utf-8")

        monkeypatch.chdir(repo_root)
        monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
        ldg.main()
        out = capsys.readouterr().out
        assert "tracker.py" in out, "the dead hook must surface once the path is right"


# ── shipped artifacts: agents/ + commands/ + skills/ (2026-09-11) ───────────
class TestStripGeneratedFields:
    """_strip_generated_fields, added 2026-09-11 alongside the `enriched`
    bucket below -- strips the two known, mechanically-explainable causes of
    skill content-drift so what remains is the body worth comparing."""

    def test_strips_triggers_field(self):
        text = "---\nname: x\ntriggers: [/x, phrase]\n---\nbody\n"
        assert "triggers:" not in ldg._strip_generated_fields(text)

    def test_leaves_body_mention_of_the_word_triggers_alone(self):
        """Only the machine-written `triggers: [...]` LINE is a known cause --
        a free-text sentence that happens to contain the word must survive,
        or this would silently eat real content on any skill whose prose
        discusses triggers (several do, describing their own routing)."""
        text = "---\nname: x\n---\nThis skill discusses triggers as a concept.\n"
        assert ldg._strip_generated_fields(text) == text

    def test_strips_leading_bsv_block(self):
        text = (
            "<!-- BSV -- Brief Skill View | search: BSV\n"
            "Скил   : x\n"
            "-->\n\n"
            "---\nname: x\n---\nbody\n"
        )
        stripped = ldg._strip_generated_fields(text)
        assert "BSV" not in stripped
        assert "---\nname: x\n---\nbody\n" == stripped

    def test_strips_both_when_both_present(self):
        text = (
            "<!-- BSV -- Brief Skill View | search: BSV\n-->\n\n"
            "---\nname: x\ntriggers: [/x]\n---\nbody\n"
        )
        stripped = ldg._strip_generated_fields(text)
        assert "BSV" not in stripped
        assert "triggers:" not in stripped

    def test_body_only_difference_survives_the_strip(self):
        """The whole point: a REAL content change must not be strippable --
        only the two specific, named causes are."""
        text = "---\nname: x\n---\nreal body text\n"
        assert ldg._strip_generated_fields(text) == text


class TestFindShippedArtifactDrift:
    """The third tree family, added as the cheap falsifiable test recorded in
    docs/artifact-distribution-topology.md (#424) against building a
    declarative artifact inventory.

    Returns (missing_live, drifted, enriched) -- deliberately NOT a merge of
    any two of these, and NOT the same skip rule find_rules_drift uses for
    "shipped, not yet live". The first draft of this function used that rule
    here too and was wrong to: #425 (release-scout.md) was exactly this
    shape -- shipped, absent live -- and was not a redeploy lag, it was
    install.sh reading the wrong source tree. Silently calling that "un-run
    redeploy" is the same complacent assumption that let release-scout stay
    invisible. Caught by review before merge, not found live a second time.

    `enriched` (added 2026-09-11) is the third bucket: present in both, raw
    text differs, but the difference is fully explained by
    _strip_generated_fields's two known causes. Its own test class is below;
    these tests only need to confirm find_shipped_artifact_drift routes to
    the right bucket, not re-litigate what counts as a known cause.

    Two more properties here are not stylistic -- each encodes a measurement
    made before the code was written, and each would be silently lost by an
    "obvious" refactor that reused find_rules_drift's logic:

    * the live install holds 583 skill .md against 135 shipped, so the
      LIVE-but-not-shipped direction (the fourth one, not returned here at
      all) must stay off for these kinds;
    * the repo nests skills as skills/{core,extensions}/<name>/SKILL.md while
      install.sh syncs them FLAT, so a same-relative-path comparison finds
      nothing at all and reports a clean tree.
    """

    def _trees(self, tmp_path):
        repo, home = tmp_path / "repo", tmp_path / "home"
        for d in ("agents", "commands", "skills"):
            (repo / d).mkdir(parents=True)
            (home / d).mkdir(parents=True)
        return repo, home

    def test_nothing_when_everything_matches(self, tmp_path):
        repo, home = self._trees(tmp_path)
        (repo / "agents" / "builder.md").write_text("same", encoding="utf-8")
        (home / "agents" / "builder.md").write_text("same", encoding="utf-8")
        assert ldg.find_shipped_artifact_drift(repo, home) == ([], [], [])

    def test_reports_agent_content_drift(self, tmp_path):
        repo, home = self._trees(tmp_path)
        (repo / "agents" / "reviewer.md").write_text("new", encoding="utf-8")
        (home / "agents" / "reviewer.md").write_text("old", encoding="utf-8")
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == []
        assert drifted == ["agent: reviewer.md"]
        assert enriched == []

    def test_reports_command_content_drift(self, tmp_path):
        """The content-drift half of the #425 shape: the file IS present
        live, so nothing looks missing -- it simply came from the wrong
        source, and no check could see it."""
        repo, home = self._trees(tmp_path)
        (repo / "commands" / "evolve-solution.md").write_text("6398 B", encoding="utf-8")
        (home / "commands" / "evolve-solution.md").write_text("2005 B", encoding="utf-8")
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == []
        assert drifted == ["command: evolve-solution.md"]
        assert enriched == []

    def test_reports_shipped_artifact_missing_from_live(self, tmp_path):
        """The OTHER half of the #425 shape, and the one the first draft of
        this function got wrong: release-scout.md was shipped and had NO
        live counterpart at all, because install.sh read the wrong source
        tree -- not because a redeploy simply hadn't run yet."""
        repo, home = self._trees(tmp_path)
        (repo / "commands" / "release-scout.md").write_text("x", encoding="utf-8")
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == ["command: release-scout.md"]
        assert drifted == []
        assert enriched == []

    def test_missing_and_drifted_are_both_reported_together(self, tmp_path):
        repo, home = self._trees(tmp_path)
        (repo / "agents" / "verifier.md").write_text("x", encoding="utf-8")  # missing
        (repo / "agents" / "reviewer.md").write_text("new", encoding="utf-8")
        (home / "agents" / "reviewer.md").write_text("old", encoding="utf-8")  # drifted
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == ["agent: verifier.md"]
        assert drifted == ["agent: reviewer.md"]
        assert enriched == []

    def test_skills_map_nested_repo_path_to_flat_live_path(self, tmp_path):
        """THE test for this whole addition. The repo nests skills two levels
        deep; install.sh lands them flat. Comparing by relative path finds no
        counterpart for any skill and reports a clean tree -- silence that
        looks like health, the worst failure mode a drift check has."""
        repo, home = self._trees(tmp_path)
        (repo / "skills" / "core" / "brainstorming").mkdir(parents=True)
        (repo / "skills" / "core" / "brainstorming" / "SKILL.md").write_text(
            "new body", encoding="utf-8"
        )
        (home / "skills" / "brainstorming").mkdir()
        (home / "skills" / "brainstorming" / "SKILL.md").write_text("old body", encoding="utf-8")
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == []
        assert drifted == ["skill: brainstorming"]
        assert enriched == []

    def test_skills_under_extensions_are_covered_too(self, tmp_path):
        repo, home = self._trees(tmp_path)
        (repo / "skills" / "extensions" / "research-audit").mkdir(parents=True)
        (repo / "skills" / "extensions" / "research-audit" / "SKILL.md").write_text(
            "a", encoding="utf-8"
        )
        (home / "skills" / "research-audit").mkdir()
        (home / "skills" / "research-audit" / "SKILL.md").write_text("b", encoding="utf-8")
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == []
        assert drifted == ["skill: research-audit"]
        assert enriched == []

    def test_skills_at_a_third_nesting_level_are_still_found(self, tmp_path):
        """The earlier draft used glob("*/*/SKILL.md") -- a fixed two-level
        assumption that is true of every shipped skill on this machine today
        but is a fact about today's layout, not something this function
        should hardcode. rglob has no depth to get wrong."""
        repo, home = self._trees(tmp_path)
        deep = repo / "skills" / "core" / "family" / "nested-skill"
        deep.mkdir(parents=True)
        (deep / "SKILL.md").write_text("new", encoding="utf-8")
        (home / "skills" / "nested-skill").mkdir()
        (home / "skills" / "nested-skill" / "SKILL.md").write_text("old", encoding="utf-8")
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == []
        assert drifted == ["skill: nested-skill"]
        assert enriched == []

    def test_live_only_artifacts_are_never_reported(self, tmp_path):
        """Measured 2026-09-11: 583 live skill .md against 135 shipped. Turning
        this direction on would emit ~450 findings, all correct by construction
        and all useless -- unlike rules/, where the live tree really is roughly
        the shipped tree and this same direction is the loudest signal."""
        repo, home = self._trees(tmp_path)
        for name in ("pareto-leverage-scan", "deletion-test", "capture"):
            (home / "skills" / name).mkdir()
            (home / "skills" / name / "SKILL.md").write_text("x", encoding="utf-8")
        (home / "agents" / "tracy.md").write_text("x", encoding="utf-8")
        assert ldg.find_shipped_artifact_drift(repo, home) == ([], [], [])

    def test_agents_claude_md_is_excluded(self, tmp_path):
        """agents/CLAUDE.md is repo-local authoring guidance that install.sh
        never copies -- the same file sync_doc_counts.py excludes from the
        agent count. Live carries an unrelated file of that name. Also
        proves CLAUDE.md is excluded from every bucket, not just drift."""
        repo, home = self._trees(tmp_path)
        (repo / "agents" / "CLAUDE.md").write_text("how to write agents", encoding="utf-8")
        (home / "agents" / "CLAUDE.md").write_text("something else", encoding="utf-8")
        assert ldg.find_shipped_artifact_drift(repo, home) == ([], [], [])

    def test_line_ending_difference_alone_is_not_drift(self, tmp_path):
        repo, home = self._trees(tmp_path)
        (repo / "agents" / "a.md").write_bytes(b"one\ntwo\n")
        (home / "agents" / "a.md").write_bytes(b"one\r\ntwo\r\n")
        assert ldg.find_shipped_artifact_drift(repo, home) == ([], [], [])

    def test_missing_live_directory_is_silent(self, tmp_path):
        """Distinct from a missing FILE (now reported): a whole live tree
        absent is a minimal install or the clean-CI case, and absence there
        is the ordinary state, not a finding -- same convention as
        find_rules_drift's own directory-level silence."""
        repo = tmp_path / "repo"
        (repo / "agents").mkdir(parents=True)
        (repo / "agents" / "a.md").write_text("x", encoding="utf-8")
        assert ldg.find_shipped_artifact_drift(repo, tmp_path / "nonexistent") == ([], [], [])

    def test_same_path_trees_are_skipped(self, tmp_path):
        """A --link install pointing at this repo can never drift."""
        repo = tmp_path / "repo"
        (repo / "agents").mkdir(parents=True)
        (repo / "agents" / "a.md").write_text("x", encoding="utf-8")
        assert ldg.find_shipped_artifact_drift(repo, repo) == ([], [], [])

    def test_skill_differing_only_by_triggers_field_is_enriched_not_drifted(self, tmp_path):
        """The behavior the whole `enriched` bucket exists for: a live copy
        that has ONLY gained the documented triggers: field must not read as
        real drift -- that is exactly the 82-of-105 false-alarm shape
        measured on the maintainer's own machine before this bucket existed."""
        repo, home = self._trees(tmp_path)
        (repo / "skills" / "core" / "x").mkdir(parents=True)
        (repo / "skills" / "core" / "x" / "SKILL.md").write_text(
            "---\nname: x\n---\nbody\n", encoding="utf-8"
        )
        (home / "skills" / "x").mkdir()
        (home / "skills" / "x" / "SKILL.md").write_text(
            "---\nname: x\ntriggers: [/x, phrase]\n---\nbody\n", encoding="utf-8"
        )
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == []
        assert drifted == []
        assert enriched == ["skill: x"]

    def test_skill_differing_only_by_stale_bsv_header_is_enriched_not_drifted(self, tmp_path):
        repo, home = self._trees(tmp_path)
        (repo / "skills" / "core" / "x").mkdir(parents=True)
        (repo / "skills" / "core" / "x" / "SKILL.md").write_text(
            "---\nname: x\n---\nbody\n", encoding="utf-8"
        )
        (home / "skills" / "x").mkdir()
        (home / "skills" / "x" / "SKILL.md").write_text(
            "<!-- BSV -- Brief Skill View | search: BSV\n-->\n\n---\nname: x\n---\nbody\n",
            encoding="utf-8",
        )
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == []
        assert drifted == []
        assert enriched == ["skill: x"]

    def test_skill_with_a_real_change_plus_triggers_still_counts_as_drifted(self, tmp_path):
        """A known cause does not launder a genuine one sitting alongside it
        -- the union must still fail the strip-and-compare check."""
        repo, home = self._trees(tmp_path)
        (repo / "skills" / "core" / "x").mkdir(parents=True)
        (repo / "skills" / "core" / "x" / "SKILL.md").write_text(
            "---\nname: x\n---\nnew body\n", encoding="utf-8"
        )
        (home / "skills" / "x").mkdir()
        (home / "skills" / "x" / "SKILL.md").write_text(
            "---\nname: x\ntriggers: [/x]\n---\nold body\n", encoding="utf-8"
        )
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert missing == []
        assert drifted == ["skill: x"]
        assert enriched == []

    def test_enriched_agent_is_possible_too(self, tmp_path):
        """The strip is content-based, not kind-conditioned -- an agent or
        command file matching the same known-cause shape is handled
        identically. No agent currently has a triggers: line in practice,
        but the classification should not silently special-case skills."""
        repo, home = self._trees(tmp_path)
        (repo / "agents" / "x.md").write_text("---\nname: x\n---\nbody\n", encoding="utf-8")
        (home / "agents" / "x.md").write_text(
            "---\nname: x\ntriggers: [/x]\n---\nbody\n", encoding="utf-8"
        )
        missing, drifted, enriched = ldg.find_shipped_artifact_drift(repo, home)
        assert drifted == []
        assert enriched == ["agent: x.md"]


class TestMainShippedArtifactHalf:
    def _make_repo(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "hooks").mkdir(parents=True)
        (repo / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo / "skills").mkdir()
        (repo / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        return repo

    def test_warns_and_names_the_kind(self, tmp_path, monkeypatch, capsys):
        repo = self._make_repo(tmp_path)
        (repo / "agents").mkdir()
        (repo / "agents" / "reviewer.md").write_text("new", encoding="utf-8")
        home = tmp_path / "home"
        (home / "hooks").mkdir(parents=True)
        (home / "agents").mkdir()
        (home / "agents" / "reviewer.md").write_text("old", encoding="utf-8")
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_HOME", str(home))
        ldg.main()
        out = capsys.readouterr().out
        assert "shipped artifact(s) differ in content" in out
        assert "agent: reviewer.md" in out

    def test_silent_when_shipped_artifacts_match(self, tmp_path, monkeypatch, capsys):
        repo = self._make_repo(tmp_path)
        (repo / "agents").mkdir()
        (repo / "agents" / "reviewer.md").write_text("same", encoding="utf-8")
        home = tmp_path / "home"
        (home / "hooks").mkdir(parents=True)
        (home / "agents").mkdir()
        (home / "agents" / "reviewer.md").write_text("same", encoding="utf-8")
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_HOME", str(home))
        ldg.main()
        assert capsys.readouterr().out == ""

    def test_warns_separately_on_shipped_artifact_missing_from_live(
        self, tmp_path, monkeypatch, capsys
    ):
        """The #425 shape end-to-end through main(): a shipped command with
        no live counterpart at all. Reported as its own block, distinct from
        content drift -- the two are different findings with different
        remedies (redeploy vs. fix install.sh's source mapping)."""
        repo = self._make_repo(tmp_path)
        (repo / "commands").mkdir()
        (repo / "commands" / "release-scout.md").write_text("x", encoding="utf-8")
        home = tmp_path / "home"
        (home / "hooks").mkdir(parents=True)
        (home / "commands").mkdir()
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_HOME", str(home))
        ldg.main()
        out = capsys.readouterr().out
        assert "NOT installed live" in out
        assert "command: release-scout.md" in out
        assert "differ in content" not in out

    def test_enriched_finding_prints_separately_from_real_drift(
        self, tmp_path, monkeypatch, capsys
    ):
        """The point of the whole `enriched` bucket, exercised end-to-end:
        a skill whose only difference is the documented triggers: field
        must print in its own, quieter block -- never inside the "differ in
        content" block real drift uses, and never silently (that would
        recreate the exact "warning nobody reads" problem for a DIFFERENT
        reason -- suppressing it instead of separating it)."""
        repo = self._make_repo(tmp_path)
        (repo / "skills" / "core" / "x").mkdir(parents=True)
        (repo / "skills" / "core" / "x" / "SKILL.md").write_text(
            "---\nname: x\n---\nbody\n", encoding="utf-8"
        )
        home = tmp_path / "home"
        (home / "hooks").mkdir(parents=True)
        (home / "skills" / "x").mkdir(parents=True)
        (home / "skills" / "x" / "SKILL.md").write_text(
            "---\nname: x\ntriggers: [/x]\n---\nbody\n", encoding="utf-8"
        )
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_HOME", str(home))
        ldg.main()
        out = capsys.readouterr().out
        assert "not a real change" in out
        assert "skill: x" in out
        assert "differ in content" not in out
