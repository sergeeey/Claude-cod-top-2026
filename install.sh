#!/bin/bash
# Claude Code Config Installer v11.0
# Interactive installer with backup, conflict resolution, and 3 profiles.
# Usage: bash install.sh

set -e

CLAUDE_DIR="$HOME/.claude"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

INSTALLED_FILES=0
SKIPPED_FILES=0
BACKED_UP_FILES=0

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; exit 1; }
info() { echo -e "${CYAN}[i]${NC} $1"; }

# --- Ask user with default ---
ask() {
    local prompt="$1"
    local default="$2"
    local result
    echo -ne "${BOLD}$prompt${NC} [$default]: "
    read -r result
    echo "${result:-$default}"
}

# --- Handle file conflict ---
# Returns: "replace", "skip", or "merge" (merge only for specific files)
handle_conflict() {
    local file="$1"
    local supports_merge="$2"

    if [ ! -f "$file" ]; then
        echo "replace"
        return
    fi

    echo ""
    warn "File exists: $file"
    if [ "$supports_merge" = "true" ]; then
        echo "  [r] Replace (backup existing file)"
        echo "  [m] Merge (add our rules to existing)"
        echo "  [s] Skip (keep existing)"
        local choice
        choice=$(ask "Choice" "r")
    else
        echo "  [r] Replace (backup existing file)"
        echo "  [s] Skip (keep existing)"
        local choice
        choice=$(ask "Choice" "r")
    fi

    case "$choice" in
        r|R) echo "replace" ;;
        m|M) echo "merge" ;;
        s|S) echo "skip" ;;
        *)   echo "replace" ;;
    esac
}

# --- Backup a single file ---
backup_file() {
    local file="$1"
    if [ -f "$file" ]; then
        local backup="${file}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$file" "$backup"
        BACKED_UP_FILES=$((BACKED_UP_FILES + 1))
        info "Backup: $backup"
    fi
}

# --- Safe copy: handles conflicts ---
safe_copy() {
    local src="$1"
    local dst="$2"
    local supports_merge="${3:-false}"

    local action
    action=$(handle_conflict "$dst" "$supports_merge")

    case "$action" in
        replace)
            backup_file "$dst"
            cp "$src" "$dst"
            INSTALLED_FILES=$((INSTALLED_FILES + 1))
            log "Installed: $(basename "$dst")"
            ;;
        merge)
            backup_file "$dst"
            echo "" >> "$dst"
            echo "# --- Merged from claude-code-config $(date +%Y-%m-%d) ---" >> "$dst"
            cat "$src" >> "$dst"
            INSTALLED_FILES=$((INSTALLED_FILES + 1))
            log "Merged: $(basename "$dst")"
            ;;
        skip)
            SKIPPED_FILES=$((SKIPPED_FILES + 1))
            info "Skipped: $(basename "$dst")"
            ;;
    esac
}

# --- Safe copy directory: new files only or with conflict resolution ---
safe_copy_dir() {
    local src_dir="$1"
    local dst_dir="$2"
    local pattern="${3:-*}"

    mkdir -p "$dst_dir"
    for src_file in "$src_dir"/$pattern; do
        [ -f "$src_file" ] || continue
        local basename
        basename=$(basename "$src_file")
        safe_copy "$src_file" "$dst_dir/$basename"
    done
}

# --- Layer 1: Core (CLAUDE.md + integrity + security) ---
install_minimal() {
    info "Installing: CLAUDE.md + integrity.md + security.md"
    mkdir -p "$CLAUDE_DIR/rules"

    safe_copy "$SCRIPT_DIR/claude-md/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md" "true"
    safe_copy "$SCRIPT_DIR/rules/integrity.md" "$CLAUDE_DIR/rules/integrity.md"
    safe_copy "$SCRIPT_DIR/rules/security.md" "$CLAUDE_DIR/rules/security.md"
}

# --- Layer 2: All rules ---
install_rules() {
    info "Installing: all rules"
    mkdir -p "$CLAUDE_DIR/rules"
    safe_copy_dir "$SCRIPT_DIR/rules" "$CLAUDE_DIR/rules" "*.md"
}

# --- Layer 3: Hooks ---
install_hooks() {
    info "Installing: hooks (9 scripts)"
    mkdir -p "$CLAUDE_DIR/hooks"
    safe_copy_dir "$SCRIPT_DIR/hooks" "$CLAUDE_DIR/hooks" "*.py"
    safe_copy "$SCRIPT_DIR/hooks/settings.json" "$CLAUDE_DIR/settings.json" "true"
}

# --- Layer 4: Scripts ---
install_scripts() {
    info "Installing: PII redaction scripts"
    mkdir -p "$CLAUDE_DIR/scripts"
    safe_copy "$SCRIPT_DIR/scripts/redact.py" "$CLAUDE_DIR/scripts/redact.py"
    safe_copy "$SCRIPT_DIR/scripts/test_redact.py" "$CLAUDE_DIR/scripts/test_redact.py"
}

# --- Layer 5: Skills ---
install_skills() {
    info "Installing: skills (9 skills)"
    mkdir -p "$CLAUDE_DIR/skills"
    for skill_dir in "$SCRIPT_DIR/skills"/*/; do
        [ -d "$skill_dir" ] || continue
        local skill_name
        skill_name=$(basename "$skill_dir")
        mkdir -p "$CLAUDE_DIR/skills/$skill_name"
        cp -r "$skill_dir"* "$CLAUDE_DIR/skills/$skill_name/" 2>/dev/null || true
        INSTALLED_FILES=$((INSTALLED_FILES + 1))
    done
    # Standalone skill files
    for f in "$SCRIPT_DIR/skills/"*.md; do
        [ -f "$f" ] || continue
        safe_copy "$f" "$CLAUDE_DIR/skills/$(basename "$f")"
    done
    log "Skills installed"
}

# --- Layer 6: Agents ---
install_agents() {
    info "Installing: agents (13 agents)"
    mkdir -p "$CLAUDE_DIR/agents"
    safe_copy_dir "$SCRIPT_DIR/agents" "$CLAUDE_DIR/agents" "*.md"
}

# --- Layer 7: MCP Profiles ---
install_mcp() {
    info "Installing: MCP profiles (3 profiles + switch script)"
    mkdir -p "$CLAUDE_DIR/mcp-profiles"
    for f in "$SCRIPT_DIR/mcp-profiles/"*; do
        [ -f "$f" ] || continue
        safe_copy "$f" "$CLAUDE_DIR/mcp-profiles/$(basename "$f")"
    done
}

# --- Layer 8: Memory templates ---
install_memory() {
    info "Installing: memory templates"
    mkdir -p "$CLAUDE_DIR/memory/projects"
    for tmpl in "$SCRIPT_DIR/memory/templates/"*.md; do
        [ -f "$tmpl" ] || continue
        local target_name
        target_name=$(basename "$tmpl" .template.md)
        local target="$CLAUDE_DIR/memory/${target_name}.md"
        if [ -f "$target" ]; then
            info "Memory exists, skipping: ${target_name}.md"
            SKIPPED_FILES=$((SKIPPED_FILES + 1))
        else
            cp "$tmpl" "$target"
            INSTALLED_FILES=$((INSTALLED_FILES + 1))
            log "Memory template: ${target_name}.md"
        fi
    done
}

# ============================================================
# MAIN
# ============================================================

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Claude Code Config Installer v11.0        ║${NC}"
echo -e "${BOLD}║   Evidence Policy · Hooks · Skills · MCP    ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Check prerequisites
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    warn "Python not found. Hooks require Python 3.8+."
    warn "Install Python and re-run, or choose 'minimal' profile."
fi

# Profile selection
echo -e "${BOLD}Choose installation profile:${NC}"
echo ""
echo "  [1] minimal   — CLAUDE.md + integrity.md + security.md"
echo "                   3 files, ~100 lines. Evidence Policy + базовая безопасность."
echo ""
echo "  [2] standard  — minimal + все rules + hooks + skills + agents"
echo "                   Полная конфигурация без MCP-профилей."
echo ""
echo "  [3] full      — standard + MCP-профили + PII redaction + memory templates"
echo "                   Всё включено."
echo ""

PROFILE_NUM=$(ask "Profile (1/2/3)" "2")

case "$PROFILE_NUM" in
    1|minimal)  PROFILE="minimal" ;;
    2|standard) PROFILE="standard" ;;
    3|full)     PROFILE="full" ;;
    *)          PROFILE="standard" ;;
esac

echo ""
info "Selected profile: $PROFILE"
echo ""

# Execute installation
case "$PROFILE" in
    minimal)
        install_minimal
        ;;
    standard)
        install_minimal
        install_rules
        install_hooks
        install_skills
        install_agents
        ;;
    full)
        install_minimal
        install_rules
        install_hooks
        install_scripts
        install_skills
        install_agents
        install_mcp
        install_memory
        ;;
esac

# Summary
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "  Profile:  $PROFILE"
echo "  Installed: $INSTALLED_FILES files"
echo "  Skipped:   $SKIPPED_FILES files"
echo "  Backed up: $BACKED_UP_FILES files"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. Adapt IDENTITY section in ~/.claude/CLAUDE.md"
echo "  2. Restart Claude Code"
echo "  3. Run /context to verify configuration loaded"
if [ "$PROFILE" = "full" ]; then
    echo "  4. Set MCP profile:"
    echo "     powershell ~/.claude/mcp-profiles/switch-profile.ps1 core"
fi
echo ""
echo -e "${CYAN}Documentation: docs/ directory in this repository${NC}"
echo -e "${CYAN}Troubleshooting: docs/troubleshooting.md${NC}"
