r"""Unit tests for hooks/file_auto_parser.py — credential-disclosure gate.

WHY: this UserPromptSubmit hook auto-parses ANY supported-extension file
merely NAMED in chat text -- no tool call, no relation to
permission_policy.py's PreToolUse gate. Confirmed live, 2026-09-12: mentioning
`~/.claude/.credentials.json` and `~/.claude.json` caused both to be fully
parsed and cached in plaintext, and the resulting cache file was then
RE-INGESTED under a third name when its own path was later quoted back into
chat. See file_auto_parser.py's own WHY comment above `_CONFIG_EXACT_FILES`
for the full incident, the skeptic + sec-auditor design review that shaped
this fix (DDD Trigger 3, per doubt-driven-development.md), and the follow-up
sec-auditor pass that found a real Windows extended-length-prefix (`\\?\`)
and UNC-path bypass in the first implementation, fixed by switching from a
drive-rooted `is_relative_to()` check to a path-component check.
"""

import io
import json
import os

import doc_registry
import file_auto_parser
import pytest
from file_auto_parser import _is_sensitive_path, main
from permission_policy import SENSITIVE_PATH_PATTERNS

pytestmark = pytest.mark.security


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Isolate every home-relative constant this test touches under
    tmp_path, so tests never depend on (or pollute) the real ~/.claude —
    including doc_registry's own REGISTRY_PATH, which is a separate
    module-level constant computed from the real Path.home() and would
    otherwise write to the real registry file during these tests."""
    home = tmp_path / "home"
    (home / ".claude" / "cache" / "parsed").mkdir(parents=True)

    # WHY no _CONFIG_ROOTS patch (removed from file_auto_parser.py itself,
    # see its own WHY comment): the location gate is now a path-COMPONENT
    # check (_CONFIG_SEGMENTS = {".claude", ".ssh", ".aws"}), which matches
    # on the literal directory name wherever it appears, home or not -- no
    # home-relative constant to isolate for it.
    monkeypatch.setattr(file_auto_parser, "_HOME", home)
    monkeypatch.setattr(file_auto_parser, "_CONFIG_EXACT_FILES", (home / ".claude.json",))
    monkeypatch.setattr(file_auto_parser, "CACHE_DIR", home / ".claude" / "cache" / "parsed")

    registry_path = home / ".claude" / "cache" / "doc_registry.json"
    monkeypatch.setattr(doc_registry, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(doc_registry, "_LOCK_PATH", registry_path.with_suffix(".lock"))

    return home


# === _is_sensitive_path() — location gate ===
# WHY these tests exist: the location gate is the primary defense (skeptic +
# sec-auditor review falsified a name-only denylist against this exact
# incident — see file_auto_parser.py's WHY comment). It must catch both
# real leaked files AND the self-ingestion case, independent of filename.


class TestIsSensitivePathLocation:
    def test_credentials_json_under_claude_dir_denied(self, fake_home):
        p = fake_home / ".claude" / ".credentials.json"
        p.write_text("{}", encoding="utf-8")
        assert _is_sensitive_path(str(p), SENSITIVE_PATH_PATTERNS)

    def test_bare_claude_json_sibling_file_denied(self, fake_home):
        # This is the file the location gate specifically exists for: NOT
        # inside .claude/, so the root check alone would miss it -- it
        # needs the separate exact-file check (_CONFIG_EXACT_FILES).
        p = fake_home / ".claude.json"
        p.write_text("{}", encoding="utf-8")
        assert _is_sensitive_path(str(p), SENSITIVE_PATH_PATTERNS)

    def test_own_cache_file_denied_even_though_name_matches_nothing(self, fake_home):
        # Regression guard for the live-reproduced self-ingestion bug: a
        # cache file's generated name (`.claude-<hash>.json`, from
        # Path.stem) contains none of SENSITIVE_PATH_PATTERNS's
        # substrings -- only the location check can catch it.
        cache_file = fake_home / ".claude" / "cache" / "parsed" / ".claude-abc123def456.json"
        cache_file.write_text("{}", encoding="utf-8")
        scan = str(cache_file).replace("\\", "/").lower()
        assert not any(pattern in scan for pattern in SENSITIVE_PATH_PATTERNS), (
            "test setup invalid: cache filename accidentally matches a name pattern, "
            "so this test would not actually exercise the location-only path"
        )
        assert _is_sensitive_path(str(cache_file), SENSITIVE_PATH_PATTERNS)

    def test_settings_local_json_under_claude_dir_denied(self, fake_home):
        p = fake_home / ".claude" / "settings.local.json"
        p.write_text("{}", encoding="utf-8")
        assert _is_sensitive_path(str(p), SENSITIVE_PATH_PATTERNS)

    def test_ssh_dir_file_denied(self, fake_home):
        (fake_home / ".ssh").mkdir()
        p = fake_home / ".ssh" / "export.json"
        p.write_text("{}", encoding="utf-8")
        assert _is_sensitive_path(str(p), SENSITIVE_PATH_PATTERNS)

    def test_unrelated_file_outside_config_roots_allowed(self, fake_home):
        p = fake_home / "research.csv"
        p.write_text("a,b\n1,2\n", encoding="utf-8")
        assert not _is_sensitive_path(str(p), SENSITIVE_PATH_PATTERNS)

    # WHY skipif here, user-confirmed (2026-09-12, same repo precedent as
    # tests/test_secure_append_env_file.py:53,61): pathlib parses backslash-
    # delimited paths only on Windows -- PosixPath treats `\\?\C:\...` as one
    # opaque filename, so this is genuinely platform-specific behavior, not
    # a test being weakened to dodge a real failure. CI runs ubuntu-latest.
    @pytest.mark.skipif(os.name != "nt", reason="Windows extended-length prefix is Windows-only")
    def test_win_extended_length_prefix_denied(self, fake_home):
        # Sec-auditor-found, live-verified 2026-09-12 against a real existing
        # cache file on this machine: a first cut of this fix used a drive-
        # rooted is_relative_to(root) check, which Path.resolve() does NOT
        # canonicalize a `\\?\`-prefix against -- `\\?\C:\...` resolves to
        # itself, so the old check returned sensitive=False for the exact
        # same file it was written to catch. The component-based check
        # fixes this because pathlib still segments the prefixed path on
        # its own backslashes.
        cache_file = fake_home / ".claude" / "cache" / "parsed" / ".claude-abc123def456.json"
        cache_file.write_text("{}", encoding="utf-8")
        prefixed = "\\\\?\\" + str(cache_file)
        assert _is_sensitive_path(prefixed, SENSITIVE_PATH_PATTERNS)

    @pytest.mark.skipif(os.name != "nt", reason="UNC admin-share form is Windows-only")
    def test_unc_admin_share_form_denied(self, fake_home):
        # Same finding as test_win_extended_length_prefix_denied, second
        # reproduction: a UNC admin-share path (`\\host\C$\...`) also never
        # matches a drive-rooted is_relative_to(root) check.
        cache_file = fake_home / ".claude" / "cache" / "parsed" / ".claude-abc123def456.json"
        cache_file.write_text("{}", encoding="utf-8")
        drive = str(cache_file)[:2]  # e.g. "C:"
        unc = str(cache_file).replace(drive, "\\\\localhost\\" + drive[0] + "$", 1)
        assert _is_sensitive_path(unc, SENSITIVE_PATH_PATTERNS)


# === _is_sensitive_path() — name-pattern gate ===
# WHY: catches a similarly-sensitive file OUTSIDE the config roots (a
# project's own .mcp.json, a credentials export in Downloads) that the
# location gate alone cannot see.


class TestIsSensitivePathNamePatterns:
    def test_project_mcp_json_denied(self, tmp_path, fake_home):
        project = tmp_path / "project"
        project.mkdir()
        p = project / ".mcp.json"
        p.write_text("{}", encoding="utf-8")
        assert _is_sensitive_path(str(p), SENSITIVE_PATH_PATTERNS)

    def test_exported_config_copy_denied(self, tmp_path, fake_home):
        # WHY named without any SENSITIVE_PATH_PATTERNS substring in the
        # test's OWN name (sec-auditor-found, 2026-09-12, and re-found by
        # this test's own setup-validity assertion below after a first
        # rename attempt traded "credentials" for "secret" -- still a
        # match): pytest's default tmp_path is derived from the test's
        # nodeid, so a test name containing ANY sensitive substring gets a
        # tmp_path whose own directory already matches it, and the
        # assertion below would pass even with the actual filename check
        # removed. Verified the fix: assert the setup itself is clean first.
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        p = downloads / "credentials.json"
        p.write_text("{}", encoding="utf-8")
        parent_scan = str(downloads).replace("\\", "/").lower()
        assert not any(pattern in parent_scan for pattern in SENSITIVE_PATH_PATTERNS), (
            "test setup invalid: tmp_path/parent dir accidentally matches a name "
            "pattern, so this test would not actually exercise the filename check"
        )
        assert _is_sensitive_path(str(p), SENSITIVE_PATH_PATTERNS)

    def test_windows_backslash_path_normalized(self, tmp_path, fake_home):
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        p = downloads / "credentials.json"
        p.write_text("{}", encoding="utf-8")
        windows_style = str(p).replace("/", "\\")
        assert _is_sensitive_path(windows_style, SENSITIVE_PATH_PATTERNS)

    def test_ordinary_research_filename_not_denied(self, tmp_path, fake_home):
        # Regression guard: SENSITIVE_PATH_PATTERNS deliberately excludes
        # bare "auth" (permission_policy.py, verified by reading it) --
        # exactly so a real filename like this one is not blocked.
        p = tmp_path / "buckholtz_32_starting_reading_EN.xlsx"
        p.write_text("x", encoding="utf-8")
        assert not _is_sensitive_path(str(p), SENSITIVE_PATH_PATTERNS)


# === main() — end-to-end incident repro ===
# WHY: unit-testing _is_sensitive_path() proves the predicate is correct;
# these tests prove main() actually WIRES it in before any parse/cache/
# register call happens -- the thing that was missing during the incident.


class TestMainSkipsSensitivePaths:
    def _run_main(self, monkeypatch, capsys, prompt: str):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"prompt": prompt})))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        return capsys.readouterr()

    def test_credentials_json_not_parsed_or_cached(self, fake_home, monkeypatch, capsys):
        secret_file = fake_home / ".claude" / ".credentials.json"
        secret_file.write_text(
            '{"claudeAiOauth": {"accessToken": "CANARY-SHOULD-NEVER-BE-CACHED"}}',
            encoding="utf-8",
        )

        out = self._run_main(monkeypatch, capsys, f'please look at "{secret_file}"')

        cache_dir = fake_home / ".claude" / "cache" / "parsed"
        cached_files = list(cache_dir.glob("*.json"))
        assert cached_files == [], f"credential file was cached: {cached_files}"
        assert "CANARY-SHOULD-NEVER-BE-CACHED" not in out.out
        assert "CANARY-SHOULD-NEVER-BE-CACHED" not in out.err
        assert out.out == "", "no additionalContext should be emitted for an all-sensitive prompt"
        assert "Skipped 1" in out.err
        assert not doc_registry.REGISTRY_PATH.exists(), (
            "sensitive file must never reach the registry"
        )

    def test_bare_claude_json_not_parsed_or_cached(self, fake_home, monkeypatch, capsys):
        # The file the fix specifically exists for -- see
        # TestIsSensitivePathLocation.test_bare_claude_json_sibling_file_denied.
        secret_file = fake_home / ".claude.json"
        secret_file.write_text(
            '{"mcpServers": {"x": {"env": {"KEY": "CANARY-SHOULD-NOT-LEAK"}}}}',
            encoding="utf-8",
        )

        out = self._run_main(monkeypatch, capsys, f'please look at "{secret_file}"')

        cache_dir = fake_home / ".claude" / "cache" / "parsed"
        assert list(cache_dir.glob("*.json")) == []
        assert "CANARY-SHOULD-NOT-LEAK" not in out.out

    def test_own_cache_file_not_reingested(self, fake_home, monkeypatch, capsys):
        # Regression guard for the live-reproduced self-ingestion bug: a
        # PRE-EXISTING cache file (as if a prior, unfixed run had already
        # cached a secret) must not be re-parsed into a second copy just
        # because its own path gets mentioned later.
        cache_dir = fake_home / ".claude" / "cache" / "parsed"
        pre_existing_cache = cache_dir / ".claude-abc123def456.json"
        pre_existing_cache.write_text(
            '{"_format": "json", "data": {"CANARY": "SHOULD-NOT-BE-COPIED-AGAIN"}}',
            encoding="utf-8",
        )

        out = self._run_main(monkeypatch, capsys, f'the cache is at "{pre_existing_cache}"')

        cached_files = sorted(p.name for p in cache_dir.glob("*.json"))
        assert cached_files == [
            ".claude-abc123def456.json"
        ], f"a second cache copy was created: {cached_files}"
        assert "SHOULD-NOT-BE-COPIED-AGAIN" not in out.out

    def test_ordinary_file_still_parsed_and_cached(self, fake_home, monkeypatch, capsys, tmp_path):
        # Regression guard: the fix must not break the hook's actual job.
        data_file = tmp_path / "results.csv"
        data_file.write_text("a,b\n1,2\n", encoding="utf-8")

        out = self._run_main(monkeypatch, capsys, f'please look at "{data_file}"')

        cache_dir = fake_home / ".claude" / "cache" / "parsed"
        cached_files = list(cache_dir.glob("*.json"))
        assert len(cached_files) == 1
        payload = json.loads(out.out)
        context = payload["hookSpecificOutput"]["additionalContext"]
        assert "Parsed 1 new file" in context
        assert doc_registry.REGISTRY_PATH.exists()

    def test_mixed_prompt_parses_ordinary_and_skips_sensitive(
        self, fake_home, monkeypatch, capsys, tmp_path
    ):
        secret_file = fake_home / ".claude" / ".credentials.json"
        secret_file.write_text('{"secret": "CANARY-MIXED"}', encoding="utf-8")
        data_file = tmp_path / "results.csv"
        data_file.write_text("a,b\n1,2\n", encoding="utf-8")

        out = self._run_main(
            monkeypatch,
            capsys,
            f'compare "{secret_file}" against "{data_file}"',
        )

        cache_dir = fake_home / ".claude" / "cache" / "parsed"
        cached_files = list(cache_dir.glob("*.json"))
        assert len(cached_files) == 1, f"expected only the ordinary file cached: {cached_files}"
        assert "CANARY-MIXED" not in out.out
        assert "Skipped 1" in out.err
        payload = json.loads(out.out)
        assert "Parsed 1 new file" in payload["hookSpecificOutput"]["additionalContext"]
