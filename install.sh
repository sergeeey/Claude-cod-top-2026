#!/bin/bash
# Claude Code Config Installer v11.0
# Usage: bash install.sh [minimal|standard|full]

set -e

CLAUDE_DIR="$HOME/.claude"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${1:-standard}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; exit 1; }

# --- Backup existing config ---
backup_existing() {
    if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
        BACKUP_DIR="$CLAUDE_DIR/backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        cp "$CLAUDE_DIR/CLAUDE.md" "$BACKUP_DIR/" 2>/dev/null || true
        cp "$CLAUDE_DIR/settings.json" "$BACKUP_DIR/" 2>/dev/null || true
        [ -d "$CLAUDE_DIR/rules" ] && cp -r "$CLAUDE_DIR/rules" "$BACKUP_DIR/" 2>/dev/null || true
        warn "Existing config backed up to $BACKUP_DIR"
    fi
}

# --- Layer 1: Core (always installed) ---
install_core() {
    mkdir -p "$CLAUDE_DIR/rules"

    cp "$SCRIPT_DIR/claude-md/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
    log "CLAUDE.md installed (70 lines)"

    cp "$SCRIPT_DIR/rules/"*.md "$CLAUDE_DIR/rules/"
    log "Rules installed (5 files)"

    # Merge settings.json (hooks + permissions)
    if [ -f "$CLAUDE_DIR/settings.json" ]; then
        warn "settings.json exists — manual merge recommended"
        cp "$SCRIPT_DIR/hooks/settings.json" "$CLAUDE_DIR/settings.json.new"
        log "New settings saved as settings.json.new"
    else
        cp "$SCRIPT_DIR/hooks/settings.json" "$CLAUDE_DIR/settings.json"
        log "settings.json installed"
    fi
}

# --- Layer 2: Hooks ---
install_hooks() {
    mkdir -p "$CLAUDE_DIR/hooks"
    cp "$SCRIPT_DIR/hooks/"*.py "$CLAUDE_DIR/hooks/"
    log "Hooks installed (9 scripts)"
}

# --- Layer 3: Scripts ---
install_scripts() {
    mkdir -p "$CLAUDE_DIR/scripts"
    cp "$SCRIPT_DIR/scripts/redact.py" "$CLAUDE_DIR/scripts/"
    cp "$SCRIPT_DIR/scripts/test_redact.py" "$CLAUDE_DIR/scripts/"
    log "PII redaction scripts installed"
}

# --- Layer 4: Skills ---
install_skills() {
    mkdir -p "$CLAUDE_DIR/skills"
    cp -r "$SCRIPT_DIR/skills/"* "$CLAUDE_DIR/skills/"
    log "Skills installed (8 skills)"
}

# --- Layer 5: Agents ---
install_agents() {
    mkdir -p "$CLAUDE_DIR/agents"
    cp "$SCRIPT_DIR/agents/"*.md "$CLAUDE_DIR/agents/"
    log "Agents installed (13 agents)"
}

# --- Layer 6: MCP Profiles ---
install_mcp() {
    mkdir -p "$CLAUDE_DIR/mcp-profiles"
    cp "$SCRIPT_DIR/mcp-profiles/"* "$CLAUDE_DIR/mcp-profiles/"
    log "MCP profiles installed (3 profiles + switch script)"
}

# --- Layer 7: Memory templates ---
install_memory() {
    mkdir -p "$CLAUDE_DIR/memory/projects"
    if [ -d "$SCRIPT_DIR/memory/templates" ]; then
        for tmpl in "$SCRIPT_DIR/memory/templates/"*.md; do
            [ -f "$tmpl" ] || continue
            target="$CLAUDE_DIR/memory/$(basename "$tmpl" .template.md).md"
            if [ ! -f "$target" ]; then
                cp "$tmpl" "$target"
                log "Memory template: $(basename "$tmpl")"
            else
                warn "Memory file exists, skipping: $(basename "$target")"
            fi
        done
    fi
}

# --- Main ---
echo "=== Claude Code Config Installer v11.0 ==="
echo "Profile: $PROFILE"
echo ""

backup_existing

case "$PROFILE" in
    minimal)
        install_core
        ;;
    standard)
        install_core
        install_hooks
        install_scripts
        install_skills
        install_agents
        ;;
    full)
        install_core
        install_hooks
        install_scripts
        install_skills
        install_agents
        install_mcp
        install_memory
        ;;
    *)
        err "Unknown profile: $PROFILE. Use: minimal | standard | full"
        ;;
esac

echo ""
log "Installation complete ($PROFILE profile)"
echo ""
echo "Next steps:"
echo "  1. Review ~/.claude/CLAUDE.md — adapt IDENTITY section"
echo "  2. Check ~/.claude/settings.json — verify hooks paths"
echo "  3. Restart Claude Code to apply changes"
[ "$PROFILE" = "full" ] && echo "  4. Set MCP profile: powershell ~/.claude/mcp-profiles/switch-profile.ps1 core"
