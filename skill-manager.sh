#!/bin/bash
# Skill Manager v1.0 — Install, remove, search, and manage Claude Code skills.
# Usage: bash skill-manager.sh <command> [args]
#
# Commands:
#   list                  Show installed and available skills
#   search <query>        Search skills by keyword
#   install <name|all>    Install a skill (or all extensions)
#   remove <name>         Remove an installed skill
#   info <name>           Show detailed skill information
#   update                Re-install all installed skills from source

set -e

# WHY: ${var,,} lowercase expansion (used in search/info) is a bash 4+ feature.
# macOS ships bash 3.2, where it is a syntax error — fail early with a clear message
# instead of a cryptic crash. err() is not defined yet, so use a raw echo.
if [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
    echo "Error: bash 4+ required (found $BASH_VERSION). On macOS: brew install bash" >&2
    exit 1
fi

CLAUDE_DIR="$HOME/.claude"
SKILLS_DIR="$CLAUDE_DIR/skills"
# WHY: SCRIPT_DIR resolves to the repo root, where skills/core/ and skills/extensions/ live
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REGISTRY="$SCRIPT_DIR/skills/registry.yaml"

# --- Colors ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }
info() { echo -e "${CYAN}→${NC} $1"; }

# --- Validate a skill name before it touches the filesystem ---
# WHY: name is interpolated into rm -rf / cp paths (cmd_remove, cmd_install_one).
# Without this, `remove ../../foo` resolves to a path OUTSIDE $SKILLS_DIR and
# rm -rf would delete it. Restrict to a safe charset — no slashes, no "..".
validate_skill_name() {
    [[ "$1" =~ ^[a-zA-Z0-9._-]+$ ]] || err "Invalid skill name: '$1' (allowed: letters, digits, . _ -)"
}

# --- Parse YAML (lightweight, no dependencies) ---
# WHY: Avoid requiring yq/python for a simple flat YAML structure.
# This parser handles the registry.yaml format only.
parse_skills_from_registry() {
    local section="$1"  # "core" or "extensions"
    local in_section=false
    local current_name=""
    local current_desc=""
    local current_cat=""
    local current_triggers=""

    while IFS= read -r line; do
        # Detect section start
        if [[ "$line" =~ ^${section}: ]]; then
            in_section=true
            continue
        fi
        # Detect next top-level section (exit current)
        if $in_section && [[ "$line" =~ ^[a-z] ]] && [[ ! "$line" =~ ^[[:space:]] ]]; then
            # Flush last entry
            if [ -n "$current_name" ]; then
                echo "${current_name}|${current_cat}|${current_desc}|${current_triggers}"
            fi
            # WHY: clear before break so the post-loop flush doesn't re-emit this
            # same entry — that double-printed the last skill of every non-final section.
            current_name=""
            break
        fi
        if ! $in_section; then continue; fi

        # Parse fields
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*name:[[:space:]]*(.+) ]]; then
            # Flush previous entry
            if [ -n "$current_name" ]; then
                echo "${current_name}|${current_cat}|${current_desc}|${current_triggers}"
            fi
            current_name="${BASH_REMATCH[1]}"
            current_cat=""
            current_desc=""
            current_triggers=""
        elif [[ "$line" =~ ^[[:space:]]*category:[[:space:]]*(.+) ]]; then
            current_cat="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]*description:[[:space:]]*\"(.+)\" ]]; then
            current_desc="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]*triggers:[[:space:]]*\[(.+)\] ]]; then
            current_triggers="${BASH_REMATCH[1]}"
        fi
    done < "$REGISTRY"
    # Flush last entry
    if $in_section && [ -n "$current_name" ]; then
        echo "${current_name}|${current_cat}|${current_desc}|${current_triggers}"
    fi
}

# --- Check if skill is installed ---
is_installed() {
    local name="$1"
    [ -d "$SKILLS_DIR/$name" ] || [ -f "$SKILLS_DIR/$name.md" ]
}

# --- Find skill source path ---
find_skill_source() {
    local name="$1"
    if [ -d "$SCRIPT_DIR/skills/core/$name" ]; then
        echo "$SCRIPT_DIR/skills/core/$name"
    elif [ -f "$SCRIPT_DIR/skills/core/$name.md" ]; then
        echo "$SCRIPT_DIR/skills/core/$name.md"
    elif [ -d "$SCRIPT_DIR/skills/extensions/$name" ]; then
        echo "$SCRIPT_DIR/skills/extensions/$name"
    elif [ -f "$SCRIPT_DIR/skills/extensions/$name.md" ]; then
        echo "$SCRIPT_DIR/skills/extensions/$name.md"
    else
        echo ""
    fi
}

# ============================================================
# COMMANDS
# ============================================================

cmd_list() {
    echo ""
    echo -e "${BOLD}Core skills${NC} ${DIM}(installed by default)${NC}"
    echo ""
    while IFS='|' read -r name cat desc triggers; do
        if is_installed "$name"; then
            echo -e "  ${GREEN}●${NC} $name ${DIM}— $desc${NC}"
        else
            echo -e "  ${RED}○${NC} $name ${DIM}— $desc${NC}"
        fi
    done < <(parse_skills_from_registry "core")

    echo ""
    echo -e "${BOLD}Extension skills${NC} ${DIM}(install on demand)${NC}"
    echo ""
    while IFS='|' read -r name cat desc triggers; do
        local cat_label=""
        [ -n "$cat" ] && cat_label="${DIM}[$cat]${NC} "
        if is_installed "$name"; then
            echo -e "  ${GREEN}●${NC} $name ${cat_label}${DIM}— $desc${NC}"
        else
            echo -e "  ${RED}○${NC} $name ${cat_label}${DIM}— $desc${NC}"
        fi
    done < <(parse_skills_from_registry "extensions")

    # Community skills
    local has_community=false
    while IFS='|' read -r name cat desc triggers; do
        [ -z "$name" ] && continue
        if ! $has_community; then
            echo ""
            echo -e "${BOLD}Community skills${NC} ${DIM}(install via CLI)${NC}"
            echo ""
            has_community=true
        fi
        local cat_label=""
        [ -n "$cat" ] && cat_label="${DIM}[$cat]${NC} "
        if is_installed "$name"; then
            echo -e "  ${GREEN}●${NC} $name ${cat_label}${DIM}— $desc${NC}"
        else
            echo -e "  ${CYAN}◆${NC} $name ${cat_label}${DIM}— $desc${NC}"
        fi
    done < <(parse_skills_from_registry "community")

    echo ""
    echo -e "${DIM}● installed  ○ not installed  ◆ community (external)${NC}"
    echo ""
}

cmd_search() {
    local query="${1,,}"  # lowercase
    [ -z "$query" ] && err "Usage: skill-manager.sh search <query>"

    echo ""
    echo -e "${BOLD}Search results for:${NC} $query"
    echo ""
    local found=0
    for section in core extensions community; do
        while IFS='|' read -r name cat desc triggers; do
            local haystack="${name,,} ${cat,,} ${desc,,} ${triggers,,}"
            if [[ "$haystack" == *"$query"* ]]; then
                local status
                is_installed "$name" && status="${GREEN}●${NC}" || status="${RED}○${NC}"
                local cat_label=""
                [ -n "$cat" ] && cat_label="${DIM}[$cat]${NC} "
                echo -e "  $status $name ${cat_label}${DIM}— $desc${NC}"
                found=$((found + 1))
            fi
        done < <(parse_skills_from_registry "$section")
    done

    if [ "$found" -eq 0 ]; then
        warn "No skills matching '$query'"
    fi
    echo ""
}

cmd_install() {
    local name="$1"
    [ -z "$name" ] && err "Usage: skill-manager.sh install <name|all>"

    mkdir -p "$SKILLS_DIR"

    if [ "$name" = "all" ]; then
        info "Installing all extension skills..."
        while IFS='|' read -r sname cat desc triggers; do
            cmd_install_one "$sname"
        done < <(parse_skills_from_registry "extensions")
        return
    fi

    cmd_install_one "$name"
}

cmd_install_one() {
    local name="$1"
    validate_skill_name "$name"
    local src
    src=$(find_skill_source "$name")

    if [ -z "$src" ]; then
        err "Skill '$name' not found in registry. Run 'list' to see available skills."
    fi

    if [ -d "$src" ]; then
        mkdir -p "$SKILLS_DIR/$name"
        # WHY: "$src/." copies hidden files too (.mcp.json, .gitignore) — a plain
        # "$src"/* glob silently drops them, installing a broken skill. Surface
        # copy failures instead of masking them with 2>/dev/null || true.
        if ! cp -r "$src/." "$SKILLS_DIR/$name/"; then
            err "Failed to copy $name from $src"
        fi
        log "Installed: $name (directory)"
    elif [ -f "$src" ]; then
        cp "$src" "$SKILLS_DIR/$(basename "$src")"
        log "Installed: $name (file)"
    fi
}

cmd_remove() {
    local name="$1"
    [ -z "$name" ] && err "Usage: skill-manager.sh remove <name>"
    validate_skill_name "$name"

    if [ -d "$SKILLS_DIR/$name" ]; then
        rm -rf "$SKILLS_DIR/$name"
        log "Removed: $name"
    elif [ -f "$SKILLS_DIR/$name.md" ]; then
        rm "$SKILLS_DIR/$name.md"
        log "Removed: $name"
    else
        warn "Skill '$name' is not installed"
    fi
}

cmd_info() {
    local name="$1"
    [ -z "$name" ] && err "Usage: skill-manager.sh info <name>"
    validate_skill_name "$name"

    echo ""
    local found=false
    for section in core extensions; do
        while IFS='|' read -r sname cat desc triggers; do
            if [ "$sname" = "$name" ]; then
                found=true
                echo -e "${BOLD}$sname${NC}"
                echo ""
                [ -n "$cat" ] && echo -e "  Category:    $cat"
                echo -e "  Type:        $section"
                echo -e "  Description: $desc"
                echo -e "  Triggers:    $triggers"
                is_installed "$name" && echo -e "  Status:      ${GREEN}installed${NC}" || echo -e "  Status:      ${RED}not installed${NC}"

                # Show SKILL.md path if exists
                local src
                src=$(find_skill_source "$name")
                [ -n "$src" ] && echo -e "  Source:      $src"
                break 2
            fi
        done < <(parse_skills_from_registry "$section")
    done

    # Check community skills if not found in core/extensions
    if ! $found; then
        while IFS='|' read -r sname cat desc triggers; do
            if [ "$sname" = "$name" ]; then
                found=true
                echo -e "${BOLD}$sname${NC} ${CYAN}(community)${NC}"
                echo ""
                [ -n "$cat" ] && echo -e "  Category:    $cat"
                echo -e "  Type:        community (external)"
                echo -e "  Description: $desc"
                echo -e "  Triggers:    $triggers"
                is_installed "$name" && echo -e "  Status:      ${GREEN}installed${NC}" || echo -e "  Status:      ${CYAN}not installed${NC}"
                # Extract install command and URL from registry
                local install_cmd
                install_cmd=$(sed -n "/name: $name/,/^  - name:/{ s/.*install: *\"\(.*\)\"/\1/p; }" "$REGISTRY")
                [ -n "$install_cmd" ] && echo -e "  Install:     $install_cmd"
                local url
                url=$(sed -n "/name: $name/,/^  - name:/{ s/.*url: *//p; }" "$REGISTRY")
                [ -n "$url" ] && echo -e "  URL:         $url"
                break
            fi
        done < <(parse_skills_from_registry "community")
    fi

    if ! $found; then
        err "Skill '$name' not found in registry"
    fi
    echo ""
}

cmd_update() {
    info "Updating all installed skills from source..."
    local updated=0

    for item in "$SKILLS_DIR"/*/; do
        [ -d "$item" ] || continue
        local name
        name=$(basename "$item")
        local src
        src=$(find_skill_source "$name")
        if [ -n "$src" ] && [ -d "$src" ]; then
            rm -rf "$item"
            mkdir -p "$item"
            # WHY: "$src/." includes hidden files; surface failures (see cmd_install_one).
            if ! cp -r "$src/." "$item/"; then
                err "Failed to update $name from $src"
            fi
            log "Updated: $name"
            updated=$((updated + 1))
        fi
    done

    for item in "$SKILLS_DIR"/*.md; do
        [ -f "$item" ] || continue
        local name
        name=$(basename "$item" .md)
        local src
        src=$(find_skill_source "$name")
        if [ -n "$src" ] && [ -f "$src" ]; then
            cp "$src" "$item"
            log "Updated: $name"
            updated=$((updated + 1))
        fi
    done

    echo ""
    log "Updated $updated skills"
}

# ============================================================
# MAIN
# ============================================================

COMMAND="${1:-}"
shift 2>/dev/null || true

case "$COMMAND" in
    list|ls)        cmd_list ;;
    search|find|s)  cmd_search "$@" ;;
    install|add|i)  cmd_install "$@" ;;
    remove|rm)      cmd_remove "$@" ;;
    info|show)      cmd_info "$@" ;;
    update|up)      cmd_update ;;
    ""|help|-h|--help)
        echo ""
        echo -e "${BOLD}Skill Manager v1.0${NC} — Manage Claude Code skills"
        echo ""
        echo "Usage: bash skill-manager.sh <command> [args]"
        echo ""
        echo "Commands:"
        echo "  list                  Show installed and available skills"
        echo "  search <query>        Search skills by keyword"
        echo "  install <name|all>    Install a skill (or all extensions)"
        echo "  remove <name>         Remove an installed skill"
        echo "  info <name>           Show detailed skill information"
        echo "  update                Re-install all installed skills from source"
        echo ""
        echo "Examples:"
        echo "  bash skill-manager.sh list"
        echo "  bash skill-manager.sh search finance"
        echo "  bash skill-manager.sh install security-audit"
        echo "  bash skill-manager.sh install all"
        echo "  bash skill-manager.sh remove suno-music"
        echo ""
        ;;
    *)
        err "Unknown command: $COMMAND. Run 'bash skill-manager.sh help' for usage."
        ;;
esac
