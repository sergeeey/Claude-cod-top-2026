"""Regression tests for hooks/utils.py's backward-compatible facade.

WHY (Codex review, PR #328, 2026-09-03): removing lib/security.py's unsafe,
unused send_webhook() also silently dropped it from this facade's __all__ --
breaking the facade's own documented promise that `from utils import X`
keeps working for consumers outside this repo's tree (e.g. a personal hook).
Nothing caught this until an external review flagged it after merge. These
tests close that gap: every declared export must actually resolve, and
send_webhook specifically must be the real, hardened webhook_notify
implementation, not a stale duplicate.

WHY test_facade_send_webhook_honors_the_old_call_contract (Codex review,
PR #329, 2026-09-03): object identity alone isn't enough -- the deleted
lib/security.send_webhook(url, payload, timeout=5) -> bool contract must
still work through the facade, not just resolve without ImportError. A
caller passing timeout= or branching on the return value is exactly the
"unchanged call site" this facade promises.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import utils
import webhook_notify


def test_every_declared_export_resolves() -> None:
    """Every name in __all__ must be an actual attribute on the module --
    a name left in __all__ after its import is deleted (or vice versa)
    is exactly the class of bug this test exists to catch."""
    missing = [name for name in utils.__all__ if not hasattr(utils, name)]
    assert not missing, f"__all__ names with no matching import: {missing}"


def test_send_webhook_delegates_to_hardened_implementation() -> None:
    """utils.send_webhook must BE webhook_notify.send_webhook (same object),
    not a re-implementation -- guards against ever resurrecting the old,
    unvalidated, SSRF-capable duplicate that used to live in lib/security.py."""
    assert utils.send_webhook is webhook_notify.send_webhook


def test_facade_send_webhook_honors_the_old_call_contract(monkeypatch) -> None:
    monkeypatch.setattr("webhook_notify._resolve_safe_ip", lambda h: "93.184.216.34")
    with patch("urllib.request.OpenerDirector.open", return_value=Mock()):
        result = utils.send_webhook("https://hooks.slack.com/T/B/x", {"text": "hi"}, timeout=10)
    assert result is True
