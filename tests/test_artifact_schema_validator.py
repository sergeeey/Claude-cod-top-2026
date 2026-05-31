"""
tests/test_artifact_schema_validator.py

3 cases for artifact_schema_validator._validate():
  1. Valid JSON in watched dir  → no stderr output
  2. Invalid JSON in watched dir → stderr warning
  3. Valid JSON outside watched dirs → no warning (ignored)
"""

import importlib.util
import io
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Load module without executing __main__ ───────────────────────────────────
# WHY: hook lives in the user's global config (~/.claude/hooks/), NOT in the repo.
# On CI runners (Linux, no ~/.claude/hooks/) we skip the whole module — the hook
# is global infrastructure, not project code. Local devs with the hook installed
# still get full coverage.
HOOK_PATH = Path.home() / ".claude" / "hooks" / "artifact_schema_validator.py"
if not HOOK_PATH.exists():
    pytest.skip(
        f"Global hook not installed at {HOOK_PATH} — skipping (CI / fresh install)",
        allow_module_level=True,
    )

spec = importlib.util.spec_from_file_location("artifact_schema_validator", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
# Patch stdin so the module-level guard doesn't consume it during import
with patch("sys.stdin", io.StringIO("")):
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

_validate = mod._validate


# ── Helper ────────────────────────────────────────────────────────────────────
def capture_stderr(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    with patch("sys.stderr", buf):
        fn(*args, **kwargs)
    return buf.getvalue()


# ── Tests ─────────────────────────────────────────────────────────────────────
class TestArtifactSchemaValidator:
    def test_valid_json_in_watched_dir_no_warning(self) -> None:
        """Case 1: valid JSON in experiments/ → silence."""
        stderr = capture_stderr(
            _validate,
            "experiments/20260531-foo/metrics/run.json",
            '{"auc": 0.92, "n": 100}',
        )
        assert stderr == "", f"Expected no warning, got: {stderr}"

    def test_invalid_json_in_watched_dir_emits_warning(self) -> None:
        """Case 2: malformed JSON in metrics/ → stderr warning."""
        stderr = capture_stderr(
            _validate,
            "metrics/run.json",
            '{"auc": 0.92, broken}',
        )
        assert "WARN" in stderr, "Expected WARN on invalid JSON"
        assert "artifact_schema_validator" in stderr

    def test_valid_json_outside_watched_dirs_ignored(self) -> None:
        """Case 3: valid JSON in an unrelated directory → no warning."""
        stderr = capture_stderr(
            _validate,
            "src/config/app.json",
            '{"debug": true}',
        )
        assert stderr == "", f"Expected no warning for unwatched dir, got: {stderr}"
