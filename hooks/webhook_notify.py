#!/usr/bin/env python3
"""Stop/PostToolUse hook: send webhook notifications on session events.

WHY: Team visibility — Slack/Telegram notifications on commits,
session end, and critical events without manual intervention.
"""

import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from utils import extract_tool_response, parse_stdin, sanitize_text

WEBHOOK_CONFIG = Path.home() / ".claude" / "cache" / "webhook_config.json"


def validate_webhook_url(url: str) -> bool:
    """Reject internal/dangerous URLs to prevent SSRF.

    WHY: urlopen with file:// reads local files. Internal IPs enable SSRF
    against cloud metadata (169.254.169.254) or localhost services.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # WHY: block known internal/loopback hostnames
        blocked = ("localhost", "127.0.0.1", "::1", "0.0.0.0", "169.254.169.254")
        if hostname in blocked:
            return False
        # WHY: block private IP ranges (10.x, 172.16-31.x, 192.168.x)
        import ipaddress

        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            pass  # WHY: hostname, not IP — already checked against blocked list
        return True
    except Exception:
        return False


def get_webhook_url() -> str | None:
    """Return webhook URL from env var or config file, None if not configured.

    WHY: Env var takes priority so CI/CD can override without touching disk.
    Config file is the fallback for local developer machines.
    """
    url = os.environ.get("CLAUDE_WEBHOOK_URL")
    if not url:
        if WEBHOOK_CONFIG.exists():
            try:
                config = json.loads(WEBHOOK_CONFIG.read_text(encoding="utf-8"))
                url = config.get("url")
            except (json.JSONDecodeError, OSError):
                pass
    # WHY: validate URL before returning to prevent SSRF
    if url and validate_webhook_url(url):
        return url
    return None


def send_webhook(url: str, payload: dict) -> None:
    """POST payload to url with a 5-second timeout; all errors are swallowed.

    WHY: This hook must never block or crash Claude Code. Fire-and-forget
    semantics mean we accept the possibility of dropped notifications over
    the risk of interrupting the user's workflow.
    """
    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        urlopen(req, timeout=5)
    except Exception:
        pass


# WHY: redact potential secrets from summary before sending externally.
# Covers: key=value, key:value, Bearer tokens, JSON "key":"value" formats.
_SECRET_PATTERN = re.compile(
    r"(?i)"
    r"(?:(?:password|secret|token|key|api_key|apikey|credential|authorization)"
    r"\s*[=:]\s*\S+)"
    r"|(?:Bearer\s+[A-Za-z0-9\-._~+/]+=*)"
    r"|(?:\"(?:password|secret|token|key|api_key|credential)\"\s*:\s*\"[^\"]+\")"
    r"|(?:ghp_[A-Za-z0-9_]+)"
    r"|(?:sk-[A-Za-z0-9_]+)"
    r"|(?:AKIA[A-Z0-9]{16})"
    r"|(?:eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+)",
)


def build_payload(event: str, timestamp: str, summary: str) -> dict:
    """Construct the JSON body sent to the webhook endpoint.

    WHY: Both Slack incoming-webhook and Telegram bot webhook accept
    a `text` key at the top level, so a single format satisfies both.
    """
    # WHY: redact secrets before sending to external webhook
    redacted = _SECRET_PATTERN.sub(r"\1=[REDACTED]", summary)
    return {
        "text": f"[Claude Code] {event} at {timestamp}\n{redacted}",
    }


def main() -> None:
    """Entry point: read stdin, resolve webhook URL, fire notification."""
    url = get_webhook_url()
    if not url:
        # WHY: No webhook configured is a normal state (most users won't set
        # one). Exit silently rather than printing noise to stderr.
        sys.exit(0)

    data = parse_stdin()

    # WHY: hook_event is the canonical field name in Claude Code hook protocol.
    # Falling back to "event" covers older/custom payloads gracefully.
    event = data.get("hook_event", data.get("event", "unknown"))

    timestamp = datetime.now(UTC).isoformat()

    # WHY: extract_tool_response handles nested dict, plain string, and
    # missing key — preferred over raw data.get() for robustness.
    raw_summary = extract_tool_response(data) or data.get("message", "Session event")
    summary = sanitize_text(str(raw_summary), max_len=500)

    payload = build_payload(event, timestamp, summary)
    send_webhook(url, payload)


if __name__ == "__main__":
    main()
