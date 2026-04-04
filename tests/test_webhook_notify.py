"""Unit tests for hooks/webhook_notify.py — SSRF protection and secret redaction.

WHY: webhook_notify sends data to external URLs. SSRF and secret leakage
are critical security risks that must be deterministically tested.
"""

import io
import json
from unittest.mock import patch

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
