#!/usr/bin/env bash
# setup_release_scout_schedule.sh — register a weekly /release-scout run via cron.
#
# WHY this exists (2026-07-16): Claude Code's native CronCreate is SESSION-ONLY --
# it is gone when the Claude session exits and auto-expires after 7 days, so it
# cannot give you a durable weekly self-dev scan. A durable schedule must be an
# OS-level task. This registers one via crontab.
#
# SAFETY: dry-run by DEFAULT. It prints the exact crontab line it would add and
# changes nothing. Re-run with --apply to actually install it. This is deliberate:
# a script that silently edits your crontab is a standing-config change you should
# see first.
#
# ONE LINE YOU MUST VERIFY: the headless invocation that runs the command
# (CLAUDE_CMD below). Whether `claude -p "/release-scout"` triggers the command in
# your install is environment-specific and NOT verified by this script's author --
# confirm it runs interactively first, then trust the schedule. Override via env:
#   CLAUDE_CMD='/path/to/claude -p "/release-scout"' ./setup_release_scout_schedule.sh
set -euo pipefail

# Weekly, Monday 09:07 local (off-minute on purpose: :00 marks stampede the fleet).
SCHEDULE="${SCHEDULE:-7 9 * * 1}"
CLAUDE_CMD="${CLAUDE_CMD:-claude -p \"/release-scout\"}"
MARKER="# release-scout-weekly (managed by setup_release_scout_schedule.sh)"
CRON_LINE="${SCHEDULE} ${CLAUDE_CMD} ${MARKER}"

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

echo "Weekly /release-scout schedule"
echo "  schedule : ${SCHEDULE}  (min hour dom mon dow — Monday 09:07 local by default)"
echo "  command  : ${CLAUDE_CMD}"
echo "  crontab  : ${CRON_LINE}"
echo

if [ "$APPLY" -eq 0 ]; then
  echo "DRY RUN — nothing changed. To install it:"
  echo "  1. Verify the command works interactively first: ${CLAUDE_CMD}"
  echo "  2. Re-run:  $0 --apply"
  exit 0
fi

# Idempotent: strip any prior managed line, then append the current one.
existing="$(crontab -l 2>/dev/null | grep -vF "$MARKER" || true)"
printf '%s\n%s\n' "$existing" "$CRON_LINE" | grep -v '^$' | crontab -
echo "Installed. Current release-scout entry:"
crontab -l | grep -F "$MARKER"
echo
echo "Remove later with:  crontab -l | grep -vF '$MARKER' | crontab -"
