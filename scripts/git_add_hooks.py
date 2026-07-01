#!/usr/bin/env python3
"""Stage synced hooks for git commit."""

import subprocess

NEW_HOOKS = [
    "hooks/agent_context_filter.py",
    "hooks/artifact_schema_validator.py",
    "hooks/doc_bridge.py",
    "hooks/doc_registry.py",
    "hooks/estimand_guard.py",
    "hooks/experiment_insight.py",
    "hooks/expert_registry.py",
    "hooks/file_auto_parser.py",
    "hooks/goal_budget_guard.py",
    "hooks/goal_stub_detector.py",
    "hooks/hook_observability.py",
    "hooks/hypothesis_router.py",
    "hooks/markitdown_auto_convert.py",
    "hooks/model_usage_tracker.py",
    "hooks/pattern_escalation_review.py",
    "hooks/pre_vault_write.py",
    "hooks/project_classifier.py",
    "hooks/smart_model_router.py",
    "scripts/hook_audit.py",
    "scripts/check_global_hooks.py",
    "scripts/sync_global_hooks.py",
    "scripts/lint_new_hooks.py",
    "scripts/fix_lint.py",
    "scripts/git_add_hooks.py",
]

result = subprocess.run(
    ["git", "add"] + NEW_HOOKS,
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.stderr:
    print(result.stderr)

status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
print(status.stdout[:2000])
