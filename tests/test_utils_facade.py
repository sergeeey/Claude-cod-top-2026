"""Regression tests for hooks/utils.py's backward-compatible facade.

WHY (Codex review, PR #328, 2026-09-03): removing lib/security.py's unsafe,
unused send_webhook() also silently dropped it from this facade's __all__ --
breaking the facade's own documented promise that `from utils import X`
keeps working for consumers outside this repo's tree (e.g. a personal hook).
Nothing caught this until an external review flagged it after merge. These
tests close that gap: every declared export must actually resolve, and
send_webhook specifically must be the real, hardened webhook_notify
implementation, not a stale duplicate.
"""

from __future__ import annotations

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
