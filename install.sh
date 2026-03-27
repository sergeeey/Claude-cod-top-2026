#!/bin/bash
# Claude Code Config Installer v2.1
# Interactive installer with backup, conflict resolution, 3 profiles, and --link mode.
# Usage: bash install.sh [OPTIONS] [minimal|standard|full]

set -e

CLAUDE_DIR="$HOME/.claude"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LINK_MODE=false
NON_INTERACTIVE=false

# --- Parse CLI arguments ---
for arg in "$@"; do
    case "$arg" in
        --link) LINK_MODE=true ;;
        --non-interactive|--yes|-y) NON_INTERACTIVE=true ;;
        --profile=*) CLI_PROFILE="${arg#--profile=}" ;;
        --target=*) CLAUDE_DIR="${arg#--target=}" ;;
        minimal|standard|full|1|2|3) CLI_PROFILE="$arg" ;;
        --help|-h)
            echo "Usage: bash install.sh [OPTIONS] [minimal|standard|full]"
            echo ""
            echo "Options:"
            echo "  --link              Symlinks instead of copies (auto-update via git pull)"
            echo "  --non-interactive   Skip all prompts, use defaults"
            echo "  --yes, -y           Alias for --non-interactive"
            echo "  --profile=PROFILE   Set profile: minimal, standard, or full"
            echo "  --target=DIR        Install to DIR instead of ~/.claude"
            echo ""
            echo "Profiles:"
            echo "  minimal   CLAUDE.md + integrity.md + security.md"
            echo "  standard  minimal + all rules + hooks + skills + agents"
            echo "  full      standard + MCP profiles + PII redaction + memory"
            echo ""
            echo "Examples:"
            echo "  bash install.sh --profile=full --non-interactive"
            echo "  bash install.sh --link full"
            echo "  bash install.sh --target=/opt/claude-config minimal"
            exit 0
            ;;
        *) echo "Unknown argument: $arg (ignored)" ;;
    esac
done

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

# --- Ask user with default (respects --non-interactive) ---
ask() {
    local prompt="$1"
    local default="$2"
    if [ "$NON_INTERACTIVE" = true ]; then
        echo "$default"
        return
    fi
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

# --- Create symlink (--link mode) ---
safe_link() {
    local src="$1"
    local dst="$2"

    # Resolve absolute path for symlink target
    local abs_src
    abs_src="$(cd "$(dirname "$src")" && pwd)/$(basename "$src")"

    if [ -L "$dst" ]; then
        # Already a symlink — update if target differs
        local current_target
        current_target="$(readlink "$dst" 2>/dev/null || true)"
        if [ "$current_target" = "$abs_src" ]; then
            info "Link OK: $(basename "$dst")"
            SKIPPED_FILES=$((SKIPPED_FILES + 1))
            return
        fi
        rm "$dst"
    elif [ -d "$dst" ]; then
        err "Cannot link file: $dst is a directory. Remove it manually."
    elif [ -f "$dst" ]; then
        backup_file "$dst"
        rm "$dst"
    fi

    ln -s "$abs_src" "$dst"
    INSTALLED_FILES=$((INSTALLED_FILES + 1))
    log "Linked: $(basename "$dst") → $(basename "$(dirname "$abs_src")")/$(basename "$abs_src")"
}

# --- Safe copy: handles conflicts ---
safe_copy() {
    local src="$1"
    local dst="$2"
    local supports_merge="${3:-false}"

    # --link mode: symlink instead of copy
    if [ "$LINK_MODE" = true ]; then
        safe_link "$src" "$dst"
        return
    fi

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
    info "Installing: hooks (15 scripts + statusline)"
    mkdir -p "$CLAUDE_DIR/hooks"
    safe_copy_dir "$SCRIPT_DIR/hooks" "$CLAUDE_DIR/hooks" "*.py"
    # WHY: statusline.py lives at $HOME/.claude/statusline.py (not in hooks/)
    # because settings.json statusLine.command references it at that path
    safe_copy "$SCRIPT_DIR/hooks/statusline.py" "$CLAUDE_DIR/statusline.py"
    safe_copy "$SCRIPT_DIR/hooks/settings.json" "$CLAUDE_DIR/settings.json" "true"

    # WHY: settings.json uses $HOME as placeholder for hook paths.
    # Claude Code does NOT expand $HOME in settings.json — it must be a real path.
    # This substitution is the #1 manual step users forget, causing all hooks to fail silently.
    if [ -f "$CLAUDE_DIR/settings.json" ] && ! [ -L "$CLAUDE_DIR/settings.json" ]; then
        local real_home
        real_home="$HOME"
        # On Windows (MSYS/Git Bash), convert to forward-slash path
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
            real_home="$(cygpath -m "$HOME" 2>/dev/null || echo "$HOME")"
        fi
        if command -v python3 &>/dev/null; then
            python3 -c "
import json, sys
with open(sys.argv[1], 'r') as f:
    content = f.read()
content = content.replace('\$HOME', sys.argv[2])
# Validate it's still valid JSON
json.loads(content)
with open(sys.argv[1], 'w') as f:
    f.write(content)
" "$CLAUDE_DIR/settings.json" "$real_home"
        elif command -v python &>/dev/null; then
            python -c "
import json, sys
with open(sys.argv[1], 'r') as f:
    content = f.read()
content = content.replace('\$HOME', sys.argv[2])
json.loads(content)
with open(sys.argv[1], 'w') as f:
    f.write(content)
" "$CLAUDE_DIR/settings.json" "$real_home"
        else
            sed -i "s|\\\$HOME|$real_home|g" "$CLAUDE_DIR/settings.json"
        fi
        log "settings.json: \$HOME → $real_home"
    fi
}

# --- Layer 4: Scripts ---
install_scripts() {
    info "Installing: PII redaction scripts"
    mkdir -p "$CLAUDE_DIR/scripts"
    safe_copy "$SCRIPT_DIR/scripts/redact.py" "$CLAUDE_DIR/scripts/redact.py"
}

# --- Link a directory (--link mode): symlink entire dir ---
safe_link_dir() {
    local src_dir="$1"
    local dst_dir="$2"

    local abs_src
    abs_src="$(cd "$src_dir" && pwd)"

    if [ -L "$dst_dir" ]; then
        local current_target
        current_target="$(readlink "$dst_dir" 2>/dev/null || true)"
        if [ "$current_target" = "$abs_src" ]; then
            info "Link OK: $(basename "$dst_dir")/"
            SKIPPED_FILES=$((SKIPPED_FILES + 1))
            return
        fi
        rm "$dst_dir"
    elif [ -d "$dst_dir" ]; then
        warn "Directory exists: $dst_dir — linking individual files instead"
        # Fall back to per-file linking
        for src_file in "$src_dir"/*; do
            [ -f "$src_file" ] || continue
            safe_link "$src_file" "$dst_dir/$(basename "$src_file")"
        done
        return
    fi

    ln -s "$abs_src" "$dst_dir"
    INSTALLED_FILES=$((INSTALLED_FILES + 1))
    log "Linked dir: $(basename "$dst_dir")/ → repo"
}

# --- Layer 5a: Core Skills (always installed) ---
install_core_skills() {
    info "Installing: core skills (6 universal skills)"

    if [ "$LINK_MODE" = true ]; then
        # In link mode, symlink each core skill individually
        mkdir -p "$CLAUDE_DIR/skills"
        for skill_dir in "$SCRIPT_DIR/skills/core"/*/; do
            [ -d "$skill_dir" ] || continue
            local skill_name
            skill_name=$(basename "$skill_dir")
            safe_link_dir "$skill_dir" "$CLAUDE_DIR/skills/$skill_name"
        done
        for f in "$SCRIPT_DIR/skills/core/"*.md; do
            [ -f "$f" ] || continue
            safe_link "$f" "$CLAUDE_DIR/skills/$(basename "$f")"
        done
        log "Core skills linked"
        return
    fi

    mkdir -p "$CLAUDE_DIR/skills"
    for skill_dir in "$SCRIPT_DIR/skills/core"/*/; do
        [ -d "$skill_dir" ] || continue
        local skill_name
        skill_name=$(basename "$skill_dir")
        mkdir -p "$CLAUDE_DIR/skills/$skill_name"
        cp -r "$skill_dir"* "$CLAUDE_DIR/skills/$skill_name/" 2>/dev/null || true
        INSTALLED_FILES=$((INSTALLED_FILES + 1))
    done
    for f in "$SCRIPT_DIR/skills/core/"*.md; do
        [ -f "$f" ] || continue
        safe_copy "$f" "$CLAUDE_DIR/skills/$(basename "$f")"
    done
    log "Core skills installed"
}

# --- Layer 5b: Extension Skills (user picks) ---
install_extension_skills() {
    local extensions_dir="$SCRIPT_DIR/skills/extensions"
    [ -d "$extensions_dir" ] || return

    echo ""
    echo -e "${BOLD}Extension skills (domain-specific, optional):${NC}"
    echo ""

    # Collect available extensions
    local ext_names=()
    local ext_descs=()
    local idx=1

    for skill_dir in "$extensions_dir"/*/; do
        [ -d "$skill_dir" ] || continue
        local name
        name=$(basename "$skill_dir")
        ext_names+=("$name")
        # Extract description from SKILL.md frontmatter
        local desc=""
        if [ -f "$skill_dir/SKILL.md" ]; then
            desc=$(sed -n 's/^description:.*\] *//p' "$skill_dir/SKILL.md" 2>/dev/null | head -1)
        fi
        [ -z "$desc" ] && desc="$name"
        ext_descs+=("$desc")
        echo "  [$idx] $name — $desc"
        idx=$((idx + 1))
    done
    for f in "$extensions_dir/"*.md; do
        [ -f "$f" ] || continue
        local name
        name=$(basename "$f" .md)
        ext_names+=("$name")
        ext_descs+=("$name (standalone skill)")
        echo "  [$idx] $name"
        idx=$((idx + 1))
    done

    echo ""
    echo "  [a] Install ALL extensions"
    echo "  [n] Skip (none)"
    echo ""
    local choices
    if [ "$NON_INTERACTIVE" = true ]; then
        choices="a"
        info "Non-interactive: installing all extensions"
    else
        choices=$(ask "Extensions (comma-separated numbers, 'a', or 'n')" "n")
    fi

    if [ "$choices" = "n" ] || [ "$choices" = "N" ]; then
        info "Skipping extension skills"
        return
    fi

    if [ "$choices" = "a" ] || [ "$choices" = "A" ]; then
        choices=$(seq -s, 1 ${#ext_names[@]})
    fi

    # Parse comma-separated choices
    IFS=',' read -ra selected <<< "$choices"
    for pick in "${selected[@]}"; do
        pick=$(echo "$pick" | tr -d ' ')
        # Validate number
        if ! [[ "$pick" =~ ^[0-9]+$ ]] || [ "$pick" -lt 1 ] || [ "$pick" -gt ${#ext_names[@]} ]; then
            warn "Invalid choice: $pick (skipped)"
            continue
        fi
        local sel_name="${ext_names[$((pick - 1))]}"
        local src_dir="$extensions_dir/$sel_name"
        local src_file="$extensions_dir/$sel_name.md"

        if [ -d "$src_dir" ]; then
            if [ "$LINK_MODE" = true ]; then
                safe_link_dir "$src_dir" "$CLAUDE_DIR/skills/$sel_name"
            else
                mkdir -p "$CLAUDE_DIR/skills/$sel_name"
                cp -r "$src_dir"/* "$CLAUDE_DIR/skills/$sel_name/" 2>/dev/null || true
                INSTALLED_FILES=$((INSTALLED_FILES + 1))
            fi
            log "Extension installed: $sel_name"
        elif [ -f "$src_file" ]; then
            safe_copy "$src_file" "$CLAUDE_DIR/skills/$sel_name.md"
            log "Extension installed: $sel_name"
        fi
    done
}

# --- Layer 6: Agents ---
install_agents() {
    info "Installing: agents (13 agents)"
    if [ "$LINK_MODE" = true ]; then
        safe_link_dir "$SCRIPT_DIR/agents" "$CLAUDE_DIR/agents"
        return
    fi
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
echo -e "${BOLD}║   Claude Code Config Installer v11.1        ║${NC}"
echo -e "${BOLD}║   Evidence Policy · Hooks · Skills · MCP    ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
if [ "$LINK_MODE" = true ]; then
    echo ""
    echo -e "${CYAN}  Mode: --link (symlinks → auto-update via git pull)${NC}"
fi
echo ""

# Check symlink permissions on Windows (--link mode)
if [ "$LINK_MODE" = true ]; then
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        mkdir -p "$CLAUDE_DIR"
        if ! ln -s "$SCRIPT_DIR/install.sh" "$CLAUDE_DIR/.symlink_test" 2>/dev/null; then
            err "--link mode requires Developer Mode or Administrator rights on Windows.\n       Enable: Settings → For Developers → Developer Mode"
        fi
        rm -f "$CLAUDE_DIR/.symlink_test"
    fi
fi

# Check prerequisites
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    warn "Python not found. Hooks require Python 3.8+."
    warn "Install Python and re-run, or choose 'minimal' profile."
fi

# Profile selection
echo -e "${BOLD}Choose installation profile:${NC}"
echo ""
echo "  [1] minimal   — CLAUDE.md + integrity.md + security.md"
echo "                   3 files, ~100 lines. Evidence Policy + basic security."
echo ""
echo "  [2] standard  — minimal + все rules + hooks + skills + agents"
echo "                   Full config without MCP profiles."
echo ""
echo "  [3] full      — standard + MCP-профили + PII redaction + memory templates"
echo "                   Everything included."
echo ""

# Use CLI profile if provided, otherwise ask interactively
if [ -n "${CLI_PROFILE:-}" ]; then
    PROFILE_NUM="$CLI_PROFILE"
elif [ "$NON_INTERACTIVE" = true ]; then
    PROFILE_NUM="standard"
    info "Non-interactive: defaulting to 'standard' profile"
else
    PROFILE_NUM=$(ask "Profile (1/2/3)" "1")
fi

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
        install_core_skills
        install_extension_skills
        install_agents
        ;;
    full)
        install_minimal
        install_rules
        install_hooks
        install_scripts
        install_core_skills
        install_extension_skills
        install_agents
        install_mcp
        install_memory
        ;;
esac

# Write marker for auto-update (--link mode only)
if [ "$LINK_MODE" = true ]; then
    echo "$SCRIPT_DIR" > "$CLAUDE_DIR/.claude-code-config-repo"
    log "Auto-update marker saved (SessionStart will git pull)"
fi

# Summary
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "  Profile:  $PROFILE"
if [ "$LINK_MODE" = true ]; then
    echo "  Mode:     symlink (auto-update)"
fi
echo "  Installed: $INSTALLED_FILES files"
echo "  Skipped:   $SKIPPED_FILES files"
echo "  Backed up: $BACKED_UP_FILES files"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. Adapt IDENTITY section in ~/.claude/CLAUDE.md"
echo "  2. Restart Claude Code"
echo "  3. Run /context to verify configuration loaded"
STEP=4
if [ "$LINK_MODE" = true ]; then
    echo "  $STEP. To update config: cd $(pwd) && git pull"
    STEP=$((STEP + 1))
fi
if [ "$PROFILE" = "full" ]; then
    echo "  $STEP. Set MCP profile:"
    echo "     bash ~/.claude/mcp-profiles/switch-profile.sh core"
    echo "     # or on Windows: powershell ~/.claude/mcp-profiles/switch-profile.ps1 core"
fi
echo ""
echo -e "${CYAN}Documentation: docs/ directory in this repository${NC}"
echo -e "${CYAN}Troubleshooting: docs/troubleshooting.md${NC}"
