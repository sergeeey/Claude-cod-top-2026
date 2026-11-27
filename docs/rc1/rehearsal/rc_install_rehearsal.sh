#!/usr/bin/env bash
# RC 1.0 isolated install rehearsal. Never writes to the real ~/.claude.
# Usage: bash docs/rc1/rehearsal/rc_install_rehearsal.sh <scratch-dir>
# Env: LIVE_CLAUDE_DIR (default "$HOME/.claude") is only READ, for the before/after snapshot.
set -u
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
S="$1"
LIVE="${LIVE_CLAUDE_DIR:-$HOME/.claude}"
HERE="$REPO/docs/rc1/rehearsal"
STAMP="$(date +%Y%m%d_%H%M%S)"
T="$S/rc_iso_$STAMP"; T2="$S/rc_iso_force_$STAMP"
mkdir -p "$T" "$T2/.claude"
cd "$REPO" || exit 2

echo "== 1. live snapshot before (read-only)"
python scripts/snapshot_state.py --out "$S/rc_snap_before_$STAMP" --live "$LIVE" >/dev/null 2>&1; echo "snapshot exit=$?"

echo "== 2. clean isolated install (standard profile)"
HOME="$T" USERPROFILE="$T" bash install.sh --target="$T/.claude" --non-interactive --profile=standard \
  > "$S/rc_install_$STAMP.log" 2>&1
echo "install exit=$?; installed files: $(find "$T/.claude" -type f | wc -l)"

echo "== 3. hook wiring in the isolated settings.json"
python "$HERE/rc_wiring_check.py" "$T/.claude" --live "$LIVE"; echo "wiring exit=$?"

echo "== 4. doctor against the isolated home"
HOME="$T" USERPROFILE="$T" python "$REPO/scripts/doctor.py" > "$S/rc_doctor_$STAMP.log" 2>&1; echo "doctor exit=$?"

echo "== 5. --force-replace over a pre-existing user config, then roll back from backups"
printf 'USER ORIGINAL CLAUDE.md\n' > "$T2/.claude/CLAUDE.md"
printf '{"user_marker": "original"}\n' > "$T2/.claude/settings.json"
H_MD="$(sha256sum "$T2/.claude/CLAUDE.md" | cut -c1-16)"; H_SET="$(sha256sum "$T2/.claude/settings.json" | cut -c1-16)"
HOME="$T2" USERPROFILE="$T2" bash install.sh --target="$T2/.claude" --non-interactive --force-replace \
  --profile=standard > "$S/rc_install_force_$STAMP.log" 2>&1
echo "install exit=$?"
BMD="$(ls "$T2/.claude"/CLAUDE.md.backup.* 2>/dev/null | head -1)"; BSET="$(ls "$T2/.claude"/settings.json.backup.* 2>/dev/null | head -1)"
echo "backups: CLAUDE.md=${BMD:+yes} settings.json=${BSET:+yes}"
[ -n "$BMD" ] && cp "$BMD" "$T2/.claude/CLAUDE.md"
[ -n "$BSET" ] && cp "$BSET" "$T2/.claude/settings.json"
echo "rollback identical: CLAUDE.md=$([ "$(sha256sum "$T2/.claude/CLAUDE.md" | cut -c1-16)" = "$H_MD" ] && echo yes || echo NO)" \
     "settings.json=$([ "$(sha256sum "$T2/.claude/settings.json" | cut -c1-16)" = "$H_SET" ] && echo yes || echo NO)"

echo "== 6. live snapshot after and compare"
python scripts/snapshot_state.py --out "$S/rc_snap_after_$STAMP" --live "$LIVE" >/dev/null 2>&1
B="$(ls "$S/rc_snap_before_$STAMP"/*.json | head -1)"; A="$(ls "$S/rc_snap_after_$STAMP"/*.json | head -1)"
python scripts/snapshot_state.py --compare "$B" "$A" 2>&1 | sed -n '1,12p'
echo "STAMP=$STAMP"
