"""Unit tests for hooks/webhook_notify.py — SSRF protection and secret redaction.

WHY: webhook_notify sends data to external URLs. SSRF and secret leakage
are critical security risks that must be deterministically tested.
"""

import io
import json
from unittest.mock import Mock, patch

from webhook_notify import build_payload, get_webhook_url, main, validate_webhook_url

# === validate_webhook_url ===


class TestValidateWebhookUrl:
    def test_https_external_valid(self):
        assert validate_webhook_url("https://hooks.slack.com/T00/B00/xxx") is True

    def test_http_external_valid(self):
        assert validate_webhook_url("http://example.com/hook") is True

    def test_file_scheme_blocked(self):
        assert validate_webhook_url("file:///etc/passwd") is False

    def test_ftp_scheme_blocked(self):
        assert validate_webhook_url("ftp://example.com/hook") is False

    def test_localhost_blocked(self):
        assert validate_webhook_url("https://localhost/hook") is False

    def test_127_0_0_1_blocked(self):
        assert validate_webhook_url("https://127.0.0.1/hook") is False

    def test_cloud_metadata_blocked(self):
        # WHY: 169.254.169.254 is AWS/GCP/Azure metadata endpoint
        assert validate_webhook_url("http://169.254.169.254/latest/meta-data/") is False

    def test_private_ip_10_blocked(self):
        assert validate_webhook_url("https://10.0.0.1/webhook") is False

    def test_private_ip_192_168_blocked(self):
        assert validate_webhook_url("https://192.168.1.100/webhook") is False

    def test_private_ip_172_16_blocked(self):
        assert validate_webhook_url("https://172.16.0.1/webhook") is False

    def test_no_hostname_blocked(self):
        assert validate_webhook_url("https:///path") is False

    def test_empty_string_blocked(self):
        assert validate_webhook_url("") is False

    def test_malformed_url_blocked(self):
        assert validate_webhook_url("not-a-url") is False

    def test_telegram_bot_valid(self):
        assert validate_webhook_url("https://api.telegram.org/bot123/sendMessage") is True


# === DNS-resolution SSRF check (_resolves_to_blocked_ip) ===
#
# WHY (HIGH, external re-audit 2026-07-07): the original validate_webhook_url
# only checked the literal hostname STRING -- a DNS name that RESOLVES to a
# private/metadata IP (e.g. an attacker-controlled domain pointed at
# 169.254.169.254) passed both the blocklist check and the ip_address()
# literal check, since the hostname string itself is neither. These tests
# mock socket.getaddrinfo for determinism -- no real DNS/network dependency.


def _fake_getaddrinfo(addresses: list[str]):
    """Build a minimal fake socket.getaddrinfo() return value for the given
    IPv4 address strings, matching the real (family, type, proto, canonname,
    sockaddr) tuple shape this code reads info[4][0] from."""

    def _fn(hostname, port, *args, **kwargs):
        return [(2, 1, 6, "", (addr, 0)) for addr in addresses]

    return _fn


class TestDnsResolutionSsrfCheck:
    def test_domain_resolving_to_private_ip_blocked(self, monkeypatch):
        monkeypatch.setattr("webhook_notify.socket.getaddrinfo", _fake_getaddrinfo(["10.0.0.5"]))
        assert validate_webhook_url("https://attacker-controlled.example/hook") is False

    def test_domain_resolving_to_cloud_metadata_ip_blocked(self, monkeypatch):
        monkeypatch.setattr(
            "webhook_notify.socket.getaddrinfo", _fake_getaddrinfo(["169.254.169.254"])
        )
        assert validate_webhook_url("https://attacker-controlled.example/hook") is False

    def test_domain_resolving_to_loopback_blocked(self, monkeypatch):
        monkeypatch.setattr("webhook_notify.socket.getaddrinfo", _fake_getaddrinfo(["127.0.0.1"]))
        assert validate_webhook_url("https://attacker-controlled.example/hook") is False

    def test_domain_resolving_only_to_public_ip_allowed(self, monkeypatch):
        monkeypatch.setattr(
            "webhook_notify.socket.getaddrinfo", _fake_getaddrinfo(["93.184.216.34"])
        )
        assert validate_webhook_url("https://legit-webhook.example/hook") is True

    def test_one_private_address_among_multiple_still_blocks(self, monkeypatch):
        """A hostname resolving to BOTH a public and a private address must
        still be blocked -- an attacker only needs ONE resolvable path to a
        private/metadata endpoint, even if other records look benign."""
        monkeypatch.setattr(
            "webhook_notify.socket.getaddrinfo",
            _fake_getaddrinfo(["93.184.216.34", "10.0.0.5"]),
        )
        assert validate_webhook_url("https://mixed-records.example/hook") is False

    def test_dns_resolution_failure_fails_open(self, monkeypatch):
        """Matches this repo's hook-wide convention: an infra glitch (DNS
        timeout, no network) must never crash the hook or block a legitimate
        webhook -- fall through to the (already-passed) literal-string checks."""

        def _raise(*args, **kwargs):
            raise OSError("simulated DNS resolution failure")

        monkeypatch.setattr("webhook_notify.socket.getaddrinfo", _raise)
        assert validate_webhook_url("https://unresolvable.example/hook") is True

    def test_literal_ip_hostname_skips_dns_resolution_entirely(self, monkeypatch):
        """When the hostname IS already a literal IP, getaddrinfo must not
        even be called -- resolving a literal IP string is redundant, and
        this also confirms the private-IP-literal case is caught by the
        existing ip_address() check, not by falling through to DNS."""
        calls = []
        monkeypatch.setattr(
            "webhook_notify.socket.getaddrinfo",
            lambda *a, **k: calls.append(1) or [],
        )
        assert validate_webhook_url("https://10.0.0.1/webhook") is False
        assert calls == []


# === get_webhook_url ===


class TestGetWebhookUrl:
    def test_env_var_valid_url_returned(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_WEBHOOK_URL", "https://hooks.slack.com/T00/B00/valid")
        url = get_webhook_url()
        assert url == "https://hooks.slack.com/T00/B00/valid"

    def test_invalid_env_url_returns_none(self, monkeypatch):
        # WHY: SSRF — env var pointing to localhost must be rejected
        monkeypatch.setenv("CLAUDE_WEBHOOK_URL", "https://localhost/hook")
        url = get_webhook_url()
        assert url is None

    def test_no_env_no_file_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_WEBHOOK_URL", raising=False)
        with patch("webhook_notify.WEBHOOK_CONFIG", tmp_path / "nonexistent.json"):
            url = get_webhook_url()
        assert url is None

    def test_config_file_fallback(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_WEBHOOK_URL", raising=False)
        config_file = tmp_path / "webhook_config.json"
        config_file.write_text(
            json.dumps({"url": "https://hooks.slack.com/T00/B00/file-url"}),
            encoding="utf-8",
        )
        with patch("webhook_notify.WEBHOOK_CONFIG", config_file):
            url = get_webhook_url()
        assert url == "https://hooks.slack.com/T00/B00/file-url"

    def test_env_takes_priority_over_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_WEBHOOK_URL", "https://hooks.slack.com/T00/B00/env-url")
        config_file = tmp_path / "webhook_config.json"
        config_file.write_text(
            json.dumps({"url": "https://hooks.slack.com/T00/B00/file-url"}),
            encoding="utf-8",
        )
        with patch("webhook_notify.WEBHOOK_CONFIG", config_file):
            url = get_webhook_url()
        assert url == "https://hooks.slack.com/T00/B00/env-url"


# === build_payload ===


class TestBuildPayload:
    def test_basic_structure(self):
        payload = build_payload("Stop", "2026-04-04T10:00:00+00:00", "session ended normally")
        assert "text" in payload

    def test_text_contains_event(self):
        payload = build_payload("Stop", "2026-04-04T10:00:00+00:00", "session ended")
        assert "Stop" in payload["text"]

    def test_text_contains_timestamp(self):
        payload = build_payload("Stop", "2026-04-04T10:00:00+00:00", "session ended")
        assert "2026-04-04" in payload["text"]

    def test_clean_summary_unchanged(self):
        payload = build_payload("Stop", "2026-04-04T10:00:00", "session ended normally")
        assert "session ended normally" in payload["text"]

    def test_api_key_redacted(self):
        summary = "key=sk-abc123xyz completed the task"
        payload = build_payload("Stop", "2026-04-04", summary)
        assert "sk-abc123xyz" not in payload["text"]
        assert "[REDACTED]" in payload["text"]

    def test_bearer_token_redacted(self):
        summary = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
        payload = build_payload("Stop", "2026-04-04", summary)
        assert "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" not in payload["text"]

    def test_github_token_redacted(self):
        summary = "token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456 used for auth"
        payload = build_payload("Stop", "2026-04-04", summary)
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456" not in payload["text"]

    def test_openai_key_redacted(self):
        summary = "api_key=sk-proj-abcdefghijklmnopqrstuvwxyz"
        payload = build_payload("Stop", "2026-04-04", summary)
        assert "sk-proj-abcdefghijklmnopqrstuvwxyz" not in payload["text"]


# === main() ===


class TestMain:
    def _run_main(self, monkeypatch, data: dict, webhook_url: str | None = None) -> str:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        buf = io.StringIO()
        with (
            patch("webhook_notify.get_webhook_url", return_value=webhook_url),
            patch("sys.stdout", buf),
        ):
            try:
                main()
            except SystemExit:
                pass
        return buf.getvalue()

    def test_no_webhook_configured_exits_silently(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"hook_event": "Stop"})))
        with patch("webhook_notify.get_webhook_url", return_value=None):
            try:
                main()
            except SystemExit:
                pass
        assert capsys.readouterr().out == ""

    def test_with_webhook_calls_send(self, monkeypatch):
        data = {"hook_event": "Stop", "message": "session ended"}
        with (
            patch("webhook_notify.get_webhook_url", return_value="https://hooks.slack.com/T/B/x"),
            patch("webhook_notify.send_webhook") as mock_send,
            patch("sys.stdin", io.StringIO(json.dumps(data))),
        ):
            try:
                main()
            except SystemExit:
                pass
        mock_send.assert_called_once()
        _, payload = mock_send.call_args[0]
        assert "text" in payload

    def test_event_field_extracted(self, monkeypatch):
        data = {"hook_event": "SessionEnd", "message": "done"}
        captured_payload = {}
        with (
            patch("webhook_notify.get_webhook_url", return_value="https://hooks.slack.com/T/B/x"),
            patch(
                "webhook_notify.send_webhook", side_effect=lambda url, p: captured_payload.update(p)
            ),
            patch("sys.stdin", io.StringIO(json.dumps(data))),
        ):
            try:
                main()
            except SystemExit:
                pass
        assert "SessionEnd" in captured_payload.get("text", "")


class TestValidatingRedirectHandler:
    """F-07 (external audit 2026-07-15): a validated webhook endpoint that
    later redirects to an internal/private URL must not be followed blindly.
    """

    def test_blocks_redirect_to_cloud_metadata(self):
        from webhook_notify import _ValidatingRedirectHandler

        handler = _ValidatingRedirectHandler()
        result = handler.redirect_request(
            Mock(), Mock(), 302, "Found", {}, "http://169.254.169.254/latest/meta-data/"
        )
        assert result is None

    def test_blocks_redirect_to_localhost(self):
        from webhook_notify import _ValidatingRedirectHandler

        handler = _ValidatingRedirectHandler()
        result = handler.redirect_request(
            Mock(), Mock(), 302, "Found", {}, "http://localhost:8080/internal"
        )
        assert result is None

    def test_allows_redirect_to_revalidated_public_url(self, monkeypatch):
        from webhook_notify import _ValidatingRedirectHandler

        monkeypatch.setattr("webhook_notify.validate_webhook_url", lambda u: True)
        sentinel = object()
        with patch("urllib.request.HTTPRedirectHandler.redirect_request", return_value=sentinel):
            handler = _ValidatingRedirectHandler()
            result = handler.redirect_request(
                Mock(), Mock(), 302, "Found", {}, "https://hooks.slack.com/services/new"
            )
        assert result is sentinel

    def test_send_webhook_builds_opener_with_validating_handler(self):
        from webhook_notify import _ValidatingRedirectHandler, send_webhook

        with patch("webhook_notify.build_opener") as mock_build_opener:
            send_webhook("https://hooks.slack.com/T/B/x", {"text": "hi"})
        mock_build_opener.assert_called_once_with(_ValidatingRedirectHandler)
