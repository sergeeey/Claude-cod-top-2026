#!/usr/bin/env python3
"""Run ruff on newly synced hooks and report."""

import subprocess
import sys

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
]

result = subprocess.run(
    [sys.executable, "-m", "ruff", "check", "--select", "I,F,E"] + NEW_HOOKS,
    capture_output=True,
    text=True,
)
print(result.stdout or "(no errors)")
if result.returncode != 0:
    print(result.stderr)
    sys.exit(result.returncode)
print(f"Checked {len(NEW_HOOKS)} hooks. Exit: {result.returncode}")
