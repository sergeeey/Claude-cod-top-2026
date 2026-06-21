#!/usr/bin/env bash
# update-claude.sh — pull latest config from GitHub and reinstall
# Usage:  bash update-claude.sh [--profile minimal|standard|full]
set -euo pipefail

PROFILE="standard"
for arg in "$@"; do
  case "$arg" in
    --profile=*) PROFILE="${arg#--profile=}" ;;
    --profile)   shift; PROFILE="$1" ;;
  esac
done

echo "=== Claude-cod-top-2026 updater (profile: $PROFILE) ==="

# Ensure we're in the repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "→ Pulling latest from origin/main..."
git pull origin main

echo "→ Running install.sh --profile=$PROFILE..."
bash install.sh --profile="$PROFILE" --non-interactive

echo ""
echo "✓ Done. Claude config updated to $(git rev-parse --short HEAD)."
