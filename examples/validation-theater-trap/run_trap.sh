#!/usr/bin/env bash
# Thin wrapper around run_trap.py for shell users.
# The Python driver is the source of truth — it is cross-platform and has no deps.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python "$DIR/run_trap.py"
