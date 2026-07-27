#!/usr/bin/env python3
"""Stop hook: send webhook notifications on session events.

WHY: Team visibility — Slack/Telegram notifications on commits,
session end, and critical events without manual intervention.

Scope note (P0.4, follow-up audit 2026-07-13): an earlier version of this
docstring also claimed "PostToolUse hook", but it was only ever registered
under Stop in hooks/settings.json, and the code has no event-specific
branching that depended on it. Not adding PostToolUse now: with this hook's
declared matcher="*" (fires on every tool call) and its real Slack/Telegram
network side effect, wiring it up requires a deliberate decision about
notification volume, not a silent registration fix.
"""

import ipaddress
import json
import os
import re
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from utils import extract_tool_response, parse_stdin, sanitize_text

WEBHOOK_CONFIG = Path.home() / ".claude" / "cache" / "webhook_config.json"

# WHY a short, dedicated timeout (external re-audit 2026-07-07): DNS
# resolution shouldn't be able to hang this hook indefinitely if a
# maliciously-configured webhook URL points at an unresponsive/slow
# nameserver -- 3s is generous for a normal lookup, short enough to never
# meaningfully delay Claude Code's Stop/PostToolUse flow.
_DNS_RESOLVE_TIMEOUT_SECONDS = 3


def _resolve_safe_ip(hostname: str) -> str | None:
    """Resolve `hostname` once; return one safe IP to connect to, or None if
    the hostname is unresolvable or resolves to a private/loopback/link-local
    address.

    WHY (HIGH, external re-audit 2026-07-07): the original validate_webhook_url
    only checked the literal hostname STRING against a blocklist and against
    ipaddress.ip_address() (which only succeeds if the string itself IS an
    IP literal). A DNS name that RESOLVES to a private/metadata IP -- e.g.
    an attacker-controlled domain pointed at 169.254.169.254 -- passed both
    checks: the hostname string is neither literally blocked nor a literal
    IP. Resolving via socket.getaddrinfo and checking every returned address
    closes that gap for the simple (non-rebinding) case: a domain whose DNS
    record points at a private/link-local/loopback address at validation time.

    WHY fail-CLOSED on resolution failure (SEC-02, external security audit
    2026-07-17 -- reverses the prior fail-open behavior): failing open here
    treated "we don't know if this is safe" as "it's safe", which is the
    wrong default for an SSRF check specifically. This is safe to flip
    because send_webhook() already accepts dropped notifications as a normal
    outcome (fire-and-forget, every exception swallowed) -- refusing to
    resolve costs one missed Slack ping, not a broken workflow, unlike
    fail-closed on e.g. input_guard.py where the wrong default would block
    a legitimate tool call outright.

    WHY this returns the IP, not just a bool (SEC-02): the previous version
    only answered "is this hostname safe", then let send_webhook's urlopen()
    re-resolve the SAME hostname again moments later to actually connect --
    two separate DNS lookups with a window in between where an attacker
    controlling DNS (rebinding) could return a public IP for the check and a
    private/metadata IP for the real connection. Returning the specific IP
    that was just validated lets the caller connect to THAT address directly
    (see send_webhook's getaddrinfo pin), so the address that was checked is
    the address that gets connected to -- no second, independent resolution.
    """
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(_DNS_RESOLVE_TIMEOUT_SECONDS)
        infos = socket.getaddrinfo(hostname, None)
    except OSError:
        return None  # couldn't resolve -- fail CLOSED, see docstring above
    finally:
        socket.setdefaulttimeout(old_timeout)

    safe_addrs: list[str] = []
    for info in infos:
        # WHY str(): info[4][0] is typed str | int in the stdlib stubs (a
        # sockaddr tuple's first element covers both AF_INET's str host and
        # other families) -- getaddrinfo always returns a string address
        # here in practice, str() just satisfies the declared -> str | None.
        addr = str(info[4][0])
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            # WHY return immediately, not just skip this one address: a
            # hostname resolving to BOTH a public and a private address must
            # still be blocked entirely -- an attacker only needs ONE
            # resolvable path to a private/metadata endpoint.
            return None
        safe_addrs.append(addr)
    return safe_addrs[0] if safe_addrs else None


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
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
            # WHY: hostname IS a literal IP already checked above -- skip DNS
            # resolution entirely, it would just re-resolve the same literal.
            return True
        except ValueError:
            pass  # not a literal IP -- fall through to DNS resolution check
        return _resolve_safe_ip(hostname) is not None
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


class _ValidatingRedirectHandler(HTTPRedirectHandler):
    """Re-validate every redirect Location against validate_webhook_url(),
    and pin the redirect target's resolved IP the same way the initial
    request is pinned (see send_webhook), closing the same DNS-rebinding
    TOCTOU window for redirect hops.

    WHY (F-07, external audit 2026-07-15): the initial URL is SSRF-checked by
    get_webhook_url(), but plain urlopen() follows 3xx redirects automatically
    without re-checking the new target. A validated public webhook endpoint
    that later responds with a redirect to an internal/private URL (attacker
    controls the endpoint, or it's compromised) would previously be followed
    silently -- the exact SSRF gap validate_webhook_url() exists to close,
    just one hop later. Returning None from redirect_request() tells urllib
    to NOT follow the redirect (stdlib returns the original 3xx response
    instead of raising), which the caller's blanket except already swallows.
    """

    def __init__(self, pins: dict[str, str]) -> None:
        super().__init__()
        self._pins = pins

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not validate_webhook_url(newurl):
            return None
        new_host = urlparse(newurl).hostname
        if new_host:
            pinned_ip = _resolve_safe_ip(new_host)
            if pinned_ip is None:
                return None
            self._pins[new_host] = pinned_ip
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def send_webhook(url: str, payload: dict) -> None:
    """POST payload to url with a 5-second timeout; all errors are swallowed.

    WHY: This hook must never block or crash Claude Code. Fire-and-forget
    semantics mean we accept the possibility of dropped notifications over
    the risk of interrupting the user's workflow.

    WHY the getaddrinfo pin (SEC-02, external security audit 2026-07-17):
    get_webhook_url() already SSRF-validated this hostname earlier, but
    urlopen() would otherwise re-resolve the SAME hostname independently at
    connect time -- a DNS-rebinding attacker could return a safe IP for that
    earlier check and a private/metadata IP for this actual connection.
    Resolving once, right here, and forcing socket.getaddrinfo to return
    exactly that validated address for the duration of this one call closes
    the window: the address that gets connected to is the address that was
    just checked, with no re-resolution in between. The monkeypatch is
    process-global but scoped tightly by try/finally and restored before
    this function returns -- safe here because this script's only job is to
    send one webhook POST and exit, not because global monkeypatching is
    safe in general.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return
        pinned_ip = _resolve_safe_ip(hostname)
        if pinned_ip is None:
            return  # unsafe or unresolvable -- fail closed, drop the notification

        pins = {hostname: pinned_ip}
        real_getaddrinfo = socket.getaddrinfo

        def _pinned_getaddrinfo(host, *args, **kwargs):
            if host in pins:
                return real_getaddrinfo(pins[host], *args, **kwargs)
            return real_getaddrinfo(host, *args, **kwargs)

        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        opener = build_opener(_ValidatingRedirectHandler(pins))
        socket.getaddrinfo = _pinned_getaddrinfo
        try:
            opener.open(req, timeout=5)
        finally:
            socket.getaddrinfo = real_getaddrinfo
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
    # WHY: redact secrets before sending to external webhook.
    # Using "[REDACTED]" as full replacement (not \1) because all pattern
    # alternations are non-capturing (?:...) — \1 would raise PatternError.
    redacted = _SECRET_PATTERN.sub("[REDACTED]", summary)
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
