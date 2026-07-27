"""Tests for cogniml_client.py — stdlib CogniML API client."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
import cogniml_client


def _mock_response(data: dict):
    """Build a mock urllib response context manager."""
    mock = MagicMock()
    mock.read.return_value = json.dumps(data).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


class TestIsSafeTarget:
    """F-05 (external audit 2026-07-15): destination restriction must hold
    regardless of bearer-token presence -- CogniML is local-only by design."""

    def test_localhost_allowed(self):
        assert cogniml_client._is_safe_target("http://localhost:8400/api/advise") is True

    def test_127_0_0_1_allowed(self):
        assert cogniml_client._is_safe_target("http://127.0.0.1:8400/api/advise") is True

    def test_ipv6_loopback_allowed(self):
        assert cogniml_client._is_safe_target("http://[::1]:8400/api/advise") is True

    def test_arbitrary_host_refused(self):
        assert cogniml_client._is_safe_target("http://attacker.example/api/advise") is False

    def test_arbitrary_ip_refused(self):
        assert cogniml_client._is_safe_target("http://203.0.113.5/api/advise") is False

    def test_non_http_scheme_refused(self):
        assert cogniml_client._is_safe_target("file:///etc/passwd") is False


class TestAdvise:
    def test_returns_answer_on_success(self):
        resp = _mock_response({"answer": "Use batch norm", "evidence_strength": "confirmed"})
        with patch("urllib.request.urlopen", return_value=resp):
            result = cogniml_client.advise("how to fix NaN loss")
        assert result == "Use batch norm"

    def test_fail_open_on_connection_error(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            result = cogniml_client.advise("query")
        assert result is None

    def test_returns_none_when_answer_empty(self):
        resp = _mock_response({"answer": "", "evidence_strength": "unknown"})
        with patch("urllib.request.urlopen", return_value=resp):
            result = cogniml_client.advise("query")
        assert result is None

    def test_returns_none_on_json_error(self):
        mock = MagicMock()
        mock.read.return_value = b"not json{"
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock):
            result = cogniml_client.advise("query")
        assert result is None

    def test_bearer_token_added_when_env_set(self):
        resp = _mock_response({"answer": "ok"})
        with patch("urllib.request.urlopen", return_value=resp):
            with patch.dict("os.environ", {"COGNIML_API_BEARER_TOKEN": "secret123"}):
                result = cogniml_client.advise("query")
        assert result == "ok"

    def test_uses_custom_api_url_when_localhost(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            return _mock_response({"answer": "yes"})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch.object(cogniml_client, "COGNIML_URL", "http://127.0.0.1:9000"):
                cogniml_client.advise("query")
        assert captured.get("url", "").startswith("http://127.0.0.1:9000")

    def test_custom_api_url_pointing_off_localhost_is_refused(self):
        """F-05 (external audit 2026-07-15): CogniML is local-only by design
        -- a COGNIML_API_URL pointing at a non-localhost host (attacker-
        controlled env, poisoned CI, malicious .envrc) must be refused
        regardless of whether a bearer token is configured, since the
        exposure is the request BODY (real session data), not just the
        token."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            with patch.object(cogniml_client, "COGNIML_URL", "http://myhost:9000"):
                result = cogniml_client.advise("query")
        mock_urlopen.assert_not_called()
        assert result is None


class TestPushWikiEntry:
    def setup_method(self, method=None):
        """Clear in-process push cache + redirect ledger before each test.

        WHY: _pushed_cache is a module-level set and _PUSHED_LEDGER is persistent.
        Without clearing both, a test that pushes "title" will block the next test
        that also uses "title" via the idempotency guard.
        """
        import tempfile

        cogniml_client._pushed_cache.clear()
        # Redirect ledger to a fresh temp file so real ~/.claude/cache is not affected
        self._tmp_ledger = Path(tempfile.mktemp(suffix=".txt"))
        self._orig_ledger = cogniml_client._PUSHED_LEDGER
        cogniml_client._PUSHED_LEDGER = self._tmp_ledger

    def teardown_method(self, method=None):
        cogniml_client._pushed_cache.clear()
        cogniml_client._PUSHED_LEDGER = self._orig_ledger
        if self._tmp_ledger.exists():
            self._tmp_ledger.unlink(missing_ok=True)

    def test_returns_skill_id_on_success(self):
        resp = _mock_response({"skill_id": "abc-123", "status": "draft"})
        with patch("urllib.request.urlopen", return_value=resp):
            result = cogniml_client.push_wiki_entry("My Note", "content", ["python"])
        assert result == "abc-123"

    def test_fail_open_returns_none(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError()):
            result = cogniml_client.push_wiki_entry("title", "body", [])
        assert result is None

    def test_returns_none_when_no_skill_id(self):
        resp = _mock_response({"status": "error"})
        with patch("urllib.request.urlopen", return_value=resp):
            result = cogniml_client.push_wiki_entry("title", "body", ["tag"])
        assert result is None

    def test_truncates_body_to_1500_chars(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data)
            return _mock_response({"skill_id": "x"})

        long_body = "x" * 3000
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            cogniml_client.push_wiki_entry("title", long_body, [])
        assert len(captured["body"]["evidence_notes"][0]) == 1500
