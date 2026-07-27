#!/usr/bin/env bash
# run_pilot_task.sh -- orchestrates one pilot task's 3-copy comparison
# (Copy A vanilla / Copy B minimal / Copy C standard) per
# experiments/20260727-config-effectiveness-opportunistic/{claim,estimand,controls}.md.
#
# Usage:
#   ./run_pilot_task.sh <target_repo_path> <task_id> <prompt_file>
#
# <target_repo_path>  path to the real repo the task lives in (must be a git repo,
#                      any uncommitted work should be committed/stashed first --
#                      this script worktrees off HEAD)
# <task_id>            short slug, e.g. "task01-offbyone-review"
# <prompt_file>         plain text file containing the EXACT prompt to send to all 3
#                      copies verbatim -- identical prompt is required for a fair
#                      comparison (see estimand.md L4 "order effects" caveat)
#
# Flags verified against `claude --help` before writing this script (2026-07-27) --
# --bare, --append-system-prompt, -p/--print all confirmed real, not guessed.

set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 <target_repo_path> <task_id> <prompt_file>" >&2
  exit 1
fi

TARGET_REPO="$(cd "$1" && pwd)"
TASK_ID="$2"
PROMPT_FILE="$(cd "$(dirname "$3")" && pwd)/$(basename "$3")"
EXPERIMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$EXPERIMENT_DIR/logs/$TASK_ID"
MINIMAL_DOC="$EXPERIMENT_DIR/../../docs/anti-hallucination.md"
WORKTREE_ROOT="$(dirname "$TARGET_REPO")/pilot-worktrees-$TASK_ID"

if [ ! -f "$PROMPT_FILE" ]; then
  echo "ERROR: prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi
if [ ! -f "$MINIMAL_DOC" ]; then
  echo "ERROR: minimal doc not found: $MINIMAL_DOC (expected docs/anti-hallucination.md)" >&2
  exit 1
fi

REPO_NAME="$(basename "$TARGET_REPO")"
HEAD_SHA="$(git -C "$TARGET_REPO" rev-parse HEAD)"
echo "Target repo: $TARGET_REPO"
echo "HEAD: $HEAD_SHA"
echo "Task ID: $TASK_ID"
echo "Prompt file: $PROMPT_FILE"
echo ""

mkdir -p "$LOG_DIR" "$WORKTREE_ROOT"

for COPY in A B C; do
  WT_PATH="$WORKTREE_ROOT/${REPO_NAME}-${COPY}"
  if [ -d "$WT_PATH" ]; then
    echo "Worktree $WT_PATH already exists, reusing (not re-creating)."
  else
    echo "Creating worktree for Copy $COPY at $WT_PATH (detached at $HEAD_SHA)..."
    git -C "$TARGET_REPO" worktree add --detach "$WT_PATH" "$HEAD_SHA"
  fi
done

echo ""
echo "=== Running Copy A (vanilla: --bare, no config) ==="
( cd "$WORKTREE_ROOT/${REPO_NAME}-A" && \
  claude -p --bare --no-session-persistence < "$PROMPT_FILE" \
  > "$LOG_DIR/A_vanilla.txt" 2> "$LOG_DIR/A_vanilla.stderr.txt" ) \
  && echo "  -> $LOG_DIR/A_vanilla.txt" \
  || echo "  !! Copy A run failed or errored -- check $LOG_DIR/A_vanilla.stderr.txt (counts as no-catch per ICE composite strategy, see estimand.md)"

echo ""
echo "=== Running Copy B (minimal: --bare + docs/anti-hallucination.md as system prompt) ==="
( cd "$WORKTREE_ROOT/${REPO_NAME}-B" && \
  claude -p --bare --no-session-persistence --append-system-prompt "$(cat "$MINIMAL_DOC")" < "$PROMPT_FILE" \
  > "$LOG_DIR/B_minimal.txt" 2> "$LOG_DIR/B_minimal.stderr.txt" ) \
  && echo "  -> $LOG_DIR/B_minimal.txt" \
  || echo "  !! Copy B run failed or errored -- check $LOG_DIR/B_minimal.stderr.txt (counts as no-catch per ICE composite strategy, see estimand.md)"

echo ""
echo "=== Running Copy C (standard: full CLAUDE.md/rules/skills/hooks, no special flags) ==="
( cd "$WORKTREE_ROOT/${REPO_NAME}-C" && \
  claude -p --no-session-persistence < "$PROMPT_FILE" \
  > "$LOG_DIR/C_standard.txt" 2> "$LOG_DIR/C_standard.stderr.txt" ) \
  && echo "  -> $LOG_DIR/C_standard.txt" \
  || echo "  !! Copy C run failed or errored -- check $LOG_DIR/C_standard.stderr.txt (counts as no-catch per ICE composite strategy, see estimand.md)"

echo ""
echo "Done. Next step: read the 3 logs in $LOG_DIR/, grade each against the"
echo "task's PRE-REGISTERED one-line catch criterion (written before reading any of"
echo "these logs), then run:"
echo "  python score_pilot.py --task-id $TASK_ID --criterion \"<criterion text>\" --catch-a <0|1> --catch-b <0|1> --catch-c <0|1>"
echo ""
echo "Worktrees left in place at $WORKTREE_ROOT for later inspection --"
echo "clean up manually with: git -C \"$TARGET_REPO\" worktree remove <path> --force"
